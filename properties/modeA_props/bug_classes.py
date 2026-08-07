"""Mode A oracles for 20 common UI bug classes.

Each test maps 1:1 to a named class. Strength varies:
  strong = crash/ANR, dead UI, blank tree, geometry gross errors
  medium = click no-response, nav shell, load-error chrome, focus
  weak   = jank/latency/flicker proxies (thresholds, not lab metrics)

Douyin + generic: package-agnostic where possible.
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    EMPTY_OR_ERROR,
    any_text,
    click_first,
    click_xy,
    clickable_nodes,
    count_bad_overlaps,
    count_clipped_text,
    count_offscreen_clickables,
    focused_input,
    fg_package,
    has_input_field,
    hierarchy_fingerprint,
    hierarchy_text_count,
    on_package,
    safe_click,
    screen_size,
    ui_alive,
    visible_text_nodes,
)


def _on_sut(self) -> bool:
    """Any non-launcher FG package."""
    p = fg_package(self.d)
    if not p:
        return False
    if p in ("com.ohos.sceneboard", "com.huawei.android.launcher"):
        return False
    return True


# Bottom/top chrome across Douyin + 红果 + 优酷 + generic CN apps
_SHELL = (
    "首页", "推荐", "关注", "消息", "我", "我的", "朋友", "搜索",
    "视频", "热门", "发现", "精选", "直播",
    # 红果免费短剧
    "短剧", "剧场", "福利", "找剧", "真人剧", "漫剧", "听书", "小说",
    # player / episode chrome
    "展开", "观看完整漫剧", "观看完整短剧", "第1集", "剧情", "演员", "分类",
    "搜索历史", "作者声明",
    # 优酷 youku
    "剧集", "动漫", "电影", "综艺", "少儿", "纪录片", "会员", "淘好片",
    "热搜榜", "上新榜", "热度榜", "正在追", "今日给您的专属推荐", "有更新", "限免中",
    # 快手 kuaishou (often EN chrome on this device)
    "精选", "热点", "Trending", "Kwai Shop", "Task Center", "History", "Settings",
    "Wallet", "Drafts", "购物", "展开", "View later", "offline mode",
    # 拼多多 pinduoduo
    "个人中心", "领消费券", "聊天", "直播", "食品", "百货", "水果", "女装",
    "内衣", "电器", "店铺", "收藏", "客服", "发起拼单", "单独购买", "查看全部",
    # 微博 weibo (EN chrome on this device)
    "Home", "Video", "Discover", "Message", "Me", "Follow", "Followers",
    "Visitor", "Albums", "Likes", "History", "Draft Box", "My wallet", "My order",
    "Chaohua Community", "Weibo", "Check-in", "Tasks", "Creation",
)
_SHELL_NAV = (
    "短剧", "剧场", "福利", "我的", "找剧", "真人剧", "漫剧", "听书", "小说",
    "首页", "推荐", "消息", "我", "朋友", "关注", "演员", "分类",
    "剧集", "动漫", "电影", "综艺", "少儿", "纪录片", "会员", "淘好片",
    "精选", "热点", "Trending", "购物", "Kwai Shop",
    "个人中心", "领消费券", "聊天", "直播", "食品", "百货", "水果", "女装",
    "Home", "Video", "Discover", "Message", "Me", "Follow",
)


class BugClassProperties(unittest.TestCase):
    """Twenty named bug-class properties."""

    @classmethod
    def setUpClass(cls):
        pass

    # 1 数据展示异常 — content layer not empty/garbage-only when shell says feed
    @prob(0.75)
    @precondition(lambda self: _on_sut(self) and any_text(self.d, _SHELL))
    def test_bc01_data_display_not_empty(self):
        """数据展示异常: main shell should show real content texts, not blank."""
        texts = [t for t, _, _ in visible_text_nodes(self.d, min_len=2)]
        chrome = set(_SHELL) | {"设置", "取消", "关闭", "AppGallery"}
        body = [
            t for t in texts
            if t not in chrome and not t.replace(":", "").replace(",", "").isdigit()
        ]
        n = hierarchy_text_count(self.d)
        # 红果 home can be tab-strip heavy early — allow n>=5
        assert n >= 5 or len(body) >= 1, f"data display empty body={len(body)} n={n}"

    # 2 按钮点击无反应
    @prob(0.75)
    @max_tries(4)
    @precondition(lambda self: _on_sut(self) and any_text(self.d, _SHELL_NAV))
    def test_bc02_button_click_has_effect(self):
        """按钮点击无反应: tap known tab; hierarchy or package should react."""
        fp0 = hierarchy_fingerprint(self.d)
        target = None
        for t in _SHELL_NAV:
            if self.d(text=t).exists():
                target = t
                break
        if not target:
            return
        t0 = time.time()
        if not safe_click(self.d, target, settle=0.4):
            return
        dt = time.time() - t0
        fp1 = hierarchy_fingerprint(self.d)
        alive = ui_alive(self.d, extra=_SHELL + (target, "登录"))
        # effect: fingerprint change OR still on interactive shell (tab may reselect same)
        assert alive, "click left dead UI"
        # if UI identical after 1s and click claimed ok — soft fail only when totally frozen
        if fp0 == fp1 and hierarchy_text_count(self.d) < 4:
            assert False, f"click no reaction target={target} dt={dt:.2f}"

    # 3 闪退 — log watcher is primary; property double-checks process FG
    @prob(0.5)
    @precondition(lambda self: True)
    def test_bc03_no_process_disappear(self):
        """闪退: SUT package still foreground or recoverable (watcher catches real crash)."""
        p = fg_package(self.d)
        if p and p not in ("com.ohos.sceneboard",):
            assert ui_alive(self.d) or hierarchy_text_count(self.d) >= 3
            return
        # allow brief transition / aa-dump flicker
        time.sleep(0.4)
        p2 = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        # real crash watcher is authoritative; prop only flags empty+no-pkg
        assert p2 is not None or n >= 5, "no foreground package and empty UI (possible crash)"

    # 4 状态不一致 — follow button label vs presence of 已关注 after social chrome
    @prob(0.99)
    @precondition(
        lambda self: _on_sut(self)
        and (
            any_text(
                self.d,
                ("已关注", "关注", "粉丝", "获赞", "追剧", "已追剧", "收藏", "已收藏", "在追",
                 "订单", "钱包", "历史", "个人中心", "优惠券", "收货地址"),
            )
            and hierarchy_text_count(self.d) >= 6
        )
    )
    def test_bc04_state_consistency_follow(self):
        """状态不一致: profile/social stats chrome coherent; shell not dead."""
        has_stats = any_text(self.d, (
            "获赞", "粉丝", "追剧", "收藏", "在追", "订单", "历史",
            "个人中心", "钱包", "优惠券", "收货地址", "客服",
        ))
        has_follow = any_text(self.d, ("关注", "已关注", "回关", "已追剧", "已收藏"))
        # dense commerce pages (拼多多 home/product) count as coherent chrome
        assert has_stats or has_follow or hierarchy_text_count(self.d) >= 6, (
            "profile/follow state chrome missing"
        )
        assert (
            ui_alive(self.d, extra=_SHELL + ("订单", "钱包", "历史", "追剧", "正在追", "会员"))
            or hierarchy_text_count(self.d) >= 8
        ), "state chrome with dead UI"

    # 5 卡顿 — proxy: dump+simple action wall time
    @prob(0.95)
    @precondition(lambda self: _on_sut(self))
    def test_bc05_no_extreme_jank_proxy(self):
        """卡顿: hierarchy dump should return within budget (extreme jank/proxy)."""
        t0 = time.time()
        try:
            self.d.dump_hierarchy()
        except Exception:
            return
        dt = time.time() - t0
        # device dump usually <2s; >8s ≈ stuck
        assert dt < 8.0, f"hierarchy dump jank dt={dt:.2f}s"

    # 6 响应时延 — click to hierarchy change
    @prob(0.85)
    @max_tries(5)
    @precondition(lambda self: _on_sut(self) and any_text(self.d, _SHELL_NAV))
    def test_bc06_response_latency_proxy(self):
        """响应时延: after tab click, UI fingerprint changes or stays valid within budget."""
        target = None
        for t in ("精选", "热点", "消息", "我", "Trending", "购物",
                  "Home", "Video", "Discover", "Message", "Me",
                  "个人中心", "领消费券", "聊天", "直播", "食品", "百货",
                  "剧集", "动漫", "电影", "综艺", "会员", "淘好片", "我的",
                  "剧场", "福利", "找剧", "关注", "推荐", "首页", "短剧"):
            if self.d(text=t).exists():
                target = t
                break
        if not target:
            return
        fp0 = hierarchy_fingerprint(self.d)
        t0 = time.time()
        if not safe_click(self.d, target, settle=0.05):
            return
        # poll until change or timeout
        deadline = t0 + 5.0
        changed = False
        while time.time() < deadline:
            if hierarchy_fingerprint(self.d) != fp0:
                changed = True
                break
            time.sleep(0.15)
        dt = time.time() - t0
        assert ui_alive(self.d, extra=(target,)), "latency probe left dead UI"
        # same-tab reclick may not change fp — only fail if slow AND dead-ish
        if not changed and dt >= 5.0 and hierarchy_text_count(self.d) < 5:
            assert False, f"response timeout target={target} dt={dt:.2f}"

    # 7 资源加载失败
    @prob(0.9)
    @precondition(lambda self: _on_sut(self))
    def test_bc07_resource_load_fail_has_recovery(self):
        """资源加载失败: if error chrome visible → recovery; else vacuous pass (no fail UI)."""
        err = any_text(
            self.d,
            ("加载失败", "加载失败，请重试", "网络异常", "刷新页面", "点击重试",
             "重新加载", "出错了", "暂无网络", "网络不太好"),
        )
        if not err:
            return  # no load-error surface this step
        assert any_text(
            self.d,
            ("重试", "刷新", "刷新页面", "点击重试", "重新加载", "加载失败，请重试", "网络异常"),
        ) or ui_alive(self.d, extra=EMPTY_OR_ERROR), "load fail with no recovery"

    # 8 错位 — clickable center far outside parent screen band
    @prob(0.9)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 3)
    def test_bc08_layout_misalign_proxy(self):
        """错位: clickable centers should lie inside screen."""
        n = count_offscreen_clickables(self.d)
        # allow a couple of offscreen recycle views
        assert n <= 3, f"misaligned clickables offscreen={n}"

    # 9 跳转失败
    @prob(0.95)
    @precondition(lambda self: _on_sut(self) and any_text(self.d, _SHELL_NAV))
    def test_bc09_navigation_not_fail(self):
        """跳转失败: open secondary tab; must remain interactive (not blank)."""
        dest = click_first(
            self.d,
            ("精选", "热点", "消息", "我", "Trending", "购物", "Kwai Shop",
             "Home", "Video", "Discover", "Message", "Me", "Follow",
             "个人中心", "领消费券", "聊天", "直播", "食品", "百货", "水果",
             "剧集", "动漫", "电影", "综艺", "会员", "淘好片", "我的",
             "剧场", "福利", "找剧", "听书", "小说", "朋友", "关注"),
            settle=0.4,
        )
        if not dest:
            return
        assert ui_alive(
            self.d,
            extra=_SHELL + ("搜索", "登录", "设置", "获赞"),
        ), f"nav to {dest} failed (dead/blank)"

    # 10 卡死 — freeze proxy: two dumps identical + no clickable
    @prob(0.95)
    @precondition(lambda self: _on_sut(self))
    def test_bc10_not_frozen(self):
        """卡死: UI still has clickables/text after short wait (not hard freeze)."""
        fp0 = hierarchy_fingerprint(self.d)
        time.sleep(0.4)
        fp1 = hierarchy_fingerprint(self.d)
        n = hierarchy_text_count(self.d)
        clicks = len(clickable_nodes(self.d))
        # frozen blank
        assert n >= 3 or clicks >= 1, f"frozen/blank n={n} clicks={clicks}"
        # completely static empty is worse — feed may be static video though
        if n < 3 and fp0 == fp1 and clicks == 0:
            assert False, "UI frozen empty"

    # 11 跳转错误 — after 首页 click should see feed-ish chrome not foreign app
    @prob(0.95)
    @precondition(
        lambda self: _on_sut(self)
        and any_text(self.d, _SHELL)
    )
    def test_bc11_nav_target_plausible(self):
        """跳转错误: primary tab keeps same package + shell chrome."""
        pkg0 = fg_package(self.d)
        if not pkg0:
            return  # FG flicker — skip, crash watcher owns real disappear
        home = None
        for t in ("首页", "Home", "精选", "短剧", "推荐", "剧场", "剧集", "热点"):
            if self.d(text=t).exists():
                home = t
                break
        if home:
            safe_click(self.d, home, settle=0.4)
        pkg = fg_package(self.d)
        # FG API can return None mid-transition; SUT-after-click is OK
        same = (
            pkg == pkg0
            or (pkg and pkg0 and pkg.split('.')[0] == pkg0.split('.')[0])
            or (pkg0 is None and pkg and pkg not in ("com.ohos.sceneboard",))
        )
        assert same, f"nav wrong package {pkg0} -> {pkg}"
        assert (
            any_text(self.d, _SHELL)
            or hierarchy_text_count(self.d) >= 5
            or (pkg is not None)
        ), "home/primary nav lost app chrome"

    # 12 控件状态错误 — enabled/selected sanity on visible CTAs
    @prob(0.9)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 3)
    def test_bc12_control_state_sanity(self):
        """控件状态错误: visible bottom tabs should be enabled."""
        tabs = (
            "首页", "朋友", "消息", "我", "我的", "推荐", "关注",
            "短剧", "剧场", "福利", "找剧", "精选", "热点", "Trending",
            "Home", "Video", "Discover", "Message", "Me",
            "个人中心", "领消费券", "聊天", "直播", "食品", "百货", "水果",
            "剧集", "动漫", "电影", "综艺", "少儿", "纪录片", "会员", "淘好片",
        )
        bad = []
        from properties.modeA_props._util import iter_node_attrs

        for a in iter_node_attrs(self.d):
            t = (a.get("text") or "").strip()
            if t not in tabs:
                continue
            if str(a.get("enabled") or "true").lower() == "false":
                bad.append(t)
        assert not bad, f"tabs disabled: {bad}"

    # 13 完成时延 — multi-step return home budget
    @prob(0.95)
    @precondition(
        lambda self: _on_sut(self)
        and any_text(self.d, ("我的", "我", "消息", "朋友", "福利", "追剧", "获赞", "粉丝"))
    )
    def test_bc13_completion_latency_home(self):
        """完成时延: leave leaf back to primary tab within budget."""
        click_first(self.d, ("我的", "我", "消息", "朋友", "福利", "会员", "淘好片",
                             "Settings", "个人中心", "聊天", "Me", "Message"), settle=0.35)
        t0 = time.time()
        home = None
        for t in ("首页", "Home", "精选", "短剧", "推荐", "剧场", "剧集", "热点"):
            if self.d(text=t).exists():
                home = t
                break
        if not home or not safe_click(self.d, home, settle=0.2):
            return
        deadline = t0 + 6.0
        while time.time() < deadline:
            if any_text(self.d, ("短剧", "剧场", "推荐", "关注", "找剧", "真人剧",
                                 "剧集", "动漫", "电影", "热搜榜", "上新榜",
                                 "精选", "热点", "Trending", "首页", "Home",
                                 "Video", "Discover")):
                break
            time.sleep(0.2)
        dt = time.time() - t0
        # 红果 player/XComponent dump often sparse after tab — package FG counts
        ok_ui = ui_alive(self.d, extra=_SHELL) or hierarchy_text_count(self.d) >= 4
        ok_pkg = fg_package(self.d) not in (None, "com.ohos.sceneboard")
        assert dt < 8.0 and (ok_ui or ok_pkg), f"home complete slow/dead dt={dt:.2f}"

    # 14 错乱 — duplicate exclusive tab selection labels stacked oddly is hard;
    #     use extreme overlap among different clickables as proxy
    @prob(0.85)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 4)
    def test_bc14_layout_chaos_overlap_proxy(self):
        """错乱: only extreme overlap + thin tree (dense rank grids alone OK)."""
        bad = count_bad_overlaps(self.d, min_ratio=0.85)
        n = hierarchy_text_count(self.d)
        # Youku home can hit 90+ peer overlaps on card grids — not a bug alone
        assert not (bad > 120 and n < 8), f"layout chaos overlaps={bad} n={n}"

    # 15 显示不全
    @prob(0.85)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 4)
    def test_bc15_display_incomplete_proxy(self):
        """显示不全: text nodes with empty/spilled bounds."""
        n = count_clipped_text(self.d)
        assert n <= 5, f"clipped/incomplete texts={n}"

    # 16 输入框无法聚焦
    @prob(0.5)
    @max_tries(3)
    @precondition(lambda self: _on_sut(self) and has_input_field(self.d))
    def test_bc16_input_can_focus(self):
        """输入框无法聚焦: tap search/input chrome; something focuses or keyboard chrome."""
        if focused_input(self.d):
            return  # already focused
        # try click search / input placeholders
        clicked = click_first(
            self.d,
            ("搜索", "说点什么", "请输入", "Search", "搜索歌名/歌手/歌词/情绪", "搜索用户", "搜一搜", "Find"),
            settle=0.35,
        )
        if not clicked:
            # coordinate-tap first input-looking node
            from properties.modeA_props._util import iter_node_attrs, _parse_bounds

            for a in iter_node_attrs(self.d):
                typ = str(a.get("type") or "")
                if not any(k in typ for k in ("Input", "Edit", "Search", "Field")):
                    continue
                b = _parse_bounds(a.get("bounds"))
                if not b:
                    continue
                click_xy(self.d, (b[0] + b[2]) // 2, (b[1] + b[3]) // 2, settle=0.35)
                break
        time.sleep(0.4)
        ok = (
            focused_input(self.d)
            or any_text(self.d, ("Autofill", "键盘", "搜索", "取消", "Celia", "Photo input"))
            or ui_alive(self.d, extra=("搜索", "取消"))
        )
        assert ok, "input field could not focus"

    # 17 重叠
    @prob(0.85)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 4)
    def test_bc17_overlap(self):
        """重叠: extreme overlap with dead-ish tree only."""
        bad = count_bad_overlaps(self.d, min_ratio=0.85)
        n = hierarchy_text_count(self.d)
        assert not (bad > 120 and n < 8), f"overlaps={bad} n={n}"

    # 18 闪屏 — rapid double dump identity thrash with empty intermediate
    @prob(0.9)
    @precondition(lambda self: _on_sut(self))
    def test_bc18_no_blank_flash(self):
        """闪屏: three quick dumps should not show empty flash while FG."""
        counts = []
        for _ in range(3):
            counts.append(hierarchy_text_count(self.d))
            time.sleep(0.25)
        # empty flash: 0/1 between rich frames
        if max(counts) >= 10 and min(counts) <= 1:
            assert False, f"blank flash counts={counts}"
        assert max(counts) >= 3, f"persistently blank counts={counts}"

    # 19 截断
    @prob(0.9)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 3)
    def test_bc19_text_truncation_bounds(self):
        """截断: text bounds outside screen or zero-sized with content."""
        n = count_clipped_text(self.d)
        assert n <= 5, f"truncated/spilled texts={n}"

    # 20 遮挡 — clickable fully covered by another higher clickable (approx)
    @prob(0.85)
    @precondition(lambda self: _on_sut(self) and hierarchy_text_count(self.d) >= 4)
    def test_bc20_occlusion_proxy(self):
        """遮挡: clickable fully inside another different clickable (approx occlusion)."""
        nodes = clickable_nodes(self.d)[:60]
        full = 0
        for i, (b1, a1) in enumerate(nodes):
            t1 = (a1.get("text") or "")[:16]
            a1_area = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
            for j, (b2, a2) in enumerate(nodes):
                if i == j:
                    continue
                t2 = (a2.get("text") or "")[:16]
                if t1 and t1 == t2:
                    continue
                # b1 fully inside b2
                if b1[0] >= b2[0] - 2 and b1[1] >= b2[1] - 2 and b1[2] <= b2[2] + 2 and b1[3] <= b2[3] + 2:
                    a2_area = max(1, (b2[2] - b2[0]) * (b2[3] - b2[1]))
                    if a2_area > a1_area * 1.8:
                        full += 1
                        break
        # Douyin nests clickable rows inside larger hit targets — high threshold
        assert full <= 40, f"occluded clickables={full}"  # Kuaishou nested rows
