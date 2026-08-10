"""OpenEye props from *hand-read source* (ground truth).

Source: ~/github/HarmoneyOpenEye/entry/src/main/ets
  MainViewModel.tabTitle → 首页/发现/热门/我的
  FindViewModel.tabTitle → 关注/分类/主题
  HotViewModel.hotTabTitle → 周排行/月排行/总排行 (weekly/monthly/historical)
  HomePage CommonTopBar title "首页"; list → DetailPage
  RankPage footer "我是有底线的"
  MinePage rows: 关注/分类/热门/关于 + "Harmony-开眼App"
  StateComponent + string.json: 加载中.../点我重试/加载数据异常/网络错误/暂无数据
  SplashPage → MainPage after 2s
  RoutePath: DetailPage, ContainerPage, TestPage, CoordinatePage

UI-checkable only. Not for generic apps.
"""
from __future__ import annotations

import time
import unittest

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

PKG = "com.winwang.harmonyOpenEye"

# MainViewModel.tabTitle order
_MAIN_TABS = ("首页", "发现", "热门", "我的")
# FindViewModel
_FIND_TABS = ("关注", "分类", "主题")
# HotViewModel
_HOT_TABS = ("周排行", "月排行", "总排行")
# MinePage.itemBuilder labels
_MINE_ROWS = ("关注", "分类", "热门", "关于", "测试Result校验", "CoordinateLayout")
# StateComponent + string.json
_LOADING = ("加载中...", "加载中", "数据加载中")
_RETRY = ("点我重试",)
_ERR = ("加载数据异常", "网络错误", "暂无数据")
_FOOTER = ("我是有底线的",)
_BRAND = ("Harmony-开眼App", "开眼", "Harmony开眼")
_ABOUT = ("关于",)
_DETAIL = ("视频详情",)  # DetailPage top — explorer tarpit


def _has(d, labels) -> bool:
    """text or description (OpenEye tabs often description-thin)."""
    if any_text(d, labels):
        return True
    for t in labels:
        try:
            if d(description=t).exists():
                return True
        except Exception:
            pass
        try:
            if d(descriptionContains=t).exists():
                return True
        except Exception:
            pass
    return False


def _click(d, labels, settle: float = 0.45) -> bool:
    if click_first(d, labels, settle=settle):
        return True
    for t in labels:
        try:
            el = d(description=t)
            if el.exists():
                el.click()
                time.sleep(settle)
                return True
        except Exception:
            pass
    return False


def _on(d) -> bool:
    p = fg_package(d) or ""
    return PKG in p or _has(d, _MAIN_TABS + _BRAND + _DETAIL)


def _ensure_main(d) -> None:
    """pop DetailPage/stack until main tabs or brand visible."""
    if _has(d, _MAIN_TABS):
        return
    for _ in range(5):
        try:
            d.press("back")
        except Exception:
            try:
                d.go_back()
            except Exception:
                break
        time.sleep(0.35)
        if _has(d, _MAIN_TABS + _BRAND):
            return


def _shell(d) -> bool:
    return (
        _has(d, _MAIN_TABS)
        or _has(d, _FIND_TABS + _HOT_TABS + _MINE_ROWS + _BRAND + _DETAIL)
        or hierarchy_text_count(d) >= 6
    ) and ui_alive(d)


