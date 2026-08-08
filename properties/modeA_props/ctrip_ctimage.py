"""Ctrip properties from *manual* B_names decompile reading (not a template miner).

Evidence (agent-read):
  xabc_out/decompiled/com.ctrip.harmonynext/arkdemo.ts  — 4657 records, B_names only
  mined_all/com.ctrip.harmonynext/{signals.json,ctimage_hits.txt,labels_cjk.txt}
  bug_reports/com.ctrip.harmonynext_ctimage_stack_overflow/  — confirmed jscrash

Module map (owned, high-signal):
  entry:   phone…CTEntryAbility / CTEntryStage
  home:    @ctbusiness/cthome
             pages: CTHomePage, CTHomeWrapper, CTHomeWrapperV1, CTHomeIndex, CTSpashUI
             feed:  CTHomeWaterFlow + SimplePic / PicTxt / PicTxtCarousel items  ← image bind
             grid:  CTHomeMainGridView / CTHomeMainGridItem  (酒店/机票/火车票/…)
             chrome: CTHomeSearchBarView, CustomTabBar, CTHomeFlowTabBar, TabBarModel
             skeleton: CTHomeSkeleton*
  image:   @ctcommon/ctimage 8.94.6-beta…
             CTImage, CTImageOption, CTImageLoader, CTImageUrlTransUtil,
             CTImageLoaderUrlTransSupportUtil, CTTransformationFactory,
             CTWebpSupportUtils, CTAVifSupportUtils
             (+ RNOH RemoteImageLoader — separate stack)
  search:  @ctbusiness/ctsearch  SearchHome, CTSearchMain, CTSearchLenovo*
  hotel:   @ctbusiness/cthotel   HotelListPage, HotelAlbum* (image-heavy deeper)
  also:    cthotel/ctflight/cttrain/cttour/ctschedule packages present

Product bug (runtime, not static body — B_names has no method AST):
  CTImage.onImageOptionChange ↔ CTImageLoader.transUrl  → RangeError Stack overflow
  often on CTHomeWrapper image bind / cold start; UI may recover

UI strings (signals + labels mine):
  tabs/grid: 首页 酒店 机票 火车票 门票 旅游 行程 攻略 民宿 我的 消息 订单
  search: 搜索 查酒店 查机票
  errors: 网络异常 加载失败 请重试 …
  actions: 取消 确认 重试 刷新 返回 知道了

Contracts (UI-checkable; crash oracle is separate faultlogger watcher):
  ctimage_symbols_mined   pre: always
                          post: mine still has CTImage stack (regressed mine?)
  inv_ctrip_shell         pre: on ctrip
                          post: home/grid chrome or thick tree
  home_waterflow_scroll   pre: on ctrip (home image path)
                          act: 4× swipe up mid-screen (WaterFlow bind)
                          post: still ctrip, not blank
  home_tabbar_hop         pre: tab labels visible (CustomTabBar)
                          act: hop ≤3 tabs + light swipe each
                          post: alive each hop; thick dump
  main_grid_entry         pre: grid label 酒店/机票/… visible
                          act: click one grid entry
                          post: shell alive; back if left home
  search_bar_opens        pre: search chrome (CTHomeSearchBarView)
                          act: click 搜索/查酒店…
                          post: not dead; back
  return_home_remount     pre: on ctrip
                          act: leave via tab/grid then 首页
                          post: home chrome back (remount wrapper / images)
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
    hierarchy_fingerprint,
    hierarchy_text_count,
    ui_alive,
)

PKG = "com.ctrip.harmonynext"
_REPO = Path(__file__).resolve().parents[2]
_MINED = _REPO / "modeA_runs/decompile_exp/mined_all" / PKG

# CustomTabBar / signals tabs
_TABS = ("首页", "酒店", "机票", "火车票", "门票", "旅游", "行程", "攻略", "民宿", "我的", "消息", "订单")
# CTHomeMainGridView entries (also appear as tabs in mine — fine)
_GRID = ("酒店", "机票", "火车票", "门票", "旅游", "民宿", "汽车票", "接送机", "租车", "攻略")
_SEARCH = ("搜索", "Search", "搜一搜", "查酒店", "查机票")
_HOME_MARK = ("首页", "酒店", "机票", "火车票")
_FEED = ("特价", "推荐", "猜你喜欢", "限时", "爆款", "直播", "周末")
_ERR = ("网络异常", "加载失败", "请重试", "请稍后重试", "连接异常")
_ACT = ("重试", "刷新", "返回", "知道了", "取消", "确认")


def _signals() -> dict:
    p = _MINED / "signals.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _on_ctrip(d) -> bool:
    p = fg_package(d) or ""
    return PKG in p or any_text(d, _HOME_MARK)


def _ctimage_confirmed() -> bool:
    s = _signals()
    if s.get("has_ctimage"):
        return True
    hits = _MINED / "ctimage_hits.txt"
    if hits.exists() and "CTImage" in hits.read_text(encoding="utf-8", errors="ignore"):
        return True
    # names dump still lists module
    names = _REPO / "modeA_runs/decompile_exp/xabc_out/decompiled" / PKG / "arkdemo.ts"
    if names.exists() and "ctcommon.ctimage" in names.read_text(encoding="utf-8", errors="ignore"):
        return True
    return False


def _swipe_up(d, n: int = 3) -> None:
    try:
        info = d.info if hasattr(d, "info") else {}
        w = int(info.get("displayWidth") or 1080)
        h = int(info.get("displayHeight") or 1920)
    except Exception:
        w, h = 1080, 1920
    for _ in range(n):
        try:
            d.swipe(w // 2, int(h * 0.72), w // 2, int(h * 0.28), 0.15)
        except Exception:
            try:
                d.swipe_ext("up", scale=0.55)
            except Exception:
                break
        time.sleep(0.3)


def _back(d) -> None:
    try:
        d.press("back")
    except Exception:
        pass
    time.sleep(0.3)


class CtripCTImageProps(unittest.TestCase):
    """Hand contracts: home/CTImage stress + grid/search shell from module map."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)
        cls._has_ct = _ctimage_confirmed()

    # --- offline / mine sanity ---
    @prob(0.99)
    @precondition(lambda self: True)
    def test_ctimage_symbols_mined(self):
        """post: @ctcommon/ctimage still present in mine/names (pack still valid)."""
        assert _ctimage_confirmed(), "CTImage missing from mine/names — re-decompile/re-mine"

    # --- inv: shell ---
    @prob(0.99)
    @max_tries(12)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_inv_ctrip_shell(self):
        """inv: on CTEntryAbility ⇒ tab/grid chrome or thick tree (not OS blank)."""
        d = self.d
        ok = (
            any_text(d, _TABS)
            or any_text(d, _GRID)
            or any_text(d, _SEARCH)
            or hierarchy_text_count(d) >= 8
        )
        assert ok and ui_alive(d), f"ctrip shell empty n={hierarchy_text_count(d)}"

    # --- CTHomeWaterFlow image bind path (CTImage stress) ---
    @prob(0.98)
    @max_tries(10)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_home_waterflow_scroll_alive(self):
        """pre: on ctrip. act: swipe WaterFlow (SimplePic/PicTxt bind). post: alive.

        Stresses CTImage option/url path; jscrash caught by log watcher if loop trips.
        """
        d = self.d
        # prefer home before scroll so wrapper is mounted
        click_first(d, ("首页",), settle=0.35)
        n0 = hierarchy_text_count(d)
        _swipe_up(d, 4)
        time.sleep(0.35)
        pkg = fg_package(d) or ""
        n1 = hierarchy_text_count(d)
        assert PKG in pkg or n1 >= 4, f"left ctrip after waterflow scroll pkg={pkg}"
        assert n1 >= 3 and ui_alive(d), f"waterflow scroll blank {n0}->{n1}"

    # --- CustomTabBar / CTHomeFlowTabBar ---
    @prob(0.97)
    @max_tries(8)
    @precondition(lambda self: _on_ctrip(self.d) and any_text(self.d, _TABS))
    def test_home_tabbar_hop(self):
        """pre: tab labels. act: hop tabs + swipe (remount image cells). post: each alive."""
        d = self.d
        tabs = tuple(_signals().get("tabs") or ()) + _TABS
        seen = 0
        for t in tabs:
            if t == "首页":
                continue
            if not (d(text=t).exists() or d(textContains=t).exists()):
                continue
            if not click_first(d, (t,), settle=0.45):
                continue
            seen += 1
            time.sleep(0.25)
            _swipe_up(d, 1)
            assert ui_alive(d), f"dead after tab {t}"
            if seen >= 3:
                break
        if seen == 0:
            return
        # return home — remount CTHomeWrapper image tree
        click_first(d, ("首页",), settle=0.4)
        n = hierarchy_text_count(d)
        assert n >= 3 and ui_alive(d), f"tab hop thin n={n}"

    # --- CTHomeMainGridView ---
    @prob(0.94)
    @max_tries(6)
    @precondition(lambda self: _on_ctrip(self.d) and any_text(self.d, _GRID))
    def test_main_grid_entry_alive(self):
        """pre: main grid labels. act: open 酒店/机票/…. post: shell; back to home."""
        d = self.d
        click_first(d, ("首页",), settle=0.3)
        fp0 = hierarchy_fingerprint(d)
        if not click_first(d, _GRID, settle=0.5):
            return
        time.sleep(0.45)
        n = hierarchy_text_count(d)
        # icon-font labels (景点/酒店) count thin in walker — chrome OR n is enough
        assert (
            ui_alive(d)
            or n >= 2
            or any_text(d, _GRID + ("首页", "我的", "筛选"))
        ), f"grid entry killed UI n={n}"
        # if navigated away, back once (HotelListPage etc.)
        if hierarchy_fingerprint(d) != fp0 and not any_text(d, ("首页",)):
            _back(d)
        pkg = fg_package(d) or ""
        assert PKG in pkg or hierarchy_text_count(d) >= 4, f"fg after grid={pkg}"

    # --- CTHomeSearchBarView / ctsearch ---
    @prob(0.93)
    @max_tries(6)
    @precondition(lambda self: _on_ctrip(self.d) and any_text(self.d, _SEARCH))
    def test_search_bar_opens_alive(self):
        """pre: search chrome. act: open SearchHome path. post: not dead-end."""
        d = self.d
        if not click_first(d, _SEARCH, settle=0.45):
            return
        time.sleep(0.4)
        n = hierarchy_text_count(d)
        assert ui_alive(d) and n >= 2, f"search open blank n={n}"
        # error chrome allowed but must have escape
        if any_text(d, _ERR):
            assert any_text(d, _ACT) or n >= 4, "search error dead-end"
        _back(d)

    # --- remount home (CTHomeWrapper / image rebind) ---
    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_return_home_remount_alive(self):
        """pre: on ctrip. act: visit 我的/消息 then 首页. post: home chrome + alive.

        Forces CTHomeWrapper remount → another CTImage bind wave.
        """
        d = self.d
        click_first(d, ("我的", "消息", "行程"), settle=0.4)
        time.sleep(0.3)
        if not click_first(d, ("首页",), settle=0.45):
            return
        time.sleep(0.35)
        _swipe_up(d, 2)
        pkg = fg_package(d) or ""
        n = hierarchy_text_count(d)
        assert PKG in pkg or n >= 4, f"left ctrip remount home pkg={pkg}"
        assert (
            any_text(d, _HOME_MARK + _GRID) or n >= 6
        ) and ui_alive(d), f"home remount weak n={n}"

    # --- feed / waterflow cell click (optional) ---
    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on_ctrip(self.d))
    def test_feedish_click_no_crash(self):
        """pre: on ctrip. act: click feedish/misc cell. post: alive; back if pushed."""
        d = self.d
        labels = _FEED + tuple((_signals().get("misc_labels") or [])[:12])
        if not click_first(d, labels, settle=0.4):
            return
        time.sleep(0.45)
        assert ui_alive(d) and hierarchy_text_count(d) >= 2, "feed click killed UI"
        if not any_text(d, _HOME_MARK):
            _back(d)
        pkg = fg_package(d) or ""
        assert PKG in pkg or hierarchy_text_count(d) >= 4, f"fg={pkg}"
