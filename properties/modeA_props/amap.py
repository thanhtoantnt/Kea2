"""高德 — safe_click + ui_alive."""
from __future__ import annotations

import unittest

from kea2 import precondition, prob

from properties.modeA_props._util import any_text, dismiss_noise, on_package, safe_click, ui_alive


class AmapProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.8)
    @precondition(
        lambda self: (
            on_package(self.d, "com.amap.hmapp")
            or (self.d(text="首页").exists() and self.d(text="探索").exists())
        )
        and self.d(text="探索").exists()
    )
    def test_home_explore_roundtrip(self):
        if not safe_click(self.d, "探索"):
            return
        assert ui_alive(self.d, extra=("探索", "首页", "路线"))
        if self.d(text="首页").exists():
            safe_click(self.d, "首页")
            assert ui_alive(self.d, extra=("首页", "路线", "探索"))

    @prob(0.85)
    @precondition(
        lambda self: (on_package(self.d, "com.amap.hmapp") or self.d(text="图层").exists())
        and self.d(text="路线").exists()
    )
    def test_route_keeps_map_chrome(self):
        if not safe_click(self.d, "路线", settle=0.4):
            return
        assert ui_alive(self.d, extra=("路线", "驾车", "公交地铁", "公交", "打车", "步行"))

    @prob(0.7)
    @precondition(
        lambda self: (on_package(self.d, "com.amap.hmapp") or True) and self.d(text="图层").exists()
    )
    def test_layer_panel_reachable(self):
        if not safe_click(self.d, "图层"):
            return
        assert ui_alive(self.d, extra=("图层", "路况", "卫星", "路线", "关闭", "完成"))

    @prob(0.75)
    @precondition(
        lambda self: self.d(text="路线").exists()
        and any_text(self.d, ("驾车", "公交地铁", "打车"))
    )
    def test_route_modes_visible(self):
        assert any_text(self.d, ("驾车", "公交地铁", "打车", "步行", "骑行"))
