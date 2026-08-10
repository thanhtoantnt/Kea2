"""
HarmonyOS UI explorer (Feature 1 substitute for Fastbot).

No Fastbot on HarmonyOS NEXT. This module dumps hierarchy via hmdriver2 and
drives exploration. Ideas borrowed from old Kea / HMDroidbot lineage
(DroidBot policies) — implemented in-tree, no HMDroidbot dependency:

  - light UTG: structure hash + prefer unseen widget edges
  - multi-action: tap / scroll / long-press / setText / back
  - tarpit: same state streak → force scroll or Back
  - steps-outside FG → relaunch (rate-limited)

Also writes Fastbot-compatible steps.log for HTML bug reports.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .hmDriver import HMDevice, _attrs, _parse_bounds, _walk_nodes
from .hdcUtils import HDCDevice
from .utils import StampManager, getLogger

logger = getLogger(__name__)

# old Kea InputPolicy-inspired caps (scaled down for dump-heavy Harmony)
_MAX_STEPS_OUTSIDE = 8
_TARPIT_STREAK = 4
_UTG_EDGE_CAP = 4000

# labels / types that are never useful explore targets
_NOISE_EXACT = {
    "metaballNode",
    "ClockStatusView",
    "StatusBarView",
    "StatusBarBox",
    "BatteryComponent-batteryIcon_Text_batterySoc",
    "TimeView_Text_timeText",
}
_NOISE_TYPE = {"StatusBarView", "StatusBarBox", "ClockStatusView"}
_TIME_RE = re.compile(r"^\d{1,2}(, ?: ?|, :, )\d{2}$|^\d{1,2}:\d{2}$|^:$")
_BATTERY_RE = re.compile(r"^\d{1,3}$")


def _is_noise(label: str, typ: str, y1: int, cy: int) -> bool:
    if cy < 120 or y1 < 80:  # status bar band
        return True
    if label in _NOISE_EXACT or typ in _NOISE_TYPE:
        return True
    if _TIME_RE.match(label) or _BATTERY_RE.match(label):
        return True
    if "status_bar" in label.lower() or "statusbar" in label.lower():
        return True
    if label.lower().startswith("double tap"):  # a11y chrome
        return True
    # H5 error chrome (Maps Discover rankings) — don't thrash Retry
    low = label.lower()
    if "loading error" in low or low in ("retry", "reload"):
        return True
    # AppGallery/GameCenter feed CTAs — installing apps mid-explore is destructive
    if low in ("install", "update", "open", "get", "下载", "安装", "更新", "打开"):
        return True
    return False


def _clickable_candidates(hierarchy: dict) -> List[Tuple[int, int, int, int, int, int, str, str, int]]:
    """Return (cx, cy, x1, y1, x2, y2, label, typ, weight) for plausible taps.

    Higher weight = more likely pick. Music Mode A: bottom feed rows (artist
    names) sat next to tab_text and opened mini-player — bias real tabs/ids.
    """
    out: List[Tuple[int, int, int, int, int, int, str, str, int]] = []
    for node in _walk_nodes(hierarchy):
        a = _attrs(node)
        bounds = _parse_bounds(a.get("bounds"))
        if not bounds:
            continue
        x1, y1, x2, y2 = bounds
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        # skip full-screen / status-bar-ish huge nodes
        if (x2 - x1) > 1000 and (y2 - y1) > 2000:
            continue
        clickable = str(a.get("clickable", "")).lower() in ("true", "1")
        typ = str(a.get("type") or "")
        text = str(a.get("text") or "")
        desc = str(a.get("description") or "")
        nid = str(a.get("id") or "")
        label = (text or desc or typ or "node")[:40]
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        if _is_noise(label, typ, y1, cy):
            continue
        # prefer interactive types
        interesting = clickable or typ in (
            "Button",
            "SymbolGlyph",
            "Image",
            "Text",
            "Row",
            "Column",
            "Stack",
            "ListItem",
            "GridItem",
            "Tabs",
            "TabBar",
            "Toggle",
        )
        if not interesting:
            continue
        if not (text or desc or clickable or typ in ("Button", "SymbolGlyph", "Toggle")):
            continue
        # scoring
        w = 1
        if desc and not text:
            w += 2  # icon-only a11y nodes (hybrid) — still tappable via description
        idl = nid.lower()
        if nid == "tab_text" or idl.startswith("tabs_") or "tab_text" in idl:
            w += 8
        if typ in ("Tabs", "TabBar") or "tab" in idl:
            w += 4
        if typ == "Button" or clickable:
            w += 2
        # bottom band without tab id = feed/player chrome — deprioritize
        if cy >= 2400 and not (nid == "tab_text" or idl.startswith("tabs_") or "tab" in idl):
            w -= 5
            if len(label) > 8:
                w -= 8  # cnnb feed titles sit in bottom band
        # mini-player / cast sheet bait
        low = label.lower()
        if low in ("play on", "this device") or "khz" in low or "spatial audio" in low:
            w -= 6
        if low in ("install", "update", "open", "get", "下载", "安装", "更新"):
            w -= 10
        # bind-phone / password-reset sheets trap explore (baiinfo zero-exec)
        if any(k in (text or "") for k in ("绑定手机", "忘记密码", "获取验证码", "Bind phone")):
            w -= 12
        # Maps: Drive/导航 leaves bottom-nav shell (Mode B flake)
        if low in ("drive", "导航", "route", "go") or "drive" == low:
            w -= 6
        if w < 1:
            w = 1
        out.append((cx, cy, x1, y1, x2, y2, label, typ, w))
    return out


def _weighted_choice(cands: List[Tuple]) -> Tuple:
    """Pick candidate by weight (last field)."""
    if not cands:
        raise ValueError("empty cands")
    weights = [max(1, int(c[-1])) for c in cands]
    return random.choices(cands, weights=weights, k=1)[0]


def _state_hash(hierarchy: dict) -> str:
    """Content-light structure fingerprint (UTG node id).

    Uses type + id + short text/desc + coarse grid — ignores volatile feed copy
    length so similar shells collide (old Kea structure_str idea, cheap).
    """
    parts: List[str] = []
    for node in _walk_nodes(hierarchy or {}):
        a = _attrs(node)
        typ = str(a.get("type") or "")
        nid = str(a.get("id") or "")
        t = str(a.get("text") or "").strip()[:12]
        d = str(a.get("description") or "").strip()[:12]
        b = _parse_bounds(a.get("bounds"))
        if not b:
            continue
        # 4x6 grid cell
        cx = (b[0] + b[2]) // 2
        cy = (b[1] + b[3]) // 2
        cell = f"{cx // 320}x{cy // 480}"
        lab = t or d
        # drop long feed titles from hash (keep short chrome labels)
        if len(lab) > 10 and typ in ("Text", "Span"):
            lab = lab[:4]
        parts.append(f"{typ}|{nid}|{lab}|{cell}")
        if len(parts) >= 80:
            break
    raw = "\n".join(parts) or "empty"
    return hashlib.md5(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _editable_candidates(hierarchy: dict) -> List[Tuple[int, int, int, int, int, int, str]]:
    """(cx,cy,x1,y1,x2,y2,label) for TextInput-like nodes."""
    out = []
    for node in _walk_nodes(hierarchy or {}):
        a = _attrs(node)
        typ = str(a.get("type") or "")
        t = str(a.get("text") or "")
        d = str(a.get("description") or "")
        nid = str(a.get("id") or "").lower()
        blob = f"{typ} {t} {d} {nid}".lower()
        editable = (
            "textinput" in typ.lower()
            or "edittext" in typ.lower()
            or "search" in blob
            or str(a.get("focused") or "").lower() in ("true", "1")
        )
        if not editable:
            continue
        bounds = _parse_bounds(a.get("bounds"))
        if not bounds:
            continue
        x1, y1, x2, y2 = bounds
        if x2 - x1 < 20 or y2 - y1 < 16:
            continue
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if cy < 100:
            continue
        out.append((cx, cy, x1, y1, x2, y2, (t or d or typ)[:40]))
    return out


def _scrollable_hint(hierarchy: dict) -> bool:
    """True if tree looks like a list/feed worth scrolling."""
    n_list = 0
    for node in _walk_nodes(hierarchy or {}):
        typ = str(_attrs(node).get("type") or "")
        if typ in ("List", "ListItem", "Grid", "GridItem", "Scroll", "Scrollable"):
            n_list += 1
        if n_list >= 2:
            return True
    return n_list >= 1


_OVERLAY_BACK = (
    "play on",
    "this device",
    "not interested",
    "similar songs",
    "set as ringtone",
    "add to playlist",
    "view artist",
    "view album",
    "premium plus",
    "0元开通",
    "music membership",
)


_PERM_TAP_EXACT = {
    "允许", "Allow", "始终允许", "仅使用期间", "使用时允许",
    "仅在使用中允许", "While using the app", "Only this time",
    "Allow this time only", "Allow all the time", "本次允许",
    "同意", "Agree", "确定", "OK", "好的",
}


def _maybe_grant_permission(d: HMDevice, hierarchy: dict) -> dict:
    """Tap system permission Allow if present (location/camera walls stall Mode A)."""
    blob_bits = []
    candidates = []
    for node in _walk_nodes(hierarchy):
        a = _attrs(node)
        text = str(a.get("text") or "").strip()
        desc = str(a.get("description") or "").strip()
        label = text or desc
        if not label:
            continue
        blob_bits.append(label.lower())
        bounds = _parse_bounds(a.get("bounds"))
        if not bounds:
            continue
        if label in _PERM_TAP_EXACT or label.lower() in {x.lower() for x in _PERM_TAP_EXACT}:
            x1, y1, x2, y2 = bounds
            candidates.append(((x1 + x2) // 2, (y1 + y2) // 2, label))
    blob = " ".join(blob_bits)
    if not candidates:
        return hierarchy
    # only when dialog-ish wording present
    if not any(
        k in blob
        for k in (
            "location", "位置", "permission", "权限", "camera", "相机",
            "microphone", "麦克风", "photos", "相册", "storage", "存储",
            "notifications", "通知", "access your", "访问",
        )
    ):
        return hierarchy
    # prefer stronger allow over OK
    prefer = ("始终允许", "Allow all the time", "使用时允许", "While using the app",
              "允许", "Allow", "同意", "Agree")
    pick = None
    for pref in prefer:
        for c in candidates:
            if c[2] == pref or c[2].lower() == pref.lower():
                pick = c
                break
        if pick:
            break
    if not pick:
        pick = candidates[0]
    cx, cy, label = pick
    logger.info(f"[Harmony] permission grant tap {label!r} @({cx},{cy})")
    try:
        d._click_xy(cx, cy)
        time.sleep(0.8)
        return d.dump_hierarchy() or hierarchy
    except Exception as e:
        logger.debug(f"permission tap failed: {e}")
        return hierarchy


def _maybe_dismiss_overlay(d: HMDevice, hdc: HDCDevice, hierarchy: dict) -> dict:
    """One Back if cast/player sheet chrome dominates (Music Mode A trap)."""
    # permission dialogs first — Back would deny and strand apps (maps/外卖)
    hierarchy = _maybe_grant_permission(d, hierarchy)
    texts = []
    for node in _walk_nodes(hierarchy):
        t = str(_attrs(node).get("text") or "").strip().lower()
        if t:
            texts.append(t)
    blob = " | ".join(texts[:80])
    if any(k in blob for k in _OVERLAY_BACK):
        # Premium/membership sheets keep tab_text visible but block body switches
        hard = any(k in blob for k in ("premium plus", "0元开通", "music membership", "play on"))
        has_tab = any(
            str(_attrs(n).get("id") or "") == "tab_text" for n in _walk_nodes(hierarchy)
        )
        if hard or not has_tab:
            logger.info("[Harmony] overlay/sheet dismiss — keyEvent Back")
            try:
                hdc.shell("uitest uiInput keyEvent Back")
            except Exception:
                try:
                    d.go_back()
                except Exception:
                    pass
            time.sleep(0.2)
            try:
                return d.dump_hierarchy() or hierarchy
            except Exception:
                return hierarchy
    return hierarchy


class HarmonyExplorer:
    def __init__(
        self,
        driver: HMDevice,
        package_names: List[str],
        throttle_ms: int = 500,
    ):
        self.d = driver
        self.packages = package_names
        self.throttle = max(0, throttle_ms) / 1000.0
        self.hdc = HDCDevice()
        self.executed_prop = False
        self._steps = 0
        self._steps_log: Optional[Path] = None
        self._activity = (package_names[0] if package_names else "unknown")
        # weak-dump tarpit guards (article.video Mode B: relaunch loop burned minutes)
        self._weak_streak = 0
        self._relaunch_count = 0
        self._last_relaunch_ts = 0.0
        self._back_on_weak = 0
        # --- HMDroidbot/old-Kea inspired ---
        self._seen_states: Set[str] = set()
        self._seen_edges: Set[str] = set()  # "state|act|wid" capped
        self._state_hist: deque = deque(maxlen=12)
        self._same_state_streak = 0
        self._steps_outside = 0
        self._last_state = ""
        self._action_rng = random.Random()

    def start_apps(self):
        for pkg in self.packages:
            logger.info(f"Starting {pkg}")
            self.hdc.start_ability(pkg)

    def _sut_fg(self) -> bool:
        return any(self.hdc.is_package_foreground(p) for p in self.packages) if self.packages else True

    def _content_texts(self, h: dict) -> List[str]:
        """Visible labels: text preferred, else description (hybrid/icon chrome)."""
        out: List[str] = []
        for node in _walk_nodes(h or {}):
            a = _attrs(node)
            t = str(a.get("text") or "").strip()
            if not t:
                t = str(a.get("description") or "").strip()
            if not t or t.startswith("file://"):
                continue
            if _TIME_RE.match(t) or _BATTERY_RE.match(t):
                continue
            if t not in out:
                out.append(t)
        return out

    def _looks_launcherish(self, h: dict) -> bool:
        """True if dump is OS home/recents, not the SUT window."""
        if not self.packages:
            return False
        texts = self._content_texts(h)
        # App content visible even if aa-dump FG flickers false (login/privacy sheets).
        if self._looks_like_sut_content(texts):
            return False
        if not self._sut_fg():
            return True
        # Recent-apps strip often shows other app names while SUT is not really focused.
        # Generic home-screen chrome (was too app-specific → false relaunch thrash)
        launcher_markers = (
            "AppGallery", "Settings", "设置", "Books", "Wallet", "GameCenter",
            "Huawei Apps", "Theme Studio", "小艺建议", "Double-tap to activate",
            "Touch & hold the time",
        )
        hit = sum(1 for t in texts if any(m.lower() in t.lower() for m in launcher_markers))
        if hit >= 2 and len(texts) <= 14:
            return True
        # Very empty dump while claiming FG — often mid-transition
        if len(texts) <= 2:
            return True
        return False

    def _looks_like_sut_content(self, texts: List[str]) -> bool:
        """Hierarchy is clearly in-app, not launcher.

        is_package_foreground() false-negatives while dump still shows SUT UI
        (login sheets, video error pages). Prefer rich dump over FG API.
        """
        if len(texts) < 3:
            return False
        # Only OS-home unique chrome — NOT in-app Settings/Wallet (Kuaishou 我 page
        # has Settings+Wallet+AppGallery entry → was false-negative → relaunch thrash).
        launcher_only = (
            "Huawei Apps", "Theme Studio", "小艺建议", "Double-tap to activate",
            "Touch & hold the time", "Celia Suggestions", "Set up in Weather app",
        )
        lhit = sum(1 for t in texts if any(m.lower() in t.lower() for m in launcher_only))
        if lhit >= 2:
            return False
        # ponytail: rich non-launcher tree = SUT
        if len(texts) >= 6:
            return True
        markers = (
            "登录", "注册", "验证码", "隐私", "同意", "用户协议", "密码",
            "首页", "我的", "搜索", "推荐", "Allow", "Deny", "Get started",
            "Log in", "Sign in", "Continue", "Skip", "+86", "获取验证码",
            "加载失败", "刷新", "视频", "讨论", "播放", "追剧", "VIP",
            "精选", "热点", "消息", "Trending", "Kwai", "草稿", "Drafts",
        )
        hits = sum(1 for t in texts if any(m.lower() in t.lower() for m in markers))
        return hits >= 1 and len(texts) >= 4

    def dump_sut_hierarchy(self) -> dict:
        """Dump hierarchy while SUT is FOREGROUND; recover carefully if weak.

        Hard budget ~12s — unlock once. Relaunch is rate-limited (cooldown + cap).
        Empty dump while SUT still FG (hybrid/webview) → Back, NOT relaunch thrash
        (article.video Mode B burned running-minutes on force-start loops).
        """
        t0 = time.time()
        budget_s = 12.0
        last: dict = {}
        unlocked = False
        for attempt in range(2):  # hard cap 2 dumps
            if time.time() - t0 > budget_s:
                logger.warning("[Harmony] dump_sut budget exhausted; return last")
                break
            if attempt > 0:
                try:
                    self.d.setHierarchy(None)
                    self.d._bust_live()
                except Exception:
                    pass
            last = self.d.dump_hierarchy() or {}
            texts = self._content_texts(last)
            joined = " ".join(texts)
            for lab in (
                "暂不认证", "随便看看", "暂不登录", "游客进入", "跳过登录",
                "先逛逛", "先看看", "暂不切换", "Skip", "Close",
            ):
                if lab in joined:
                    try:
                        if self.d(text=lab).exists():
                            self.d(text=lab).click()
                            time.sleep(0.15)
                            last = self.d.dump_hierarchy() or {}
                            texts = self._content_texts(last)
                            joined = " ".join(texts)
                            break
                    except Exception:
                        pass
            fg = self._sut_fg()
            if self._looks_like_sut_content(texts) and not self._looks_launcherish(last):
                self._weak_streak = 0
                return last
            if fg and not self._looks_launcherish(last) and len(texts) >= 3:
                self._weak_streak = 0
                return last

            # Weak dump
            self._weak_streak += 1
            logger.warning(
                f"[Harmony] weak dump try={attempt} texts={len(texts)} "
                f"fg={fg} streak={self._weak_streak} sample={texts[:6]!r}"
            )

            # Case A: SUT still FG but dump empty/thin → hybrid blank / mid-transition.
            # Back out; do NOT relaunch (relaunch thrashes and burns the run).
            if fg and len(texts) <= 2:
                if self._back_on_weak < 3:
                    try:
                        self.hdc.shell("uitest uiInput keyEvent Back")
                        self._back_on_weak += 1
                        time.sleep(0.35)
                        last = self.d.dump_hierarchy() or {}
                        texts2 = self._content_texts(last)
                        if len(texts2) >= 3 or self._looks_like_sut_content(texts2):
                            self._weak_streak = 0
                            self._back_on_weak = 0
                            return last
                    except Exception:
                        pass
                # give stepMonkey something; skip relaunch
                break

            # Case B: not FG or launcher chrome → unlock once + rate-limited relaunch
            if not unlocked:
                try:
                    self.hdc.unlock()
                    unlocked = True
                except Exception:
                    pass
                time.sleep(0.2)
            now = time.time()
            # ponytail: max 3 relaunches/run, ≥12s apart — stops article.video tarpit
            if (
                self._relaunch_count < 3
                and (now - self._last_relaunch_ts) >= 12.0
                and attempt == 0
            ):
                logger.info(
                    f"[Harmony] relaunch SUT ({self._relaunch_count + 1}/3) after weak dump"
                )
                self.start_apps()
                self._relaunch_count += 1
                self._last_relaunch_ts = now
                self._back_on_weak = 0
                time.sleep(0.6)
                continue
            break
        return last or {}

    def dumpHierarchy(self) -> str:
        h = self.dump_sut_hierarchy()
        return json.dumps(h, ensure_ascii=False)

    def dump_for_props(self) -> str:
        """Hierarchy for precondition check — no explore tap."""
        return self.dumpHierarchy()

    def _ensure_steps_log(self):
        if self._steps_log is not None:
            return
        sm = StampManager()
        if not sm.output_dir or not sm.stamp:
            return
        out = Path(sm.output_dir) / f"output_{sm.stamp}"
        out.mkdir(parents=True, exist_ok=True)
        self._steps_log = out / "steps.log"
        # stub coverage.log so widget_coverage/HTML report don't require Fastbot
        cov = out / "coverage.log"
        if not cov.exists():
            act = self._activity
            cov.write_text(
                json.dumps(
                    {
                        "stepsCount": 0,
                        "coverage": 0.0,
                        "totalActivitiesCount": 1,
                        "testedActivitiesCount": 1,
                        "totalActivities": [act],
                        "testedActivities": [act],
                        "activityCountHistory": {act: 1},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

    def _append_step(self, record: dict):
        self._ensure_steps_log()
        if self._steps_log is None:
            return
        record.setdefault("Time", datetime.now().isoformat(timespec="milliseconds"))
        record.setdefault("MonkeyStepsCount", self._steps)
        record.setdefault("Screenshot", "")
        record.setdefault("Activity", self._activity)
        with open(self._steps_log, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_monkey(
        self,
        act: str,
        pos: List[int],
        label: str = "",
        typ: str = "",
    ):
        widget = json.dumps(
            {
                "class": typ or "node",
                "resource-id": "",
                "content-desc": label,
            },
            ensure_ascii=False,
        )
        info = json.dumps(
            {"act": act, "pos": pos, "widget": widget},
            ensure_ascii=False,
        )
        self._append_step({"Type": "Monkey", "Info": info})

    def log_script_info(
        self,
        prop_name: str,
        state: str,
        kind: str = "property",
        steps: Optional[int] = None,
    ):
        if steps is not None:
            self._steps = steps
        self._append_step(
            {
                "Type": "ScriptInfo",
                "Info": {
                    "propName": prop_name,
                    "state": state,
                    "kind": kind,
                },
            }
        )

    def _widget_id(self, label: str, typ: str, x1: int, y1: int) -> str:
        return f"{typ}:{label[:24]}@{x1 // 40}x{y1 // 40}"

    def _remember_edge(self, state: str, act: str, wid: str) -> None:
        if len(self._seen_edges) >= _UTG_EDGE_CAP:
            return
        self._seen_edges.add(f"{state}|{act}|{wid}")

    def _boost_unseen(self, state: str, cands: List[Tuple]) -> List[Tuple]:
        """UTG: up-weight widgets whose edge from this state is new."""
        if not cands:
            return cands
        out = []
        for c in cands:
            cx, cy, x1, y1, x2, y2, label, typ, w = c[:9]
            wid = self._widget_id(label, typ, x1, y1)
            edge = f"{state}|CLICK|{wid}"
            ww = int(w)
            if edge not in self._seen_edges:
                ww += 5
            out.append((cx, cy, x1, y1, x2, y2, label, typ, max(1, ww)))
        return out

    def _update_state_track(self, h: dict) -> str:
        st = _state_hash(h)
        self._seen_states.add(st)
        if st == self._last_state:
            self._same_state_streak += 1
        else:
            self._same_state_streak = 0
            self._last_state = st
        self._state_hist.append(st)
        return st

    def _do_scroll(self, direction: str = "up") -> None:
        # screen mid; up = finger moves up = content down (feed)
        if direction == "up":
            x1, y1, x2, y2 = 540, 1900, 540, 700
        elif direction == "down":
            x1, y1, x2, y2 = 540, 700, 540, 1900
        elif direction == "left":
            x1, y1, x2, y2 = 1000, 1400, 200, 1400
        else:
            x1, y1, x2, y2 = 200, 1400, 1000, 1400
        try:
            self.d.swipe(x1, y1, x2, y2, speed=350)
        except Exception:
            try:
                self.hdc.shell(f"uitest uiInput swipe {x1} {y1} {x2} {y2} 300")
            except Exception as e:
                logger.debug(f"scroll failed: {e}")
        self.log_monkey("SCROLL", [x1, y1, x2, y2], label=f"scroll_{direction}", typ="swipe")

    def _do_back(self) -> None:
        try:
            self.hdc.shell("uitest uiInput keyEvent Back")
        except Exception:
            try:
                self.d.go_back()
            except Exception:
                pass
        self.log_monkey("BACK", [0, 0, 0, 0], label="back", typ="key")

    def _do_long_press(self, cx: int, cy: int, x1: int, y1: int, x2: int, y2: int, label: str) -> None:
        try:
            self.hdc.shell(f"uitest uiInput longClick {cx} {cy}")
        except Exception as e:
            logger.debug(f"longClick failed: {e}; fallback tap")
            try:
                self.d._click_xy(cx, cy)
            except Exception:
                pass
        self.log_monkey("LONG_CLICK", [x1, y1, x2, y2], label=label, typ="long")

    def _do_set_text(self, cx: int, cy: int, x1: int, y1: int, x2: int, y2: int, label: str) -> None:
        sample = random.choice(("test", "a", "12", "搜索", "kea"))
        try:
            # focus then inputText via hdc (hmdriver set_text needs selector)
            self.d._click_xy(cx, cy)
            time.sleep(0.15)
            quoted = json.dumps(sample, ensure_ascii=False)
            self.hdc.shell(f"uitest uiInput inputText {cx} {cy} {quoted}")
        except Exception as e:
            logger.debug(f"setText failed: {e}")
        self.log_monkey("SET_TEXT", [x1, y1, x2, y2], label=f"{label}:{sample}", typ="input")

    def _pick_action(self, h: dict, state: str, cands: List[Tuple], edits: List[Tuple]) -> str:
        """Choose action kind — random with tarpit bias (old Kea RandomPolicy mix)."""
        # outside app: handled by caller
        if self._same_state_streak >= _TARPIT_STREAK:
            # tarpit escape: scroll or back, not another same tap
            return random.choice(("SCROLL", "SCROLL", "BACK"))
        r = self._action_rng.random()
        if edits and r < 0.08:
            return "SET_TEXT"
        if cands and r < 0.10:
            return "LONG_CLICK"
        if (_scrollable_hint(h) and r < 0.28) or (not cands and r < 0.7):
            return "SCROLL"
        if r < 0.06:
            return "BACK"
        if cands:
            return "CLICK"
        return "SCROLL"

    def stepMonkey(self, _info: Optional[dict] = None) -> str:
        """One exploration step (multi-action + light UTG); return hierarchy JSON."""
        self._steps += 1
        try:
            h = self.dump_sut_hierarchy()
        except Exception as e:
            logger.warning(f"dump_sut_hierarchy failed: {e}; retry once")
            time.sleep(0.4)  # B8
            try:
                h = self.dump_sut_hierarchy()
            except Exception as e2:
                logger.error(f"dump_sut_hierarchy retry failed: {e2}")
                return "{}"
        h = _maybe_dismiss_overlay(self.d, self.hdc, h)

        # FG outside tracking (old Kea MAX_NUM_STEPS_OUTSIDE)
        if self.packages and not self._sut_fg() and not self._looks_like_sut_content(
            self._content_texts(h)
        ):
            self._steps_outside += 1
            if self._steps_outside >= _MAX_STEPS_OUTSIDE:
                logger.info(
                    f"[Harmony] outside FG {self._steps_outside} steps — relaunch SUT"
                )
                try:
                    self.start_apps()
                    time.sleep(0.5)
                    h = self.dump_sut_hierarchy()
                except Exception as e:
                    logger.debug(f"relaunch outside failed: {e}")
                self._steps_outside = 0
        else:
            self._steps_outside = 0

        # Weather/city picker etc.: no bottom tabs, has search/popular cities → Back
        try:
            texts_l = [x.lower() for x in self._content_texts(h)]
            blob = " ".join(texts_l)
            has_tab = any(
                str(_attrs(n).get("id") or "") == "tab_text" for n in _walk_nodes(h)
            )
            if (not has_tab) and any(
                k in blob
                for k in (
                    "popular cities",
                    "search for a city",
                    "search city",
                    "manage cities",
                    "select a city",
                )
            ):
                logger.info("[Harmony] city-picker/subpage without tabs — Back")
                self._do_back()
                time.sleep(0.2)
                h = self.dump_sut_hierarchy()
        except Exception:
            pass
        # Escape broken H5 error pages (Maps Discover rankings trap)
        texts = " ".join(self._content_texts(h)).lower()
        if "loading error" in texts or ("retry" in texts and "h5" in texts):
            logger.info("[Harmony] H5 load-error surface — keyEvent Back")
            self._do_back()
            time.sleep(0.25)
            h = self.dump_sut_hierarchy()

        state = self._update_state_track(h)
        cands = self._boost_unseen(state, _clickable_candidates(h))
        edits = _editable_candidates(h)
        act = self._pick_action(h, state, cands, edits)

        prev = None
        try:
            prev = self.d._hierarchy_fingerprint()
        except Exception:
            pass

        if act == "BACK":
            logger.info(f"Harmony explore BACK (tarpit={self._same_state_streak})")
            self._do_back()
            self._remember_edge(state, "BACK", "key")
        elif act == "SCROLL":
            direction = random.choice(("up", "up", "up", "down", "left", "right"))
            logger.info(
                f"Harmony explore SCROLL {direction} (tarpit={self._same_state_streak})"
            )
            self._do_scroll(direction)
            self._remember_edge(state, f"SCROLL_{direction}", "screen")
        elif act == "SET_TEXT" and edits:
            cx, cy, x1, y1, x2, y2, label = random.choice(edits)
            logger.info(f"Harmony explore SET_TEXT ({cx},{cy}) {label!r}")
            self._do_set_text(cx, cy, x1, y1, x2, y2, label)
            self._remember_edge(state, "SET_TEXT", self._widget_id(label, "input", x1, y1))
        elif act == "LONG_CLICK" and cands:
            pick = _weighted_choice(cands)
            cx, cy, x1, y1, x2, y2, label, typ = pick[:8]
            logger.info(f"Harmony explore LONG_CLICK ({cx},{cy}) {label!r}")
            self._do_long_press(cx, cy, x1, y1, x2, y2, label)
            self._remember_edge(state, "LONG_CLICK", self._widget_id(label, typ, x1, y1))
        elif cands:
            pick = _weighted_choice(cands)
            cx, cy, x1, y1, x2, y2, label, typ = pick[:8]
            logger.info(f"Harmony explore tap ({cx},{cy}) {label!r} w={pick[-1]}")
            try:
                self.d._click_xy(cx, cy)
            except Exception as e:
                logger.warning(f"tap failed: {e}")
            self.log_monkey("CLICK", [x1, y1, x2, y2], label=label, typ=typ)
            self._remember_edge(state, "CLICK", self._widget_id(label, typ, x1, y1))
        else:
            # empty candidates: Back if weak/empty tree, else swipe
            texts0 = self._content_texts(h)
            if len(texts0) <= 2 and self._sut_fg() and self._back_on_weak < 4:
                logger.info("Harmony explore Back fallback (empty tree)")
                self._do_back()
                self._back_on_weak += 1
            else:
                logger.info("Harmony explore swipe fallback")
                self._do_scroll("up")

        try:
            self.d._settle_after_action(prev_fp=prev, timeout=max(0.5, self.throttle or 0.5))
        except Exception:
            if self.throttle:
                time.sleep(self.throttle)

        # Taps can drop SUT; re-grab before precond dump.
        # If already in weak-dump streak, cheap dump only (no relaunch thrash).
        try:
            if self._weak_streak >= 2:
                try:
                    self.d.setHierarchy(None)
                except Exception:
                    pass
                h2 = self.d.dump_hierarchy() or {}
                texts2 = self._content_texts(h2)
                if len(texts2) < 3 and self._sut_fg() and self._back_on_weak < 4:
                    try:
                        self._do_back()
                        self._back_on_weak += 1
                        time.sleep(0.3)
                        h2 = self.d.dump_hierarchy() or {}
                    except Exception:
                        pass
                if len(self._content_texts(h2)) < 3:
                    try:
                        self._do_scroll("up")
                        time.sleep(0.25)
                        h2 = self.d.dump_hierarchy() or h2
                    except Exception:
                        pass
            else:
                h2 = self.dump_sut_hierarchy()
            h2 = _maybe_dismiss_overlay(self.d, self.hdc, h2)
            if self._looks_like_sut_content(self._content_texts(h2)):
                self._weak_streak = 0
                self._back_on_weak = 0
            # update UTG with post state (node only; edge already recorded)
            try:
                self._seen_states.add(_state_hash(h2))
            except Exception:
                pass
            return json.dumps(h2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"post-step dump failed: {e}")
            return json.dumps(h or {}, ensure_ascii=False)

    def stopMonkey(self):
        logger.info("HarmonyExplorer stop")

    def join(self):
        pass

    def get_return_code(self) -> int:
        return 0

    def check_alive(self):
        return True

    def init(self, options=None, stamp=None):
        self._ensure_steps_log()
        self.start_apps()

    def logScript(self, *_args, **_kwargs):
        pass

    @property
    def device_output_dir(self) -> str:
        self._ensure_steps_log()
        if self._steps_log is not None:
            return str(self._steps_log.parent)
        return "/data/local/tmp/.kea2"


if __name__ == "__main__":
    # ponytail: self-check blacklist without device
    fake = {
        "attributes": {"bounds": "[0,0][1280,2832]", "type": "root"},
        "children": [
            {
                "attributes": {
                    "bounds": "[100,40][200,90]",
                    "text": "83",
                    "type": "Text",
                    "clickable": "true",
                }
            },
            {
                "attributes": {
                    "bounds": "[100,200][400,300]",
                    "text": "首页",
                    "type": "Text",
                    "clickable": "true",
                }
            },
            {
                "attributes": {
                    "bounds": "[500,2500][700,2700]",
                    "description": "metaballNode",
                    "type": "Stack",
                    "clickable": "true",
                }
            },
            {
                "attributes": {
                    "bounds": "[200,400][500,500]",
                    "text": "路线",
                    "type": "Button",
                    "clickable": "true",
                }
            },
        ],
    }
    cands = _clickable_candidates(fake)
    labels = [c[6] for c in cands]
    assert "首页" in labels and "路线" in labels, labels
    assert "83" not in labels and "metaballNode" not in labels, labels
    # tab-like bottom should outrank noise if weighted
    fake2 = {
        "attributes": {"bounds": "[0,0][1280,2832]", "type": "root"},
        "children": [
            {
                "attributes": {
                    "bounds": "[100,2600][300,2750]",
                    "text": "Home",
                    "id": "tab_text",
                    "type": "Text",
                    "clickable": "true",
                }
            },
            {
                "attributes": {
                    "bounds": "[400,2550][700,2700]",
                    "text": "Some Artist",
                    "type": "Text",
                    "clickable": "true",
                }
            },
        ],
    }
    c2 = _clickable_candidates(fake2)
    by_label = {c[6]: c[-1] for c in c2}
    assert by_label.get("Home", 0) > by_label.get("Some Artist", 0), by_label
    # UTG helpers
    h1 = _state_hash(fake)
    h2 = _state_hash(fake)
    assert h1 == h2 and len(h1) == 12, h1
    fake_edit = {
        "attributes": {"bounds": "[0,0][1280,2832]", "type": "root"},
        "children": [
            {
                "attributes": {
                    "bounds": "[100,300][600,380]",
                    "type": "TextInput",
                    "text": "Search",
                    "clickable": "true",
                }
            },
            {
                "attributes": {
                    "bounds": "[0,400][1280,2000]",
                    "type": "List",
                    "clickable": "false",
                },
                "children": [
                    {
                        "attributes": {
                            "bounds": "[0,400][1280,500]",
                            "type": "ListItem",
                            "text": "row",
                            "clickable": "true",
                        }
                    }
                ],
            },
        ],
    }
    assert _editable_candidates(fake_edit), "editable miss"
    assert _scrollable_hint(fake_edit), "scroll hint miss"
    # boost unseen edges
    ex = HarmonyExplorer.__new__(HarmonyExplorer)
    ex._seen_edges = set()
    cands = _clickable_candidates(fake)
    boosted = ex._boost_unseen("abc", cands)  # type: ignore[attr-defined]
    assert all(b[-1] >= c[-1] for b, c in zip(boosted, cands))
    print("ok", labels, "weights", by_label, "state", h1)
