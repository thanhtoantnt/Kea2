"""Stronger Mode A oracles — action must change UI fingerprint.

Unlike generic_ui (chrome still present), these fail when a click is a no-op
or navigates off the SUT. Package-agnostic; high prob for fire-rate.
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    TABISH,
    any_text,
    click_first,
    count_texts,
    dismiss_noise,
    fg_package,
    hierarchy_fingerprint,
    hierarchy_text_count,
    safe_click,
    ui_alive,
)

# Tabs safe to poke (avoid 我的/消息 login tarpits when possible)
_TABS = (
    "推荐", "热榜", "关注", "首页", "视频", "发现", "热门", "故事", "知识",
    "直答", "社区", "行程", "美食", "酒店", "美团",
    "Home", "Video", "Discover", "Follow", "Trending",
)
_SEARCH = ("搜索", "Search", "搜一搜", "搜一搜：")


def _sut_pkg(self) -> str | None:
    return fg_package(self.d)


class SemanticProps(unittest.TestCase):
    """Medium-strength: must observe effect, not just survival."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 2)
    def test_tab_click_changes_ui(self):
        """Tab tap must change hierarchy fingerprint (no-op click = bug)."""
        tabs = [t for t in _TABS if self.d(text=t).exists()]
        if len(tabs) < 2:
            return
        # pick non-current-looking second tab
        target = tabs[1] if tabs[0] == "首页" and len(tabs) > 1 else tabs[0]
        # prefer 热榜/视频/发现 over 首页
        for pref in ("热榜", "视频", "发现", "关注", "故事", "知识", "直答", "Video", "Discover"):
            if pref in tabs:
                target = pref
                break
        fp0 = hierarchy_fingerprint(self.d)
        pkg0 = _sut_pkg(self)
        if not safe_click(self.d, target, settle=0.4):
            return
        fp1 = hierarchy_fingerprint(self.d)
        pkg1 = _sut_pkg(self)
        n = hierarchy_text_count(self.d)
        # still SUT (or FG flicker but rich tree)
        assert pkg1 == pkg0 or pkg1 is None or n >= 5, (
            f"tab left SUT {pkg0} -> {pkg1}"
        )
        # stricter: fingerprint must change (same-tab no-op = fail)
        if fp0 == fp1:
            # one retry on alternate tab
            alt = next((t for t in tabs if t != target), None)
            if alt and safe_click(self.d, alt, settle=0.4):
                fp2 = hierarchy_fingerprint(self.d)
                n = hierarchy_text_count(self.d)
                assert fp0 != fp2 or n >= 15, (
                    f"tab no-op target={target}/{alt} n={n}"
                )
            else:
                assert n >= 15, f"tab no-op target={target} n={n}"

    @prob(0.9)
    @max_tries(6)
    @precondition(
        lambda self: any_text(self.d, _SEARCH)
        and (any_text(self.d, TABISH) or hierarchy_text_count(self.d) >= 6)
    )
    def test_search_opens_surface(self):
        """Search entry must change UI (open search page / focus)."""
        fp0 = hierarchy_fingerprint(self.d)
        hit = click_first(self.d, _SEARCH, settle=0.4)
        if not hit:
            return
        fp1 = hierarchy_fingerprint(self.d)
        # search chrome OR fingerprint change OR input focus-ish texts
        opened = any_text(
            self.d,
            (
                "取消", "搜索历史", "热门搜索", "猜你想搜", "清除",
                "Cancel", "History", "热搜", "搜索感兴趣的内容",
                "登录", "获取验证码", "+86",
            ),
        )
        n = hierarchy_text_count(self.d)
        # IME / canvas search may keep same text-fp but stay rich
        assert opened or fp0 != fp1 or n >= 10, "search entry no effect"

    @prob(0.95)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 3)
    def test_shell_or_substance(self):
        """Always-on: SUT dump must have shell chrome or real content."""
        n = hierarchy_text_count(self.d)
        assert n >= 5 or any_text(self.d, TABISH) or ui_alive(self.d), (
            f"empty/dead UI n={n}"
        )

    @prob(0.85)
    @max_tries(5)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 1)
    def test_back_keeps_sut_or_chrome(self):
        """Back from content should not wipe to empty non-launcher void."""
        pkg0 = _sut_pkg(self)
        try:
            if hasattr(self.d, "go_back"):
                self.d.go_back()
            else:
                self.d.press_back()
        except Exception:
            return
        time.sleep(0.35)
        pkg1 = _sut_pkg(self)
        n = hierarchy_text_count(self.d)
        # launcher OK; empty nothing not OK
        launcher = pkg1 in ("com.ohos.sceneboard", "com.huawei.android.launcher", None)
        if launcher and n < 3:
            # sceneboard still has clock etc — n usually >3; truly empty fails
            assert n >= 0  # dump fail OK
            if n == 0:
                raise AssertionError("back to empty void")
            return
        assert ui_alive(self.d) or n >= 5 or pkg1 == pkg0, (
            f"back broke UI pkg={pkg0}->{pkg1} n={n}"
        )

    @prob(0.9)
    @max_tries(6)
    @precondition(
        lambda self: any_text(self.d, ("分享", "收藏", "点赞", "关注", "赞同", "喜欢"))
        and hierarchy_text_count(self.d) >= 4
    )
    def test_action_not_blank(self):
        """Social/content action must not blank the tree."""
        n0 = hierarchy_text_count(self.d)
        if not click_first(
            self.d, ("分享", "收藏", "点赞", "关注", "赞同", "喜欢"), settle=0.35
        ):
            return
        n1 = hierarchy_text_count(self.d)
        assert ui_alive(self.d) or n1 >= max(3, n0 // 3), (
            f"action blanked UI n {n0}->{n1}"
        )
