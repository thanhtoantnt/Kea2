"""
Kea2 HarmonyOS property sample — Amap (com.amap.hmapp), third-party.

Run (device unlocked):
  .venv/bin/python -m kea2.cli run --platform harmony \\
    -s <SERIAL> -p com.amap.hmapp \\
    --running-minutes 2 --max-step 12 --throttle 700 \\
    -o ~/harmonyy-app/amap/kea2-out \\
    propertytest examples.harmony_amap_sample
"""
import unittest

from kea2 import precondition


class AmapHarmonyProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None:
            return
        # clipboard / permission popups on first launch
        for t in ("Deny", "Allow this time only", "不同意", "同意"):
            try:
                if d(text=t).exists():
                    d(text=t).click()
            except Exception:
                pass

    @precondition(
        lambda self: self.d(text="首页").exists() and self.d(text="探索").exists()
    )
    def test_home_explore_roundtrip(self):
        """Bottom tabs 首页 ↔ 探索 stay reachable."""
        self.d(text="探索").click()
        assert self.d(text="探索").exists() or self.d(text="首页").exists()
        self.d(text="首页").click()
        assert self.d(text="首页").exists()

    @precondition(lambda self: self.d(text="路线").exists())
    def test_route_entry_reachable(self):
        """Tapping 路线 keeps map chrome (路线 or 驾车) on screen."""
        self.d(text="路线").click()
        assert (
            self.d(text="路线").exists()
            or self.d(text="驾车").exists()
            or self.d(text="首页").exists()
        )
