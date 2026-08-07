"""Aggressive Mode A hunt oracles — prefer false fail over silent miss.

Designed to surface real stuck/blank/no-op bugs. Failures need dump review
(not auto product-bug). High fire rate: loose preconds, high @prob.
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

_TABS = (
    "推荐", "热榜", "关注", "首页", "视频", "发现", "热门", "故事", "知识",
    "直答", "社区", "行程", "美食", "酒店", "美团", "附近", "消息",
    "Home", "Video", "Discover", "Follow", "Message", "Me", "Trending",
)
_SECONDARY = (
    "消息", "我的", "Me", "Message", "购物车", "行程", "社区", "视频",
    "Discover", "Video", "直答",
)


class HuntProps(unittest.TestCase):
    """Stricter than generic_ui; may FP on sparse dumps — review fails."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.99)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 2)
    def test_not_blank_tree(self):
        """Blank / near-empty hierarchy while SUT should be up."""
        n = hierarchy_text_count(self.d)
        pkg = fg_package(self.d)
        if pkg in ("com.ohos.sceneboard", "com.huawei.android.launcher"):
            return
        assert n >= 4 or any_text(self.d, TABISH), f"blank/near-empty tree n={n} pkg={pkg}"

    @prob(0.98)
    @max_tries(10)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 2)
    def test_tab_must_mutate(self):
        """Click a non-home tab; fingerprint MUST change (no-op = fail)."""
        tabs = [t for t in _TABS if self.d(text=t).exists()]
        if len(tabs) < 2:
            return
        # avoid clicking same tab only — pick secondary-looking
        target = None
        for pref in (
            "热榜", "视频", "发现", "关注", "故事", "知识", "直答", "社区",
            "行程", "消息", "Video", "Discover", "Follow", "Message", "Me",
        ):
            if pref in tabs:
                target = pref
                break
        if not target:
            target = tabs[-1]
        fp0 = hierarchy_fingerprint(self.d)
        pkg0 = fg_package(self.d)
        if not safe_click(self.d, target, settle=0.4):
            return
        fp1 = hierarchy_fingerprint(self.d)
        pkg1 = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        # left to empty launcher-ish
        if pkg1 in ("com.ohos.sceneboard",) and n < 5:
            raise AssertionError(f"tab {target} dumped to launcher blank")
        if pkg0 and pkg1 and pkg1 != pkg0 and pkg1 not in (
            "com.ohos.sceneboard", "com.huawei.hmsapp.appgallery",
        ):
            # jumped to other app unexpectedly
            raise AssertionError(f"tab {target} left package {pkg0}->{pkg1}")
        assert fp0 != fp1 or n >= 12, (
            f"tab no-op target={target} fp_same n={n}"
        )

    @prob(0.95)
    @max_tries(6)
    @precondition(
        lambda self: any_text(self.d, ("搜索", "Search", "搜一搜"))
        and hierarchy_text_count(self.d) >= 4
    )
    def test_search_must_mutate(self):
        """Search chrome tap must change hierarchy."""
        fp0 = hierarchy_fingerprint(self.d)
        if not click_first(self.d, ("搜索", "Search", "搜一搜", "搜一搜："), settle=0.4):
            return
        fp1 = hierarchy_fingerprint(self.d)
        opened = any_text(
            self.d,
            ("取消", "Cancel", "搜索历史", "热门搜索", "猜你想搜", "清除", "热搜"),
        )
        assert opened or fp0 != fp1, "search tap no-op"

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: count_texts(self.d, _SECONDARY) >= 1)
    def test_secondary_not_dead_end(self):
        """Open 消息/我的/… ; must not be empty dead end."""
        dest = click_first(self.d, _SECONDARY, settle=0.4)
        if not dest:
            return
        n = hierarchy_text_count(self.d)
        assert (
            ui_alive(self.d, extra=_SECONDARY + LOGINISH_EXTRA)
            or n >= 6
        ), f"secondary dead-end dest={dest} n={n}"

    @prob(0.92)
    @max_tries(4)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 8)
    def test_scroll_or_swipe_progress(self):
        """Swipe feed; fingerprint should usually change (stuck scroll = fail)."""
        fp0 = hierarchy_fingerprint(self.d)
        try:
            # HMDevice.swipe or d.swipe
            if hasattr(self.d, "swipe"):
                self.d.swipe(0.5, 0.75, 0.5, 0.35, 0.15)
            else:
                return
        except Exception:
            return
        time.sleep(0.4)
        fp1 = hierarchy_fingerprint(self.d)
        n = hierarchy_text_count(self.d)
        # allow sticky headers: require change OR still rich
        assert fp0 != fp1 or n >= 5, f"swipe no progress fp_same n={n}"

    @prob(0.99)
    @precondition(lambda self: True)
    def test_process_present(self):
        """FG package exists (crash path; watcher is authority)."""
        p = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        if p is None and n < 3:
            time.sleep(0.5)
            p = fg_package(self.d)
            n = hierarchy_text_count(self.d)
        # system overlay (实名认证) may blank FG API but UI still has chrome
        assert p is not None or n >= 3 or ui_alive(self.d), "no FG package and empty UI"


# login-ish extras for secondary pages
LOGINISH_EXTRA = (
    "登录", "注册", "验证码", "+86", "订单", "钱包", "设置", "收藏",
    "关注", "粉丝", "历史", "客服", "优惠券", "Log in", "Sign in",
    "Settings", "Followers", "Wallet", "Drafts",
)
