"""Deep hunt — semantic flows that can catch real product bugs.

Focus: search query reflection, nav round-trip, freeze, dead primary CTA.
Fails require dump triage (timing FP possible) but stronger than chrome-alive.
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    LOGINISH,
    TABISH,
    any_text,
    click_first,
    count_texts,
    dismiss_noise,
    fg_package,
    hierarchy_fingerprint,
    hierarchy_text_count,
    query_reflected,
    safe_click,
    texts_blob,
    type_into_search,
    ui_alive,
)

_HOME = ("首页", "Home", "推荐", "美团", "关注")
_TABS = (
    "推荐", "热榜", "关注", "首页", "视频", "发现", "热门", "直答", "社区",
    "行程", "消息", "我的", "Home", "Video", "Discover", "Message", "Me",
)
# short queries that should echo in UI if search works
_QUERIES = ("酒店", "火锅", "手机", "咖啡", "地图", "hotel", "food")


class DeepHuntProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.95)
    @max_tries(6)
    @precondition(
        lambda self: any_text(self.d, ("搜索", "Search", "搜一搜"))
        or hierarchy_text_count(self.d) >= 6
    )
    def test_search_query_reflected(self):
        """Type a query; hierarchy must reflect it (input echo or results)."""
        # open search surface
        click_first(self.d, ("搜索", "Search", "搜一搜", "搜一搜："), settle=0.35)
        q = None
        blob0 = texts_blob(self.d)
        for cand in _QUERIES:
            # prefer query not already plastered on home marketing
            if blob0.count(cand) <= 2:
                q = cand
                break
        if not q:
            q = "测试"
        if not type_into_search(self.d, q, settle=0.4):
            return  # cannot drive input on this surface
        # submit if 搜索 button exists
        click_first(self.d, ("搜索", "Search", "确定", "完成"), settle=0.4)
        time.sleep(0.5)
        # login wall after search is product gate, not broken search
        if any_text(self.d, LOGINISH + ("+86", "获取验证码", "欢迎来到", "Log in", "Sign in")):
            return
        assert query_reflected(self.d, q) or focused_ok(self.d, q), (
            f"search query not reflected q={q!r}"
        )

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: count_texts(self.d, _HOME) >= 1 and count_texts(self.d, _TABS) >= 2)
    def test_leave_and_return_home(self):
        """Leave home tab → return; home chrome must come back."""
        home = next((t for t in _HOME if self.d(text=t).exists()), None)
        other = next(
            (t for t in _TABS if t != home and self.d(text=t).exists()),
            None,
        )
        if not home or not other:
            return
        if not safe_click(self.d, other, settle=0.4):
            return
        if not safe_click(self.d, home, settle=0.4):
            return
        assert (
            any_text(self.d, _HOME + TABISH)
            or hierarchy_text_count(self.d) >= 8
        ), f"return home failed home={home} via={other}"

    @prob(0.92)
    @max_tries(4)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 6)
    def test_ui_not_frozen(self):
        """Two actions; if fingerprint never moves → freeze/stuck."""
        fp0 = hierarchy_fingerprint(self.d)
        # action 1: swipe or tab
        moved = False
        try:
            if hasattr(self.d, "swipe"):
                self.d.swipe(0.5, 0.7, 0.5, 0.35, 0.12)
                time.sleep(0.35)
                moved = hierarchy_fingerprint(self.d) != fp0
        except Exception:
            pass
        if not moved:
            tab = next((t for t in _TABS if self.d(text=t).exists()), None)
            if tab:
                safe_click(self.d, tab, settle=0.4)
                moved = hierarchy_fingerprint(self.d) != fp0
        if not moved:
            click_first(self.d, ("搜索", "Search"), settle=0.35)
            moved = hierarchy_fingerprint(self.d) != fp0
        n = hierarchy_text_count(self.d)
        pkg = fg_package(self.d)
        if pkg in ("com.ohos.sceneboard", None):
            return
        # ponytail: map/canvas/static chrome often no text-fp change — only fail
        # when tree is thin (real stuck blank) not when rich sticky UI
        # dialog/sheet chrome = interactive (not freeze)
        if any_text(self.d, ("取消", "确认", "确定", "关闭", "Cancel", "OK", "知道了")):
            return
        # only thin stuck trees are freeze; rich sticky OK
        assert moved or n >= 6, f"UI frozen/thin fp_stuck n={n} pkg={pkg}"

    @prob(0.88)
    @max_tries(5)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 2)
    def test_rapid_tab_switch_stable(self):
        """A→B→A tab switches must keep interactive UI (not crash blank)."""
        tabs = [t for t in _TABS if self.d(text=t).exists()][:3]
        if len(tabs) < 2:
            return
        pkg0 = fg_package(self.d)
        for t in (tabs[0], tabs[1], tabs[0]):
            safe_click(self.d, t, settle=0.7)
        pkg1 = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        assert n >= 5 or ui_alive(self.d), f"rapid tab left blank n={n}"
        if pkg0 and pkg1 and pkg1 != pkg0:
            if pkg1 not in ("com.ohos.sceneboard", "com.huawei.hmsapp.appgallery"):
                raise AssertionError(f"rapid tab package leak {pkg0}->{pkg1}")

    @prob(0.85)
    @max_tries(4)
    @precondition(lambda self: any_text(self.d, ("搜索", "Search")) and hierarchy_text_count(self.d) >= 5)
    def test_search_cancel_restores(self):
        """Open search then 取消/back; shell should return."""
        fp0 = hierarchy_fingerprint(self.d)
        if not click_first(self.d, ("搜索", "Search", "搜一搜"), settle=0.35):
            return
        if not click_first(self.d, ("取消", "Cancel", "关闭"), settle=0.35):
            try:
                if hasattr(self.d, "go_back"):
                    self.d.go_back()
                else:
                    self.d.press_back()
            except Exception:
                return
            time.sleep(0.7)
        assert (
            ui_alive(self.d)
            or any_text(self.d, TABISH)
            or hierarchy_text_count(self.d) >= 6
            or hierarchy_fingerprint(self.d) == fp0
        ), "search cancel lost shell"


def focused_ok(d, q: str) -> bool:
    """Input still focused with query-ish content."""
    from properties.modeA_props._util import focused_input, query_reflected
    return focused_input(d) and query_reflected(d, q)
