"""夸克 — safe_click + alive."""
from __future__ import annotations

import unittest

from kea2 import precondition, prob

from properties.modeA_props._util import any_text, dismiss_noise, on_package, safe_click, ui_alive


class QuarkProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.8)
    @precondition(
        lambda self: on_package(self.d, "com.quark.ohosbrowser")
        or any_text(self.d, ("千问", "把问题和任务交给我", "嗨！我是夸克"))
    )
    def test_ai_home_chrome(self):
        assert ui_alive(self.d, extra=("千问", "AI写作", "学习", "扫描王", "小说", "网盘"))

    @prob(0.75)
    @precondition(
        lambda self: (
            on_package(self.d, "com.quark.ohosbrowser") or any_text(self.d, ("千问", "嗨！我是夸克"))
        )
        and self.d(text="AI写作").exists()
    )
    def test_ai_write_entry(self):
        if not safe_click(self.d, "AI写作"):
            return
        assert ui_alive(self.d, extra=("AI写作", "写作", "开始", "千问"))

    @prob(0.7)
    @precondition(
        lambda self: (
            on_package(self.d, "com.quark.ohosbrowser") or any_text(self.d, ("千问", "嗨！我是夸克"))
        )
        and self.d(text="扫描王").exists()
    )
    def test_scan_entry(self):
        if not safe_click(self.d, "扫描王"):
            return
        assert ui_alive(self.d, extra=("扫描", "拍照", "相册", "Allow", "允许", "Deny"))
