"""
Lightweight random UI explorer for HarmonyOS (Feature 1 substitute).

Kea2 Android uses Fastbot; there is no Fastbot for HarmonyOS NEXT.
This explorer dumps hierarchy via hmdriver2 and taps random on-screen widgets,
returning hierarchy JSON for precondition checks (Feature 3).
"""
from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from .hmDriver import HMDevice, _attrs, _parse_bounds, _walk_nodes
from .hdcUtils import HDCDevice
from .utils import getLogger

logger = getLogger(__name__)


def _clickable_candidates(hierarchy: dict) -> List[Tuple[int, int, str]]:
    """Return list of (x, y, label) centers for plausible taps."""
    out: List[Tuple[int, int, str]] = []
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
        )
        if not interesting:
            continue
        if not (text or desc or clickable or typ in ("Button", "SymbolGlyph")):
            continue
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        label = text or desc or typ or "node"
        out.append((cx, cy, label[:40]))
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

    def start_apps(self):
        for pkg in self.packages:
            logger.info(f"Starting {pkg}")
            self.hdc.start_ability(pkg)

    def dumpHierarchy(self) -> str:
        h = self.d.dump_hierarchy()
        return json.dumps(h, ensure_ascii=False)

    def stepMonkey(self, _info: Optional[dict] = None) -> str:
        """One random exploration step; return hierarchy JSON string."""
        self._steps += 1
        h = self.d.dump_hierarchy()
        cands = _clickable_candidates(h)
        if cands:
            x, y, label = random.choice(cands)
            logger.info(f"Harmony explore tap ({x},{y}) {label!r}")
            try:
                self.d._click_xy(x, y)
            except Exception as e:
                logger.warning(f"tap failed: {e}")
        else:
            # swipe fallback
            logger.info("Harmony explore swipe fallback")
            self.hdc.shell("uitest uiInput swipe 540 1800 540 600 300")
        if self.throttle:
            time.sleep(self.throttle)
        h2 = self.d.dump_hierarchy()
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
        self.start_apps()

    def logScript(self, *_args, **_kwargs):
        pass

    @property
    def device_output_dir(self) -> str:
        return "/data/local/tmp/.kea2"
