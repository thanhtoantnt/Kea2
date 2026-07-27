"""
Lightweight random UI explorer for HarmonyOS (Feature 1 substitute).

Kea2 Android uses Fastbot; there is no Fastbot for HarmonyOS NEXT.
This explorer dumps hierarchy via hmdriver2 and taps random on-screen widgets,
returning hierarchy JSON for precondition checks (Feature 3).

Also writes a Fastbot-compatible steps.log so HTML bug reports can load.
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .hmDriver import HMDevice, _attrs, _parse_bounds, _walk_nodes
from .hdcUtils import HDCDevice
from .utils import StampManager, getLogger

logger = getLogger(__name__)

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


def _maybe_dismiss_overlay(d: HMDevice, hdc: HDCDevice, hierarchy: dict) -> dict:
    """One Back if cast/player sheet chrome dominates (Music Mode A trap)."""
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
            time.sleep(0.5)
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

    def start_apps(self):
        for pkg in self.packages:
            logger.info(f"Starting {pkg}")
            self.hdc.start_ability(pkg)

    def _sut_fg(self) -> bool:
        return any(self.hdc.is_package_foreground(p) for p in self.packages) if self.packages else True

    def _content_texts(self, h: dict) -> List[str]:
        out: List[str] = []
        for node in _walk_nodes(h or {}):
            t = str(_attrs(node).get("text") or "").strip()
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
        if not self._sut_fg():
            return True
        texts = self._content_texts(h)
        # Recent-apps strip often shows other app names while SUT is not really focused.
        launcher_markers = ("美柚", "通信工程师考试", "AppGallery", "设置", "Settings", "Books", "Wallet")
        hit = sum(1 for t in texts if t in launcher_markers)
        if hit >= 2 and len(texts) <= 12:
            return True
        # Very empty dump while claiming FG — often mid-transition
        if len(texts) <= 2:
            return True
        return False

    def dump_sut_hierarchy(self) -> dict:
        """Dump hierarchy while SUT is FOREGROUND; relaunch if dump is launcherish.

        Browser/hybrid late paint: empty dump while FG is normal for a few seconds —
        poll before force-relaunch (relaunch thrash burned whole running-minutes).
        """
        last: dict = {}
        for attempt in range(6):
            if not self._sut_fg():
                logger.info(f"[Harmony] SUT not FOREGROUND (try {attempt}); start_apps")
                self.start_apps()
                time.sleep(2.0)
            last = self.d.dump_hierarchy() or {}
            texts = self._content_texts(last)
            if self._sut_fg() and not self._looks_launcherish(last):
                return last
            # Empty / tiny dump while still FG: wait and re-dump (no relaunch yet).
            if self._sut_fg() and len(texts) <= 2 and attempt < 5:
                logger.warning(
                    f"[Harmony] empty FG dump try={attempt} texts={len(texts)}; wait-paint"
                )
                time.sleep(2.0)
                continue
            logger.warning(
                f"[Harmony] weak/launcher hierarchy try={attempt} "
                f"fg={self._sut_fg()} texts={len(texts)} sample={texts[:8]!r}; relaunch"
            )
            self.start_apps()
            time.sleep(2.5)
        return last or self.d.dump_hierarchy() or {}

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

    def stepMonkey(self, _info: Optional[dict] = None) -> str:
        """One random exploration step; return hierarchy JSON string (SUT FG)."""
        self._steps += 1
        h = self.dump_sut_hierarchy()
        h = _maybe_dismiss_overlay(self.d, self.hdc, h)
        # Weather/city picker etc.: no bottom tabs, has search/popular cities → Back to home chrome
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
                self.hdc.shell("uitest uiInput keyEvent Back")
                time.sleep(0.5)
                h = self.dump_sut_hierarchy()
        except Exception:
            pass
        # Escape broken H5 error pages (Maps Discover rankings trap)
        texts = " ".join(self._content_texts(h)).lower()
        if "loading error" in texts or ("retry" in texts and "h5" in texts):
            logger.info("[Harmony] H5 load-error surface — keyEvent Back")
            try:
                self.hdc.shell("uitest uiInput keyEvent Back")
            except Exception:
                pass
            time.sleep(0.6)
            h = self.dump_sut_hierarchy()
        cands = _clickable_candidates(h)
        if cands:
            pick = _weighted_choice(cands)
            cx, cy, x1, y1, x2, y2, label, typ = pick[:8]
            logger.info(f"Harmony explore tap ({cx},{cy}) {label!r} w={pick[-1]}")
            prev = None
            try:
                prev = self.d._hierarchy_fingerprint()
            except Exception:
                pass
            try:
                self.d._click_xy(cx, cy)
            except Exception as e:
                logger.warning(f"tap failed: {e}")
            try:
                self.d._settle_after_action(prev_fp=prev, timeout=max(0.5, self.throttle or 0.5))
            except Exception:
                if self.throttle:
                    time.sleep(self.throttle)
            self.log_monkey("CLICK", [x1, y1, x2, y2], label=label, typ=typ)
        else:
            logger.info("Harmony explore swipe fallback")
            self.hdc.shell("uitest uiInput swipe 540 1800 540 600 300")
            self.log_monkey("SCROLL", [540, 1800, 540, 600], label="swipe", typ="swipe")
            if self.throttle:
                time.sleep(self.throttle)
        # Taps (esp. after hmdriver reconnect) can drop SUT; re-grab before precond dump.
        h2 = self.dump_sut_hierarchy()
        h2 = _maybe_dismiss_overlay(self.d, self.hdc, h2)
        return json.dumps(h2, ensure_ascii=False)

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
    print("ok", labels, "weights", by_label)
