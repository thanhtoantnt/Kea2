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
        # substring match (multiline tab labels: "部门\n第 1 个标签…")
        if k in ("textContains", "textMatches"):
            # ponytail: textMatches treated as contains; full regex if needed later
            if str(v) not in str(a.get("text") or ""):
                return False
            continue
        if k in ("descriptionContains", "descContains"):
            if str(v) not in str(a.get("description") or ""):
                return False
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
        # Prefer in-memory hierarchy match. Live hmdriver2 .exists() retries for
        # seconds per miss — kills setUpClass dismiss loops and precond scans.
        # timeout==0 → one dump + match, no live retry storm.
        if self.driver._hierarchy is not None:
            return self.driver._find_first(self.selectors) is not None
        timeout = max(0.0, float(timeout or 0))
        if timeout == 0:
            try:
                self.driver.dump_hierarchy()
                return self.driver._find_first(self.selectors) is not None
            except Exception:
                return False
        deadline = time.time() + timeout
        while True:
            try:
                self.driver.dump_hierarchy()
                if self.driver._find_first(self.selectors) is not None:
                    return True
            except Exception:
                pass
            if time.time() >= deadline:
                return False
            time.sleep(0.2)

    def click(self):
        # Bounds-first live click + post-click settle. Multi-click nav races
        # (music Me roundtrip, maps POI close) were ElementNotFound between
        # precond dump and hmdriver2 selector resolve — or next click too soon.
        r = self.driver._live_click(self.selectors, retries=3)
        time.sleep(0.35)  # ponytail: global settle; per-prop sleep if still flaky
        return r

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
        # uitest sometimes returns empty/invalid JSON mid-transition (quark blank,
        # app switch). Retry before treating as empty tree.
        h: dict = {}
        for attempt in range(3):
            raw = self._hm.dump_hierarchy()
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    raw = {}
            h = raw if isinstance(raw, dict) else {}
            if h and (h.get("children") or h.get("attributes")):
                break
            logger.warning(f"empty hierarchy dump try={attempt}; retry")
            time.sleep(0.45)
        self._hierarchy = h
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
        # textContains is hierarchy-only — resolve to exact text via dump first.
        kw = {}
        for k, v in selectors.items():
            if k in ("textContains", "textMatches", "descriptionContains", "descContains"):
                continue
            if k == "resourceId":
                kw["id"] = v
            elif k == "className":
                kw["type"] = v
            else:
                kw[k] = v
        if not kw and any(k in selectors for k in ("textContains", "textMatches", "descriptionContains", "descContains")):
            # fill exact text from hierarchy so hmdriver2 can still match
            try:
                self.dump_hierarchy()
                node = self._find_first(selectors)
                if node is not None:
                    t = str(_attrs(node).get("text") or "")
                    d = str(_attrs(node).get("description") or "")
                    if t: kw["text"] = t
                    elif d: kw["description"] = d
            except Exception:
                pass
        return self._hm(**kw)

    def _live_click(self, selectors: dict, retries: int = 3):
        # Prefer dump→bounds→coordinate tap: survives selector index churn and
        # mid-animation hmdriver2 misses better than bare obj.click().
        last = None
        for i in range(max(1, retries)):
            try:
                try:
                    self.dump_hierarchy()
                    node = self._find_first(selectors)
                    if node is not None:
                        bounds = _parse_bounds(_attrs(node).get("bounds"))
                        if bounds:
                            x = (bounds[0] + bounds[2]) // 2
                            y = (bounds[1] + bounds[3]) // 2
                            return self._click_xy(x, y)
                except Exception as e:
                    last = e
                obj = self._live_obj(selectors)
                return obj.click()
            except Exception as e:
                last = e
                name = type(e).__name__
                if "ElementNotFound" not in name and "NotFound" not in name:
                    raise
                time.sleep(0.5)
        if last is not None:
            raise last

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