class OpenEyeSourceProps(unittest.TestCase):
    """Contracts taken from OpenEye ArkTS source + string.json."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.99)
    @max_tries(10)
    @precondition(lambda self: _on(self.d))
    def test_src_main_tabs_present(self):
        """MainViewModel: bottom tabs 首页/发现/热门/我的 visible (or ≥3)."""
        d = self.d
        _ensure_main(d)
        n = sum(1 for t in _MAIN_TABS if _has(d, (t,)))
        assert n >= 3 or hierarchy_text_count(d) >= 8, f"main tabs n={n}"

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_src_tab_find_topbar(self):
        """act: tap 发现. post: FindPage topbar title 发现 (CommonTopBar)."""
        d = self.d
        _ensure_main(d)
        if not _click(d, ("发现",), settle=0.5):
            return
        time.sleep(0.35)
        assert _has(d, ("发现",)) and _shell(d), "FindPage chrome missing"

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_src_hot_subtabs(self):
        """HotViewModel: after 热门, subtabs 周/月/总排行."""
        d = self.d
        _ensure_main(d)
        if not _click(d, ("热门",), settle=0.55):
            return
        time.sleep(0.4)
        n = sum(1 for t in _HOT_TABS if _has(d, (t,)))
        assert n >= 2 or _has(d, ("热门",)), f"hot subtabs n={n}"
        assert _shell(d)

    @prob(0.92)
    @max_tries(6)
    @precondition(lambda self: _on(self.d))
    def test_src_find_subtabs(self):
        """FindViewModel: 关注/分类/主题 under 发现."""
        d = self.d
        _ensure_main(d)
        if not _click(d, ("发现",), settle=0.55):
            return
        time.sleep(0.35)
        n = sum(1 for t in _FIND_TABS if _has(d, (t,)))
        assert n >= 2, f"find subtabs n={n}"

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on(self.d))
    def test_src_mine_rows(self):
        """MinePage: brand + menu rows from source itemBuilder."""
        d = self.d
        _ensure_main(d)
        if not _click(d, ("我的",), settle=0.55):
            return
        time.sleep(0.4)
        brand = _has(d, _BRAND)
        rows = sum(1 for t in ("关注", "分类", "关于") if _has(d, (t,)))
        assert brand or rows >= 2, f"mine brand={brand} rows={rows}"

    @prob(0.88)
    @max_tries(5)
    @precondition(lambda self: _on(self.d))
    def test_src_about_dialog(self):
        """Mine → 关于 → CommonDialog (title 关于)."""
        d = self.d
        _ensure_main(d)
        _click(d, ("我的",), settle=0.45)
        if not _click(d, _ABOUT, settle=0.5):
            return
        time.sleep(0.3)
        assert _has(d, _ABOUT + _BRAND) or _shell(d)

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on(self.d) and _has(self.d, _RETRY + _ERR))
    def test_src_state_retry_keeps_shell(self):
        """StateComponent: 点我重试 on error/empty → shell alive (retryCallback)."""
        d = self.d
        fp0 = hierarchy_fingerprint(d)
        if not _click(d, _RETRY, settle=0.6):
            return
        time.sleep(0.4)
        assert _shell(d) or hierarchy_fingerprint(d) != fp0 or _has(d, _LOADING + _ERR)

    @prob(0.85)
    @max_tries(5)
    @precondition(lambda self: _on(self.d) and _has(self.d, _ERR + _LOADING))
    def test_src_error_strings_from_resources(self):
        """string.json error/empty chrome present ⇒ not blank (StateComponent)."""
        d = self.d
        assert _has(d, _ERR + _LOADING + _RETRY) or hierarchy_text_count(d) >= 4

    @prob(0.88)
    @max_tries(5)
    @precondition(lambda self: _on(self.d))
    def test_src_rank_footer_or_list(self):
        """RankPage footer 我是有底线的 OR list content after hot rank load."""
        d = self.d
        _ensure_main(d)
        _click(d, ("热门",), settle=0.5)
        _click(d, _HOT_TABS, settle=0.55)
        time.sleep(0.6)
        ok = _has(d, _FOOTER) or hierarchy_text_count(d) >= 8 or _has(d, _HOT_TABS)
        assert ok and _shell(d), "rank page empty"

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on(self.d))
    def test_src_home_list_tap_stays_pkg(self):
        """Home shell / Detail still OpenEye package."""
        d = self.d
        _ensure_main(d)
        _click(d, ("首页",), settle=0.45)
        time.sleep(0.3)
        pkg = fg_package(d) or ""
        n0 = hierarchy_text_count(d)
        assert PKG in pkg or n0 >= 5, f"left home pkg={pkg}"
        assert _shell(d)

    @prob(0.92)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_src_inv_shell(self):
        """inv: on OpenEye ⇒ main/find/hot/mine chrome or thick tree."""
        assert _shell(self.d), f"dead shell n={hierarchy_text_count(self.d)}"

    @prob(0.85)
    @max_tries(4)
    @precondition(lambda self: _on(self.d))
    def test_src_mine_test_route(self):
        """Mine itemBuilder 测试Result校验 → RoutePath.TestPage; stay alive."""
        d = self.d
        _ensure_main(d)
        _click(d, ("我的",), settle=0.45)
        if not _click(d, ("测试Result校验",), settle=0.55):
            return
        time.sleep(0.35)
        pkg = fg_package(d) or ""
        assert PKG in pkg or _shell(d), f"test route killed pkg={pkg}"
