"""Hierarchy xpath for Harmony HMDevice (hmdriver2-compatible)."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


def _walk_nodes(root):
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


def _parse_bounds(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        return [int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])]
    nums = re.findall(r"-?\d+", str(raw))
    if len(nums) >= 4:
        return [int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])]
    return None


def _clean_xml_text(s: str) -> str:
    return "".join(ch for ch in s if ord(ch) >= 32 or ch in "\t\n\r")


def hierarchy_to_xml(hierarchy: dict):
    from lxml import etree

    attrs = hierarchy.get("attributes")
    if not isinstance(attrs, dict):
        attrs = (
            {k: v for k, v in hierarchy.items() if k != "children"}
            if isinstance(hierarchy, dict)
            else {}
        )
    cleaned = {k: _clean_xml_text(str(v)) for k, v in (attrs or {}).items()}
    tag = cleaned.get("type") or "orgRoot"
    tag = re.sub(r"[^A-Za-z0-9_.-]", "_", str(tag)) or "orgRoot"
    if tag[0].isdigit():
        tag = "n_" + tag
    el = etree.Element(tag, attrib=cleaned)
    for ch in hierarchy.get("children") or []:
        if isinstance(ch, dict):
            el.append(hierarchy_to_xml(ch))
    return el


def xpath_first(hierarchy: dict, expr: str) -> Tuple[Optional[List[int]], dict]:
    if not hierarchy or not expr:
        return None, {}
    try:
        xml = hierarchy_to_xml(hierarchy)
        hits = xml.xpath(expr)
        if hits:
            node = hits[0]
            attrib = dict(node.attrib)
            return _parse_bounds(attrib.get("bounds")), attrib
    except Exception:
        pass
    key = val = None
    m = re.search(r"@text=(['\"])(.*?)\1", expr)
    if m:
        key, val = "text", m.group(2)
    else:
        m = re.search(r"@description=(['\"])(.*?)\1", expr)
        if m:
            key, val = "description", m.group(2)
    if not key:
        return None, {}
    for node in _walk_nodes(hierarchy):
        a = _attrs(node)
        if str(a.get(key) or "") == val:
            return _parse_bounds(a.get("bounds")), dict(a)
    return None, {}


class HMXpathElement:
    def __init__(self, device, expr: str):
        self.device = device
        self.expr = expr
        self._bounds: Optional[List[int]] = None
        self._attrib: dict = {}
        self._resolve()

    def _resolve(self) -> None:
        try:
            if getattr(self.device, "_static_locked", False) and self.device._hierarchy is not None:
                root = self.device._hierarchy
            else:
                root = self.device.dump_hierarchy()
        except Exception:
            root = {}
        self._bounds, self._attrib = xpath_first(root or {}, self.expr)

    def exists(self) -> bool:
        return self._bounds is not None

    def click(self, settle: float = 0.4):
        if not self._bounds:
            raise LookupError("xpath not found: %s" % self.expr)
        prev = self.device._hierarchy_fingerprint()
        x = (self._bounds[0] + self._bounds[2]) // 2
        y = (self._bounds[1] + self._bounds[3]) // 2
        r = self.device._click_xy(x, y)
        self.device._bust_live()
        self.device._settle_after_action(prev_fp=prev, timeout=min(0.25, float(settle or 0)))
        return r

    def click_if_exists(self, settle: float = 0.4) -> bool:
        if not self.exists():
            return False
        self.click(settle=settle)
        return True

    @property
    def info(self) -> dict:
        return dict(self._attrib)
