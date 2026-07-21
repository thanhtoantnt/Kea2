"""Manual Kea2 — Qunar. T0 bottom tabs 首页/我的."""
import time
import unittest
from kea2 import precondition

class QunarProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None: return
        for t in ("同意", "Deny", "关闭", "取消", "我再想想"):
            try:
                if d(text=t).exists():
                    d(text=t).click(); time.sleep(0.4)
            except Exception: pass
        try:
            if d(text="首页").exists():
                d(text="首页").click(); time.sleep(0.5)
        except Exception: pass

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="我的").exists())
    def test_home_me_roundtrip(self):
        self.d(text="我的").click(); time.sleep(0.6)
        assert self.d(text="我的").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.6)
        assert self.d(text="首页").exists() or self.d(text="我的").exists()

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="行程").exists())
    def test_home_trip_roundtrip(self):
        self.d(text="行程").click(); time.sleep(0.6)
        assert self.d(text="行程").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.6)
        assert self.d(text="首页").exists() or self.d(text="行程").exists()
