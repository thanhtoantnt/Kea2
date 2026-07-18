"""
HarmonyOS UI driver for Kea2 properties (Feature 2/3).

Uses hmdriver2 (Hypium/uitest) instead of uiautomator2.
API surface mirrors what scripts use: self.d(text=...).click()/exists(), go_back, app_stop.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .utils import getLogger

logger = getLogger(__name__)


def _walk_nodes(root: Any):
    if not isinstance(root, dict):
        return
    yield root
    for c in root.get("children") or []:
        yield from _walk_nodes(c)


def _attrs(node: dict) -> dict:
    a = node.get("attributes")
    if isinstance(a, dict):
        return a
    return node if isinstance(node, dict) else {}


def _match_node(node: dict, selectors: dict) -> bool:
    a = _attrs(node)
    for k, v in selectors.items():
        if v is None:
            continue
        # map common aliases
        key = k
        if k == "resourceId":
            key = "id"
        if k == "description":
            key = "description"
        if k == "className":
            key = "type"
        actual = a.get(key)
        if actual is None and key == "id":
            actual = a.get("id")
        if str(actual) != str(v):
            return False
    return True


def _parse_bounds(raw) -> Optional[List[int]]:
    """Harmony bounds: '[x1,y1][x2,y2]' or list."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        return [int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])]
    s = str(raw)
    import re
    nums = re.findall(r"-?\d+", s)
    if len(nums) >= 4:
        return [int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])]
    return None


class HMUiObject:
    def __init__(self, driver: "HMDevice", selectors: dict):
        self.driver = driver
        self.selectors = selectors

    def exists(self, timeout: float = 0) -> bool:
        # Static hierarchy (precondition checker) OR live hmdriver2.
        deadline = time.time() + max(0, float(timeout or 0))
        while True:
            if self.driver._hierarchy is not None:
                if self.driver._find_first(self.selectors) is not None:
                    return True
            else:
                try:
                    if self.driver._live_obj(self.selectors).exists():
                        return True
                except Exception:
                    pass
            if time.time() >= deadline:
                return False
            time.sleep(0.2)

    def click(self):
        # Prefer live click for property bodies; static path only if hierarchy set.
        if self.driver._hierarchy is None:
            return self.driver._live_click(self.selectors)
        node = self.driver._find_first(self.selectors)
        if node is None:
            return self.driver._live_click(self.selectors)
        bounds = _parse_bounds(_attrs(node).get("bounds"))
        if bounds:
            x = (bounds[0] + bounds[2]) // 2
            y = (bounds[1] + bounds[3]) // 2
            return self.driver._click_xy(x, y)
        return self.driver._live_click(self.selectors)

    def set_text(self, text: str):
        return self.driver._live_set_text(self.selectors, text)

    def get_text(self) -> str:
        node = self.driver._find_first(self.selectors)
        if node is not None:
            text = str(_attrs(node).get("text") or "")
            if text:
                return text
        # Static text empty (e.g. a TextInput whose live value is not in the
        # dumped `text` attr) → fall through to a live query so rules can assert
        # on the actual displayed value instead of being forced to structural
        # oracles. Without this, get_text() on a live TextInput returned '' even
        # though hmdriver2's live .info['text'] shows the value.
        return self.driver._live_get_text(self.selectors) or ""

    @property
    def info(self) -> dict:
        node = self.driver._find_first(self.selectors)
        if node is not None:
            return dict(_attrs(node))
        return {}


