"""
Kea2 HarmonyOS properties — Amap (com.amap.hmapp).

Ported/extended from Kea example/prop_amap.py (privacy dialog) plus
tab/route chrome checks from live dumpLayout.

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
        # clipboard / permission popups — do not auto-accept privacy (see Kea)
        for t in ("Deny", "Allow this time only", "不允许"):
            try:
                if d(text=t).exists():
                    d(text=t).click()
            except Exception:
                pass

    # --- from Kea prop_amap.AmapProperty.privacy_dialog_stable ---
    @precondition(
        lambda self: self.d(text="同意并继续").exists()
        or self.d(text="不同意").exists()
        or self.d(text="Agree and continue").exists()
    )
    def test_privacy_dialog_stable(self):
        """Privacy dialog present → still present (do not auto-accept)."""
        assert (
            self.d(text="同意并继续").exists()
            or self.d(text="不同意").exists()
            or self.d(text="Agree and continue").exists()
        )

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
        """Tapping 路线 keeps map chrome (路线 / 驾车 / 首页) on screen."""
        self.d(text="路线").click()
        assert (
            self.d(text="路线").exists()
            or self.d(text="驾车").exists()
            or self.d(text="首页").exists()
            or self.d(text="公交").exists()
            or self.d(text="公交地铁").exists()
        )
