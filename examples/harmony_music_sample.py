"""
Kea2 HarmonyOS property sample — Huawei Music (com.huawei.hmsapp.music).

Run from Kea2 repo (device unlocked, music installed):

  cd ~/github/Kea2
  .venv/bin/python -m kea2.cli run --platform harmony \\
    -s 5SM0125606000291 -p com.huawei.hmsapp.music \\
    --running-minutes 3 --max-step 15 --throttle 700 \\
    -o ~/harmonyy-app/music/kea2-out \\
    propertytest examples.harmony_music_sample
"""
import unittest

from kea2 import precondition


class MusicHarmonyProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # dismiss common first-run dialogs if present
        d = getattr(cls, "d", None)
        if d is None:
            return
        for t in ("Agree", "Deny", "Allow", "Cancel"):
            try:
                if d(text=t).exists():
                    d(text=t).click()
            except Exception:
                pass

    @precondition(
        lambda self: self.d(text="Home").exists() and self.d(text="Me").exists()
    )
    def test_home_me_roundtrip(self):
        """Home → Me → Home keeps bottom tab chrome."""
        self.d(text="Me").click()
        assert self.d(text="Me").exists() or self.d(text="Home").exists()
        self.d(text="Home").click()
        assert self.d(text="Home").exists()

    @precondition(
        lambda self: self.d(text="Recommended").exists()
        and self.d(text="Playlists").exists()
    )
    def test_carousel_playlists_selectable(self):
        """Tapping Playlists keeps carousel labels on screen."""
        self.d(text="Playlists").click()
        assert self.d(text="Playlists").exists() or self.d(text="Recommended").exists()
