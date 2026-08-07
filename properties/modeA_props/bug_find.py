"""Highest-signal Mode A bug finders — prefer catch over silence.

Target classes:
  - nav lands on OS shell (AppGallery/Settings) unexpectedly
  - search yields blank/error with no escape
  - clickable controls are dead (no UI change)
  - error wall without retry
  - tab bar disappears mid-session
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    EMPTY_OR_ERROR,
    LOGINISH,
    TABISH,
    any_text,
    click_first,
    click_xy,
    clickable_nodes,
    count_texts,
    dismiss_noise,
    fg_package,
    hierarchy_fingerprint,
    hierarchy_text_count,
    query_reflected,
    safe_click,
    type_into_search,
    ui_alive,
)

_OS_NOISE = (
    "AppGallery", "Settings", "设置", "Huawei Apps", "Theme Studio",
    "小艺建议", "Celia Suggestions",
)
_TABS = (
    "首页", "推荐", "热榜", "关注", "视频", "发现", "消息", "我的",
    "Home", "Video", "Discover", "Message", "Me", "直答", "社区", "行程",
)
_ERR = ("加载失败", "网络异常", "出错了", "页面异常", "系统繁忙", "加载失败，请重试")
_RETRY = ("重试", "刷新", "点击重试", "重新加载", "刷新页面")


class BugFindProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.99)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 2)
    def test_not_lost_to_os_shell(self):
        """SUT session must not be only OS launcher/AppGallery chrome."""
        pkg = fg_package(self.d)
        if pkg in ("com.ohos.sceneboard", "com.huawei.android.launcher"):
            # brief OK; fail if stuck with only OS markers and no SUT return
            time.sleep(0.5)
            pkg2 = fg_package(self.d)
            if pkg2 in ("com.ohos.sceneboard", "com.huawei.android.launcher", None):
                n = hierarchy_text_count(self.d)
                os_hit = sum(1 for t in _OS_NOISE if any_text(self.d, (t,)))
                if os_hit >= 2 and n < 12:
                    raise AssertionError(f"stuck on OS shell pkg={pkg2} os_hit={os_hit} n={n}")
            return
        # in some app: AppGallery overlay alone is bad
        if pkg and "appgallery" in pkg.lower():
            raise AssertionError(f"navigated to AppGallery pkg={pkg}")
        if any_text(self.d, ("AppGallery",)) and not any_text(self.d, TABISH + _TABS):
            if hierarchy_text_count(self.d) < 8:
                raise AssertionError("AppGallery-only chrome, SUT shell gone")

    @prob(0.95)
    @max_tries(6)
    @precondition(
        lambda self: any_text(self.d, ("搜索", "Search", "搜一搜"))
        and hierarchy_text_count(self.d) >= 5
    )
    def test_search_not_blank_error(self):
        """After search, must not land blank or error-without-retry."""
        click_first(self.d, ("搜索", "Search", "搜一搜"), settle=0.35)
        q = "酒店"
        typed = type_into_search(self.d, q, settle=0.4)
        if typed:
            click_first(self.d, ("搜索", "Search", "确定"), settle=0.4)
        else:
            # still opened search surface?
            if not any_text(self.d, ("取消", "Cancel", "搜索历史", "热门搜索", "清除")):
                return
        time.sleep(0.6)
        n = hierarchy_text_count(self.d)
        err = any_text(self.d, _ERR)
        retry = any_text(self.d, _RETRY)
        if err and not retry:
            raise AssertionError(f"search error without retry n={n}")
        if n < 4 and not query_reflected(self.d, q):
            raise AssertionError(f"search blank n={n}")
        # success paths: query echo, results-ish, or cancel chrome
        if any_text(self.d, LOGINISH + ("+86", "获取验证码", "欢迎来到")):
            return  # login gate OK
        ok = (
            query_reflected(self.d, q)
            or any_text(self.d, ("取消", "Cancel", "搜索历史", "热门搜索", "相关", "结果"))
            or n >= 8
            or retry
        )
        assert ok, f"search dead-end n={n}"

    @prob(0.92)
    @max_tries(8)
    @precondition(lambda self: len(clickable_nodes(self.d)) >= 3)
    def test_clickable_has_effect(self):
        """Tap a mid-screen clickable; UI fingerprint should change or stay rich."""
        nodes = clickable_nodes(self.d)
        if len(nodes) < 2:
            return
        # prefer mid-body nodes; skip status bar / nav edges (system sheet FPs)
        body = []
        for b, a in nodes:
            cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
            if 180 <= cy <= 1750 and 40 <= cx <= 1040:
                body.append((b, a, cx, cy))
        if not body:
            return
        b, a, cx, cy = body[len(body) // 2]
        fp0 = hierarchy_fingerprint(self.d)
        pkg0 = fg_package(self.d)
        if not click_xy(self.d, cx, cy, settle=0.4):
            return
        fp1 = hierarchy_fingerprint(self.d)
        pkg1 = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        # left SUT to home/status-bar chrome — explore noise, not product dead-click
        if any_text(self.d, ("Drag here", "拖到此处", "控制中心")):
            return
        if pkg1 and pkg0 and pkg1 != pkg0:
            if "appgallery" in (pkg1 or "").lower():
                raise AssertionError(f"clickable opened AppGallery {pkg0}->{pkg1}")
            if pkg1 in ("com.ohos.sceneboard", "com.huawei.android.launcher") and n < 8:
                raise AssertionError(f"clickable dumped to launcher n={n}")
            # other apps / system sheets after random mid-tap — skip
            return
        # dead click: same fp and became thin (skip bottom nav / edge)
        if fp0 == fp1 and n < 6:
            if cy > 1900:  # B6: bottom-nav dead-zone FP
                return
            raise AssertionError(f"dead clickable cx={cx} cy={cy} n={n}")
        # soft OK if rich same (toggle)
        assert fp0 != fp1 or n >= 8 or ui_alive(self.d), (
            f"clickable no effect cx={cx} cy={cy} n={n}"
        )

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: any_text(self.d, _ERR))
    def test_error_offers_escape(self):
        """Visible error must offer retry/back/close — not hard wall."""
        if any_text(self.d, _RETRY + ("返回", "关闭", "取消", "知道了", "Back", "Cancel")):
            return
        # error text in feed copy? require also low chrome
        if hierarchy_text_count(self.d) >= 20 and any_text(self.d, TABISH):
            return  # likely false "加载失败" in content
        raise AssertionError("error wall without retry/back/close")

    @prob(0.95)
    @max_tries(6)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 2)
    def test_tab_bar_survives_hop(self):
        """After hopping to another tab, tab bar (or rich shell) still there."""
        tabs = [t for t in _TABS if self.d(text=t).exists()]
        if len(tabs) < 2:
            return
        target = tabs[1]
        pkg0 = fg_package(self.d)
        if not safe_click(self.d, target, settle=0.4):
            return
        n = hierarchy_text_count(self.d)
        tabs_after = count_texts(self.d, _TABS)
        pkg1 = fg_package(self.d)
        if pkg1 and pkg0 and pkg1 != pkg0 and "appgallery" in pkg1.lower():
            raise AssertionError(f"tab hop to gallery {pkg0}->{pkg1}")
        assert tabs_after >= 1 or n >= 10 or ui_alive(self.d), (
            f"tab bar gone after →{target} tabs={tabs_after} n={n}"
        )


    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: count_texts(self.d, _TABS) >= 1 and hierarchy_text_count(self.d) >= 8)
    def test_back_restores_tabs(self):
        """Open something then back; tabs/shell should remain or return."""
        pkg0 = fg_package(self.d)
        # dive: search or secondary
        click_first(self.d, ("搜索", "消息", "我的", "Me", "Message", "Video"), settle=0.35)
        try:
            if hasattr(self.d, "go_back"):
                self.d.go_back()
            else:
                self.d.press_back()
        except Exception:
            return
        time.sleep(0.35)
        n = hierarchy_text_count(self.d)
        pkg1 = fg_package(self.d)
        if pkg1 and pkg0 and pkg1 != pkg0 and pkg1 in ("com.ohos.sceneboard",):
            # back to launcher once is OK
            return
        assert (
            count_texts(self.d, _TABS) >= 1
            or any_text(self.d, TABISH)
            or n >= 4
            or ui_alive(self.d)
            or (pkg1 is None and n >= 2)  # FG flicker
        ), f"back lost shell n={n}"


    @prob(0.9)
    @max_tries(4)
    @precondition(
        lambda self: any_text(self.d, ("加载中", "正在加载", "Loading", "请稍候", "加载中..."))
        and hierarchy_text_count(self.d) < 12
    )
    def test_loading_not_eternal(self):
        """Loading-only chrome must clear within ~3s."""
        time.sleep(1.2)
        still = any_text(self.d, ("加载中", "正在加载", "Loading", "请稍候", "加载中..."))
        n = hierarchy_text_count(self.d)
        if still and n < 8 and not any_text(self.d, _RETRY + TABISH + _TABS):
            raise AssertionError(f"eternal loading n={n}")

    @prob(0.93)
    @max_tries(5)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 8)
    def test_no_white_screen_after_tap(self):
        """After tapping a content-ish clickable, must not go blank 1.5s."""
        nodes = clickable_nodes(self.d)
        if len(nodes) < 3:
            return
        # prefer lower half content (not tabs)
        pick = None
        for b, a in nodes:
            cy = (b[1] + b[3]) // 2
            if 400 < cy < 1400:
                pick = b
                break
        if not pick:
            pick = nodes[len(nodes)//2][0]
        cx, cy = (pick[0]+pick[2])//2, (pick[1]+pick[3])//2
        pkg0 = fg_package(self.d)
        if not click_xy(self.d, cx, cy, settle=0.4):
            return
        n = hierarchy_text_count(self.d)
        pkg1 = fg_package(self.d)
        if n < 3 and pkg1 not in ("com.ohos.sceneboard",):
            time.sleep(0.4)
            n = hierarchy_text_count(self.d)
            if n < 3:
                raise AssertionError(f"white screen after tap n={n} pkg={pkg0}->{pkg1}")


    @prob(0.96)
    @precondition(lambda self: hierarchy_text_count(self.d) >= 2)
    def test_cta_or_content_alive(self):
        """Always-on: must have clickable OR enough text (dead process UI)."""
        n = hierarchy_text_count(self.d)
        clicks = len(clickable_nodes(self.d))
        if n < 3 and clicks < 1:
            raise AssertionError(f"dead UI n={n} clickables={clicks}")
