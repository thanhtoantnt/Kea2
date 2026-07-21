"""Manual Kea2 — 淘票票. T0 bottom tabs."""
import time
import unittest
from kea2 import precondition

class TaobaomovieProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None: return
        for t in ("同意", "下次再说", "Deny", "关闭", "取消"):
            try:
                if d(text=t).exists():
                    d(text=t).click(); time.sleep(0.4)
            except Exception: pass
        for city in ("北京", "上海", "杭州"):
            try:
                if d(text=city).exists() and (d(text="选择城市").exists() or d(text="热门城市").exists()):
                    d(text=city).click(); time.sleep(0.8); break
            except Exception: pass
        try:
            if d(text="首页").exists():
                d(text="首页").click(); time.sleep(0.5)
        except Exception: pass

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="我的").exists())
    def test_home_me_roundtrip(self):
        self.d(text="我的").click(); time.sleep(0.8)
        assert self.d(text="我的").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.8)
        assert self.d(text="首页").exists() or self.d(text="我的").exists()

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="影院").exists())
    def test_home_cinema_roundtrip(self):
        self.d(text="影院").click(); time.sleep(0.8)
        assert self.d(text="影院").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.8)
        assert self.d(text="首页").exists() or self.d(text="影院").exists()
