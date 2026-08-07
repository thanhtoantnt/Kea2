"""Ctrip CTImage-targeted props — from B7 crash + abc mine.

B7 product bug: RangeError Stack overflow in
  @ctcommon/ctimage CTImage.onImageOptionChange <-> CTImageLoader.transUrl
  page @ctbusiness/cthome_CTHomeWrapperV1

Mine evidence: mined_all/com.ctrip.harmonynext/ctimage_hits.txt (CTImageLoader,
UrlTrans, TestCTImagePage, …).

Goal: scroll/swipe home feed (image-heavy) + tab hop to stress image bind loop;
assert no crash and UI stays alive. Phone required to execute; signals offline.
"""
from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    any_text,
    click_first,
    dismiss_noise,
    fg_package,
    hierarchy_text_count,
    ui_alive,
)

PKG = "com.ctrip.harmonynext"
_REPO = Path(__file__).resolve().parents[2]
_SIG = _REPO / "modeA_runs/decompile_exp/mined_all" / PKG / "signals.json"

# home chrome from mine + known ctrip
_HOME = ("首页", "酒店", "机票", "火车票", "门票", "旅游", "行程", "我的", "攻略", "民宿")
_FEEDISH = ("特价", "推荐", "猜你喜欢", "限时", "爆款", "直播", "周末")


def _signals() -> dict:
    if _SIG.exists():
        return json.loads(_SIG.read_text(encoding="utf-8"))
    return {}


def _on_ctrip(d) -> bool:
    p = fg_package(d) or ""
    return PKG in p or any_text(d, _HOME)


def _ctimage_confirmed() -> bool:
    s = _signals()
    if s.get("has_ctimage") and s.get("ctimage_symbols"):
        return True
    hits = _REPO / "modeA_runs/decompile_exp/mined_all" / PKG / "ctimage_hits.txt"
    if hits.exists() and "CTImage" in hits.read_text(encoding="utf-8", errors="ignore"):
        return True
    return False


class CtripCTImageProps(unittest.TestCase):
    """Stress image-heavy surfaces; catch CTImage notify loops as crash/blank."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)
        # offline gate — pack is a no-op generator check without device
        cls._has_ct = _ctimage_confirmed()

    @prob(0.99)
    @precondition(lambda self: True)
    def test_ctimage_symbols_mined(self):
        """Offline oracle: abc mine must still show CTImage stack (regressed mine?)."""
        assert _ctimage_confirmed(), "CTImage symbols missing from mined_all — re-mine abc"

    @prob(0.98)
    @max_tries(10)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_home_image_scroll_alive(self):
        """Scroll home (CTHome image bind path); must not crash/blank."""
        d = self.d
        n0 = hierarchy_text_count(d)
        # swipe feed region mid-screen
        try:
            info = d.info if hasattr(d, "info") else {}
            w = int(info.get("displayWidth") or 1080)
            h = int(info.get("displayHeight") or 1920)
        except Exception:
            w, h = 1080, 1920
        for _ in range(4):
            try:
                d.swipe(w // 2, int(h * 0.72), w // 2, int(h * 0.28), 0.15)
            except Exception:
                break
            time.sleep(0.35)
            if not ui_alive(d):
                break
        time.sleep(0.4)
        pkg = fg_package(d) or ""
        n1 = hierarchy_text_count(d)
        assert PKG in pkg or n1 >= 4, f"left ctrip after image scroll pkg={pkg}"
        assert n1 >= 3 and ui_alive(d), f"CTImage scroll blank {n0}->{n1}"

    @prob(0.97)
    @max_tries(8)
    @precondition(lambda self: _on_ctrip(self.d) and any_text(self.d, _HOME))
    def test_tab_hop_image_surfaces(self):
        """Hop tabs that remount image cells — B7 path was home wrapper."""
        d = self.d
        tabs = tuple(_signals().get("tabs") or ()) + _HOME
        seen = 0
        for t in tabs:
            if not d(text=t).exists() and not d(textContains=t).exists():
                continue
            if click_first(d, (t,), settle=0.45):
                seen += 1
                time.sleep(0.3)
                # light swipe after tab to force image bind
                try:
                    d.swipe(0.5, 0.65, 0.5, 0.35, 0.12)
                except Exception:
                    pass
                time.sleep(0.25)
                assert ui_alive(d), f"dead after tab {t}"
                if seen >= 3:
                    break
        if seen == 0:
            return
        n = hierarchy_text_count(d)
        assert n >= 3, f"tab hop thin dump n={n}"

    @prob(0.96)
    @max_tries(8)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_feedish_click_no_crash(self):
        d = self.d
        labels = _FEEDISH + tuple((_signals().get("misc_labels") or [])[:15])
        if not click_first(d, labels, settle=0.4):
            return
        time.sleep(0.5)
        # back once if pushed detail
        try:
            d.press("back")
        except Exception:
            pass
        time.sleep(0.35)
        pkg = fg_package(d) or ""
        assert ui_alive(d) and hierarchy_text_count(d) >= 2, "feed click killed UI"
        assert PKG in pkg or hierarchy_text_count(d) >= 4, f"fg={pkg}"
