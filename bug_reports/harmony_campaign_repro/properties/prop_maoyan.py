"""Manual Kea2 — Maoyan (猫眼). Less popular. T0 bottom tabs."""
import time
import unittest
from kea2 import precondition

class MaoyanProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None: return
        for t in ("同意", "Deny", "关闭", "取消", "我知道了"):
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

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="演出").exists())
    def test_home_show_roundtrip(self):
        self.d(text="演出").click(); time.sleep(0.6)
        assert self.d(text="演出").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.6)
        assert self.d(text="首页").exists() or self.d(text="演出").exists()
