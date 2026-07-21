"""Manual Kea2 — WPS Office. Less popular. T0 bottom tabs."""
import time
import unittest
from kea2 import precondition

class WpsProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None: return
        for t in ("同意", "同意并继续", "我知道了", "Deny", "关闭", "跳过", "取消"):
            try:
                if d(text=t).exists():
                    d(text=t).click(); time.sleep(0.4)
            except Exception: pass
        try:
            if d(text="首页").exists():
                d(text="首页").click(); time.sleep(0.5)
        except Exception: pass

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="我").exists())
    def test_home_me_roundtrip(self):
        self.d(text="我").click(); time.sleep(0.9)
        assert self.d(text="我").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.9)
        assert self.d(text="首页").exists() or self.d(text="我").exists()

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="云盘").exists())
    def test_home_cloud_roundtrip(self):
        self.d(text="云盘").click(); time.sleep(0.9)
        assert self.d(text="云盘").exists() or self.d(text="首页").exists()
        self.d(text="首页").click(); time.sleep(0.9)
        assert self.d(text="首页").exists() or self.d(text="云盘").exists()
