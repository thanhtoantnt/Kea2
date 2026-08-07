"""美团 — safe_click + ui_alive."""
from __future__ import annotations

import unittest

from kea2 import precondition, prob

from properties.modeA_props._util import any_text, dismiss_noise, on_package, safe_click, ui_alive


class MeituanProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.8)
    @precondition(
        lambda self: (
            on_package(self.d, "com.sankuai.hmeituan", "com.sankuai.dianping", "com.meituan.takeaway")
            or any_text(self.d, ("欢迎登录美团", "购物车"))
        )
        and self.d(text="搜索").exists()
    )
    def test_search_keeps_shell(self):
        if not safe_click(self.d, "搜索"):
            return
        assert ui_alive(self.d, extra=("搜索", "取消", "购物车", "推荐"))

    @prob(0.7)
    @precondition(
        lambda self: any_text(self.d, ("欢迎登录美团", "未注册手机号验证后自动创建美团账号"))
    )
    def test_login_sheet_coherent(self):
        assert any_text(self.d, ("欢迎登录美团", "+86", "用户协议", "隐私政策", "我已阅读并同意"))

    @prob(0.65)
    @precondition(
        lambda self: sum(
            1 for t in ("首页", "视频", "消息", "购物车", "我的") if self.d(text=t).exists()
        )
        >= 2
    )
    def test_main_tabs_roundtrip(self):
        # avoid 我的 first (login); prefer 首页/视频
        clicked = any(
            safe_click(self.d, t)
            for t in ("视频", "首页", "消息", "购物车")
            if self.d(text=t).exists()
        )
        if not clicked:
            return
        assert ui_alive(self.d, extra=("首页", "购物车", "视频", "消息"))
