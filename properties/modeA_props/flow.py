"""App-flow oracles — package-aware paths that can catch product bugs.

Lean preconds: only fire when SUT package matches. Prefer FAIL on broken
search results / blank detail / lost cart chrome over soft chrome-alive.
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

# package → preferred search query
_PKG_Q = {
    "com.sankuai.dianping": "火锅",
    "com.ctrip.harmonynext": "北京",
    "com.amap.hmapp": "加油站",
    "com.sina.weibo.stage": "热搜",
    "com.taobao.idlefish4ohos": "手机",
}
_EMPTY_OK = (
    "暂无", "没有找到", "无结果", "未找到", "换个词", "空空如也",
    "No results", "nothing found", "试试其他",
)
_RESULTISH = (
    "相关", "结果", "条", "家", "元", "¥", "评分", "km", "公里",
    "酒店", "门票", "机票", "路线", "导航", "想买", "想要", "人想要",
    "转发", "评论", "赞", "收藏", "距离", "营业",
)
_ERR = ("加载失败", "网络异常", "出错了", "页面异常", "系统繁忙")
_RETRY = ("重试", "刷新", "点击重试", "重新加载")


def _pkg(d):
    return fg_package(d) or ""


def _is_target(d) -> bool:
    p = _pkg(d)
    return any(k in p for k in _PKG_Q)


class FlowProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.97)
    @max_tries(8)
    @precondition(
        lambda self: _is_target(self.d)
        and any_text(self.d, ("搜索", "Search", "搜一搜"))
        and hierarchy_text_count(self.d) >= 4
    )
    def test_search_yields_results_or_empty(self):
        """After typed search: results chrome OR empty-state OR error+retry — not blank."""
        pkg = _pkg(self.d)
        q = next((v for k, v in _PKG_Q.items() if k in pkg), "测试")
        click_first(self.d, ("搜索", "Search", "搜一搜"), settle=0.35)
        if not type_into_search(self.d, q, settle=0.4):
            return
        click_first(self.d, ("搜索", "Search", "确定", "完成"), settle=0.4)
        time.sleep(0.35)
        if any_text(self.d, LOGINISH + ("+86", "获取验证码", "欢迎来到")):
            return
        n = hierarchy_text_count(self.d)
        err = any_text(self.d, _ERR)
        retry = any_text(self.d, _RETRY)
        if err and not retry:
            raise AssertionError(f"search error no retry pkg={pkg} q={q} n={n}")
        ok = (
            query_reflected(self.d, q)
            or any_text(self.d, _RESULTISH + _EMPTY_OK)
            or retry
            or n >= 10
        )
        assert ok, f"search blank/dead pkg={pkg} q={q} n={n}"

    @prob(0.93)
    @max_tries(6)
    @precondition(
        lambda self: _is_target(self.d) and hierarchy_text_count(self.d) >= 10
    )
    def test_open_detail_not_blank(self):
        """Tap mid-content clickable → detail/sheet must not be white/empty."""
        nodes = clickable_nodes(self.d)
        pick = None
        for b, a in nodes:
            cy = (b[1] + b[3]) // 2
            h = b[3] - b[1]
            w = b[2] - b[0]
            # mid content card-ish
            if 350 < cy < 1600 and h > 80 and w > 200:
                pick = b
                break
        if not pick:
            return
        cx, cy = (pick[0] + pick[2]) // 2, (pick[1] + pick[3]) // 2
        pkg0 = _pkg(self.d)
        fp0 = hierarchy_fingerprint(self.d)
        if not click_xy(self.d, cx, cy, settle=0.4):
            return
        n = hierarchy_text_count(self.d)
        pkg1 = _pkg(self.d)
        if pkg1 and "appgallery" in pkg1.lower():
            raise AssertionError(f"detail opened AppGallery {pkg0}->{pkg1}")
        if n < 3:
            time.sleep(0.4)
            n = hierarchy_text_count(self.d)
            if n < 3 and pkg1 not in ("com.ohos.sceneboard", ""):
                raise AssertionError(f"blank detail n={n} pkg={pkg1}")
        # if still same home fp and thin — soft skip
        if hierarchy_fingerprint(self.d) == fp0 and n < 6:
            return
        # amap profile: 关注/粉丝/获赞 present but walker n can be 3
        assert (
            n >= 3
            or ui_alive(self.d)
            or any_text(self.d, ("关注", "粉丝", "获赞", "评价", "详情", "返回"))
        ), f"detail dead n={n}"

    @prob(0.9)
    @max_tries(5)
    @precondition(
        lambda self: _is_target(self.d)
        and any_text(self.d, TABISH)
        and hierarchy_text_count(self.d) >= 6
    )
    def test_me_page_not_crash_blank(self):
        """我的/Me entry must show profile/login chrome — not blank crash."""
        if not click_first(self.d, ("我的", "Me", "我", "个人中心"), settle=0.4):
            return
        n = hierarchy_text_count(self.d)
        ok = (
            any_text(
                self.d,
                LOGINISH
                + (
                    "设置", "订单", "收藏", "钱包", "客服", "编辑资料",
                    "Settings", "Orders", "Wallet", "关注", "粉丝",
                    "闲鱼币", "优惠券", "足迹",
                ),
            )
            or n >= 8
            or ui_alive(self.d)
        )
        assert ok, f"me page blank/crash n={n} pkg={_pkg(self.d)}"

    @prob(0.88)
    @max_tries(4)
    @precondition(
        lambda self: "amap" in _pkg(self.d) or "ctrip" in _pkg(self.d)
    )
    def test_map_travel_search_alive(self):
        """高德/携程: search entry stays interactive (map canvas sparse OK if chrome)."""
        if not click_first(self.d, ("搜索", "Search", "搜一搜"), settle=0.4):
            return
        n = hierarchy_text_count(self.d)
        ok = (
            any_text(self.d, ("取消", "Cancel", "历史", "热门", "清除", "目的地", "城市"))
            or n >= 4
            or ui_alive(self.d)
        )
        assert ok, f"map/travel search dead n={n}"

    @prob(0.9)
    @max_tries(5)
    @precondition(
        lambda self: _is_target(self.d) and hierarchy_text_count(self.d) >= 5
    )
    def test_double_back_not_void(self):
        """Two backs must not land empty void (non-launcher)."""
        pkg0 = _pkg(self.d)
        for _ in range(2):
            try:
                if hasattr(self.d, "go_back"):
                    self.d.go_back()
                else:
                    self.d.press_back()
            except Exception:
                return
            time.sleep(0.55)
        n = hierarchy_text_count(self.d)
        pkg1 = _pkg(self.d)
        if pkg1 in ("com.ohos.sceneboard", "com.huawei.android.launcher"):
            return
        assert n >= 3 or ui_alive(self.d) or any_text(self.d, TABISH), (
            f"double-back void n={n} pkg={pkg0}->{pkg1}"
        )


    @prob(0.97)
    @max_tries(8)
    @precondition(
        lambda self: _is_target(self.d)
        and count_texts(self.d, (
            "首页", "推荐", "热榜", "关注", "视频", "发现", "消息", "我的",
            "Home", "Video", "Discover", "Message", "Me", "行程", "社区",
            "酒店", "机票", "门票", "火车票", "旅游", "攻略", "订单",
        )) >= 2
    )
    def test_two_tabs_differ(self):
        """Two different tabs must not show identical content fingerprint."""
        tabs = [
            t for t in (
                "首页", "推荐", "热榜", "关注", "视频", "发现", "消息", "我的",
                "Home", "Video", "Discover", "Message", "Me", "行程", "社区",
                "酒店", "机票", "门票", "火车票", "旅游", "攻略", "订单",
            )
            if self.d(text=t).exists()
        ]
        if len(tabs) < 2:
            return
        # prefer bottom-nav-ish labels; skip category chips alone
        prefer = [t for t in tabs if t in (
            "首页", "消息", "我的", "我", "发现", "视频", "闲鱼", "会玩", "会员",
            "Home", "Message", "Me", "Discover", "Video", "Follow",
        )]
        if len(prefer) >= 2:
            tabs = prefer
        # pick two distinct roles when possible (home vs me/message)
        role_me = [t for t in tabs if t in ("我的", "我", "Me", "消息", "Message")]
        role_home = [t for t in tabs if t in ("首页", "Home", "发现", "Discover", "视频", "Video")]
        if role_me and role_home:
            a, b = role_home[0], role_me[0]
        else:
            a, b = tabs[0], tabs[1]
        if a == b:
            return
        if not safe_click(self.d, a, settle=0.4):
            return
        # location / city dialog blocks tab hop — not a product tab bug
        if any_text(self.d, ("当前定位", "切换到", "开启定位", "定位服务")):
            return
        fp_a = hierarchy_fingerprint(self.d)
        na = hierarchy_text_count(self.d)
        if not safe_click(self.d, b, settle=0.4):
            return
        if any_text(self.d, ("当前定位", "切换到", "开启定位", "定位服务")):
            return
        fp_b = hierarchy_fingerprint(self.d)
        nb = hierarchy_text_count(self.d)
        # feed tabs often share chrome; only flag near-identical rich trees
        if fp_a == fp_b and na >= 20 and nb >= 20:
            raise AssertionError(f"tabs identical content {a!r}/{b!r} n={na}")
        assert na >= 3 and nb >= 3, f"tab blank {a}={na} {b}={nb}"

    @prob(0.92)
    @max_tries(5)
    @precondition(
        lambda self: _is_target(self.d)
        and any_text(self.d, ("搜索", "Search", "搜一搜"))
    )
    def test_search_submit_not_hard_error(self):
        """Submit search; hard error without retry is a product bug signal."""
        pkg = _pkg(self.d)
        q = next((v for k, v in _PKG_Q.items() if k in pkg), "测试")
        click_first(self.d, ("搜索", "Search", "搜一搜"), settle=0.35)
        if not type_into_search(self.d, q, settle=0.4):
            return
        click_first(self.d, ("搜索", "Search", "确定", "完成"), settle=0.4)
        time.sleep(0.7)
        if any_text(self.d, LOGINISH + ("+86", "获取验证码", "欢迎来到")):
            return
        if any_text(self.d, _ERR) and not any_text(self.d, _RETRY):
            raise AssertionError(f"search hard error no retry pkg={pkg} q={q}")
        n = hierarchy_text_count(self.d)
        assert n >= 3 or ui_alive(self.d), f"search submit blank n={n}"

    @prob(0.9)
    @max_tries(4)
    @precondition(lambda self: _is_target(self.d) and hierarchy_text_count(self.d) >= 6)
    def test_swipe_keeps_sut(self):
        """Feed swipe must not eject to launcher/AppGallery."""
        pkg0 = _pkg(self.d)
        try:
            if hasattr(self.d, "swipe"):
                self.d.swipe(0.5, 0.72, 0.5, 0.32, 0.14)
            else:
                return
        except Exception:
            return
        time.sleep(0.35)
        pkg1 = _pkg(self.d)
        n = hierarchy_text_count(self.d)
        if pkg1 and "appgallery" in pkg1.lower():
            raise AssertionError(f"swipe opened gallery {pkg0}->{pkg1}")
        if pkg1 in ("com.ohos.sceneboard",) and n < 6:
            raise AssertionError(f"swipe dumped launcher n={n}")
        assert n >= 3 or ui_alive(self.d), f"swipe blank n={n} pkg={pkg1}"