class HMDevice:
    """Live + optional static hierarchy for precondition checks."""

    def __init__(self, serial: str):
        self.serial = serial
        self._hm = None
        self._hierarchy: Optional[dict] = None  # static snapshot for precond
        self._connect()

    def _connect(self):
        try:
            from hmdriver2.driver import Driver
        except ImportError as e:
            raise ImportError(
                "hmdriver2 is required for HarmonyOS Kea2. "
                "Install: pip install hmdriver2 (and working hdc + uitest agent)."
            ) from e
        logger.info(f"Connecting hmdriver2 to {self.serial} …")
        self._hm = Driver(self.serial)
        time.sleep(1)

    def setHierarchy(self, hierarchy: Any):
        if hierarchy is None:
            self._hierarchy = None
            return
        if isinstance(hierarchy, str):
            try:
                self._hierarchy = json.loads(hierarchy)
            except json.JSONDecodeError:
                self._hierarchy = None
        elif isinstance(hierarchy, dict):
            self._hierarchy = hierarchy
        else:
            self._hierarchy = None

    def dump_hierarchy(self) -> dict:
        h = self._hm.dump_hierarchy()
        if isinstance(h, str):
            try:
                h = json.loads(h)
            except json.JSONDecodeError:
                h = {}
        self._hierarchy = h if isinstance(h, dict) else {}
        return self._hierarchy

    def __call__(self, **kwargs) -> HMUiObject:
        return HMUiObject(self, kwargs)

    def click(self, x: int, y: int):
        # Coordinate tap — parity with the Android u2 driver (d.click(x,y)). Harmony
        # apps often have icon-only buttons (e.g. Calendar's '+') with no unique
        # text/description/type selector, so a property can only self-drive them by
        # the coordinates from a live dump. Without this, such targets are reachable
        # only when the random explorer happens to tap them.
        return self._click_xy(x, y)

    def _find_first(self, selectors: dict) -> Optional[dict]:
        root = self._hierarchy
        if root is None:
            return None
        for node in _walk_nodes(root):
            if _match_node(node, selectors):
                return node
        return None

    def _live_obj(self, selectors: dict):
        # hmdriver2 uses same keyword style: text=, id=, description=, type=
        kw = {}
        for k, v in selectors.items():
            if k == "resourceId":
                kw["id"] = v
            elif k == "className":
                kw["type"] = v
            else:
                kw[k] = v
        return self._hm(**kw)

    def _live_click(self, selectors: dict):
        obj = self._live_obj(selectors)
        return obj.click()

    def _live_set_text(self, selectors: dict, text: str):
        obj = self._live_obj(selectors)
        # hmdriver2 input
        if hasattr(obj, "input_text"):
            return obj.input_text(text)
        if hasattr(obj, "set_text"):
            return obj.set_text(text)
        raise AttributeError("hmdriver2 object has no input_text/set_text")

    def _live_get_text(self, selectors: dict) -> str:
        obj = self._live_obj(selectors)
        try:
            # hmdriver2 .info is an ElementInfo dataclass, not a dict — use the
            # .text property directly (calls Component.getText), which returns
            # the live value even for TextInput whose static `text` attr is ''.
            return str(obj.text or "")
        except Exception:
            return ""

    def _click_xy(self, x: int, y: int):
        # prefer driver click coordinate
        if hasattr(self._hm, "click"):
            try:
                return self._hm.click(x, y)
            except TypeError:
                pass
        from .hdcUtils import HDCDevice
        HDCDevice().shell(f"uitest uiInput click {x} {y}")

    def go_back(self):
        if hasattr(self._hm, "go_back"):
            return self._hm.go_back()
        if hasattr(self._hm, "press_back"):
            return self._hm.press_back()
        from .hdcUtils import HDCDevice
        HDCDevice().shell("uitest uiInput keyEvent Back")

    def app_stop(self, package: str):
        from .hdcUtils import HDCDevice
        HDCDevice().force_stop(package)

    def app_start(self, package: str, activity: Optional[str] = None):
        from .hdcUtils import HDCDevice
        ability = activity or "EntryAbility"
        HDCDevice().start_ability(package, ability)

    def xpath(self, *args, **kwargs):
        raise NotImplementedError("xpath is Android/u2-only; use d(text=...)/d(id=...) on HarmonyOS")


class HMDriver:
    """Factory parallel to U2Driver."""

    scriptDriver: Optional[HMDevice] = None
    serial: Optional[str] = None

    @classmethod
    def setDevice(cls, serial: Optional[str]):
        cls.serial = serial

    @classmethod
    def getScriptDriver(cls, mode: str = "proxy") -> HMDevice:
        if cls.scriptDriver is None:
            if not cls.serial:
                from .hdcUtils import HDCDevice
                HDCDevice.setDevice(cls.serial)
                cls.serial = HDCDevice().serial
            cls.scriptDriver = HMDevice(cls.serial)
        return cls.scriptDriver

    @classmethod
    def getStaticChecker(cls, hierarchy=None) -> HMDevice:
        d = cls.getScriptDriver()
        d.setHierarchy(hierarchy)
        return d

    @classmethod
    def tearDown(cls):
        cls.scriptDriver = None
