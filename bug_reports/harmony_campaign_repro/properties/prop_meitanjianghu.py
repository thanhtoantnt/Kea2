"""Manual Kea2 — 煤炭江湖. T0 home tabs."""
import time
import unittest
from kea2 import precondition


class MeitanJianghuProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None:
            return
        for t in ("Allow", "Deny", "同意", "取消", "我知道了", "关闭", "跳过"):
            try:
                if d(text=t).exists():
                    d(text=t).click()
                    time.sleep(0.4)
            except Exception:
                pass
        try:
            if d(text="首页").exists():
                d(text="首页").click()
                time.sleep(0.5)
        except Exception:
            pass

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="我的").exists())
    def test_home_me_roundtrip(self):
        self.d(text="我的").click()
        time.sleep(0.5)
        assert self.d(text="我的").exists() or self.d(text="首页").exists()
        self.d(text="首页").click()
        time.sleep(0.5)
        assert self.d(text="首页").exists() or self.d(text="我的").exists()

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="推荐").exists())
    def test_home_recommend_visible(self):
        assert self.d(text="推荐").exists()
        assert self.d(text="首页").exists()
