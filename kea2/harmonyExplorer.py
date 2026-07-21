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
    return False


def _clickable_candidates(hierarchy: dict) -> List[Tuple[int, int, int, int, int, int, str, str]]:
    """Return (cx, cy, x1, y1, x2, y2, label, typ) for plausible taps."""
    out: List[Tuple[int, int, int, int, int, int, str, str]] = []
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
        out.append((cx, cy, x1, y1, x2, y2, label, typ))
    return out


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
        """Dump hierarchy while SUT is FOREGROUND; relaunch if dump is launcherish."""
        last: dict = {}
        for attempt in range(4):
            if not self._sut_fg():
                logger.info(f"[Harmony] SUT not FOREGROUND (try {attempt}); start_apps")
                self.start_apps()
                time.sleep(2.0)
            last = self.d.dump_hierarchy() or {}
            texts = self._content_texts(last)
            if self._sut_fg() and not self._looks_launcherish(last):
                return last
            logger.warning(
                f"[Harmony] weak/launcher hierarchy try={attempt} "
                f"fg={self._sut_fg()} texts={len(texts)} sample={texts[:8]!r}; relaunch"
            )
            self.start_apps()
            time.sleep(2.0)
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
        cands = _clickable_candidates(h)
        if cands:
            cx, cy, x1, y1, x2, y2, label, typ = random.choice(cands)
            logger.info(f"Harmony explore tap ({cx},{cy}) {label!r}")
            try:
                self.d._click_xy(cx, cy)
            except Exception as e:
                logger.warning(f"tap failed: {e}")
            self.log_monkey("CLICK", [x1, y1, x2, y2], label=label, typ=typ)
        else:
            logger.info("Harmony explore swipe fallback")
            self.hdc.shell("uitest uiInput swipe 540 1800 540 600 300")
            self.log_monkey("SCROLL", [540, 1800, 540, 600], label="swipe", typ="swipe")
        if self.throttle:
            time.sleep(self.throttle)
        # Taps (esp. after hmdriver reconnect) can drop SUT; re-grab before precond dump.
        h2 = self.dump_sut_hierarchy()
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
    labels = [c[6] for c in _clickable_candidates(fake)]
    assert "首页" in labels and "路线" in labels, labels
    assert "83" not in labels and "metaballNode" not in labels, labels
    print("ok", labels)
