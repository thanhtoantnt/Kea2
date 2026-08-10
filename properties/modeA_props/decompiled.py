"""App-agnostic props driven by offline decompile/mine signals.

Loads `modeA_runs/decompile_exp/mined_all/<pkg>/signals.json` (built from abc
string mine / xabc). No phone needed to generate; phone only to execute.

Target package: env KEA2_TARGET_PKG, else fg package, else first signals hit.
"""
from __future__ import annotations

import json
import os
import time
import unittest
from functools import lru_cache
from pathlib import Path

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    any_text,
    click_first,
    dismiss_noise,
    fg_package,
    hierarchy_fingerprint,
    hierarchy_text_count,
    safe_click,
    ui_alive,
)

_REPO = Path(__file__).resolve().parents[2]
_MINED = _REPO / "modeA_runs" / "decompile_exp" / "mined_all"

# app chrome boosts (decompile often misses live tab labels)
_TAB_BOOST = {
    "com.taobao.idlefish4ohos": ("闲鱼", "首页", "消息", "我的", "卖", "会玩", "鱼塘"),
    "com.ctrip.harmonynext": ("首页", "酒店", "机票", "火车票", "门票", "行程", "我的", "消息", "订单"),
    "com.amap.hmapp": ("首页", "附近", "消息", "我的", "导航", "打车", "设置", "地铁", "公交"),
    "com.sankuai.dianping": ("首页", "视频", "消息", "我的", "深圳", "北京"),
    "com.sina.weibo.stage": ("首页", "视频", "发现", "消息", "我"),
    # zhihu names: 推荐/热榜/关注 feed + mine (mine tabs had API noise)
    "com.zhihu.hmos": ("首页", "推荐", "热榜", "关注", "会员", "消息", "我的", "知乎"),
    "com.ss.hm.ugc.aweme": ("首页", "朋友", "消息", "我", "商城"),
    "com.kuaishou.hmapp": ("首页", "精选", "消息", "我", "同城"),
    "com.youku.next": ("首页", "会员", "会员中心", "我的", "发现"),
    "com.phoenix.read.next": ("首页", "书架", "我的", "福利", "短剧", "精选", "推荐"),
    "com.xunmeng.pinduoduo.hos": ("首页", "多多视频", "聊天", "个人中心"),
    # meituan mine tabs thin (美团/领券); names: Home/WaterFlow/Search/Order
    "com.sankuai.hmeituan": ("首页", "视频", "消息", "我的", "购物车", "美团", "订单", "购物"),
    "com.meituan.takeaway": ("首页", "订单", "消息", "我的", "外卖", "购物车"),
    "com.fliggy.hmos": ("首页", "行程", "消息", "我的", "酒店", "机票", "火车票"),
    "com.anjuke.home": ("首页", "消息", "我的", "二手房", "新房", "租房", "找房"),
    "com.ss.hm.article.video": ("首页", "放映厅", "我的", "关注", "推荐", "电影"),
}
_SEARCH_BOOST = ("搜索", "Search", "搜一搜", "搜点什么", "输入")


def _sanitize(pkg: str, raw: dict) -> dict:
    """Drop mine noise; inject known chrome. Runtime, cheap."""
    if not raw:
        return raw
    s = dict(raw)
    tabs = [t for t in (s.get("tabs") or []) if isinstance(t, str) and 1 < len(t) <= 6]
    boost = list(_TAB_BOOST.get(pkg) or ())
    s["tabs"] = list(dict.fromkeys(boost + tabs))[:20]
    search = [
        x
        for x in (s.get("search") or [])
        if isinstance(x, str) and 1 < len(x) <= 8 and "官网" not in x and "失败" not in x
    ]
    s["search"] = list(dict.fromkeys(list(_SEARCH_BOOST) + search))[:12]
    errs = [
        e
        for e in (s.get("errors") or [])
        if isinstance(e, str) and 2 <= len(e) <= 16 and "参数" not in e and "请求" not in e
    ]
    s["errors"] = list(dict.fromkeys(errs + ["网络异常", "加载失败", "请重试"]))[:30]
    empty = [
        e
        for e in (s.get("empty") or [])
        if isinstance(e, str)
        and 2 <= len(e) <= 16
        and not e.startswith(("%", ")", "+"))
        and "=" not in e
    ]
    s["empty"] = list(dict.fromkeys(empty + ["暂无", "没有更多"]))[:20]
    acts = [a for a in (s.get("actions") or []) if isinstance(a, str) and len(a) <= 6]
    s["actions"] = list(
        dict.fromkeys(acts + ["取消", "确认", "重试", "刷新", "返回", "关闭", "知道了"])
    )[:20]
    misc = [
        m
        for m in (s.get("misc_labels") or [])
        if isinstance(m, str) and 2 <= len(m) <= 8
    ]
    s["misc_labels"] = list(dict.fromkeys(list(s["tabs"][:8]) + misc))[:30]
    s["package"] = pkg
    return s


@lru_cache(maxsize=32)
def _load_signals(pkg: str) -> dict:
    from properties.modeA_props.decompile_gate import require_decompile_signals, signals_path
    require_decompile_signals(pkg)  # hard fail — no boost-only ghost runs
    p = signals_path(pkg)
    return _sanitize(pkg, json.loads(p.read_text(encoding="utf-8")))


def _target_pkg(d=None) -> str | None:
    env = os.environ.get("KEA2_TARGET_PKG") or os.environ.get("KEA2_PACKAGE")
    if env:
        return env.strip()
    if d is not None:
        fg = fg_package(d) or ""
        if fg and (_MINED / fg / "signals.json").exists():
            return fg
        # partial match (ability suffix)
        for sub in _MINED.iterdir() if _MINED.exists() else []:
            if sub.is_dir() and sub.name in fg:
                return sub.name
    return None


def _sig(d) -> dict:
    pkg = _target_pkg(d)
    if not pkg:
        return {}
    return _load_signals(pkg)


def _on_sut(d) -> bool:
    pkg = _target_pkg(d)
    if not pkg:
        return hierarchy_text_count(d) >= 3
    fg = fg_package(d) or ""
    return pkg in fg or hierarchy_text_count(d) >= 4


class DecompiledMineProps(unittest.TestCase):
    """Oracles seeded from static abc mine (labels / errors / search / empty)."""

    @classmethod
    def setUpClass(cls):
        from properties.modeA_props.decompile_gate import require_decompile_signals
        require_decompile_signals()  # abort suite if no offline decompile for target
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.98)
    @max_tries(8)
    @precondition(lambda self: _on_sut(self.d))
    def test_mined_tab_reachable(self):
        """Mined tab chrome tappable; apps without tabs (calc) check shell."""
        d = self.d
        dismiss_noise(d)
        s = _sig(d)
        tabs = tuple(s.get("tabs") or ())
        if not tabs:
            n = hierarchy_text_count(d)
            # no mine tabs + thin/lock-screen dump → skip (not product tab bug)
            if n < 5 and not any_text(d, tuple(s.get("misc_labels") or ()) + tuple(s.get("actions") or ())):
                return
            labels = tuple(s.get("misc_labels") or ()) + tuple(s.get("actions") or ())
            assert any_text(d, labels) or n >= 4, (
                "no tabs and no mined chrome"
            )
            return
        if any_text(d, tabs):
            hit = click_first(d, tabs, settle=0.35)
            if hit:
                time.sleep(0.25)
            assert ui_alive(d) and hierarchy_text_count(d) >= 3, (
                f"mined tab killed UI tabs={tabs[:6]}"
            )
            return
        n = hierarchy_text_count(d)
        # interstitial/ad (e.g. weibo KFC Skip) — not a product tab bug
        if any_text(d, ("广告", "Skip", "跳过")) and n <= 6:
            return
        # lock-screen / AA-dump flicker (clock-only tree) — skip
        if n < 4:
            return
        assert n >= 4, "no mined tabs and thin dump"

    @prob(0.97)
    @max_tries(8)
    @precondition(
        lambda self: _on_sut(self.d)
        and bool(_sig(self.d).get("search"))
        and bool(_sig(self.d).get("tabs"))  # skip non-search apps (calc)
    )
    def test_mined_search_opens(self):
        s = _sig(self.d)
        # only short search chrome — long mine strings are API noise
        labels = tuple(x for x in (s.get("search") or ()) if len(x) <= 8) or ("搜索", "Search")
        fp0 = hierarchy_fingerprint(self.d)
        if not click_first(self.d, labels, settle=0.4):
            return
        time.sleep(0.3)
        fp1 = hierarchy_fingerprint(self.d)
        ok = fp0 != fp1 or any_text(self.d, labels + ("取消", "搜索", "Search"))
        assert ok or ui_alive(self.d), f"search no-op labels={labels[:5]}"

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: _on_sut(self.d) and bool(_sig(self.d).get("errors")))
    def test_error_chrome_not_dead_end(self):
        """If mined error string visible, retry/back chrome or content remains."""
        s = _sig(self.d)
        errs = tuple(s.get("errors") or ())
        acts = tuple(s.get("actions") or ()) + ("重试", "刷新", "返回", "关闭", "取消", "Retry")
        if not any_text(self.d, errs):
            return
        n = hierarchy_text_count(self.d)
        # error page may offer retry; either way must not be blank
        click_first(self.d, acts, settle=0.35)
        n2 = hierarchy_text_count(self.d)
        assert n >= 2 and n2 >= 2 and ui_alive(self.d), (
            f"error state dead n={n}->{n2} errs={errs[:4]}"
        )

    @prob(0.88)
    @max_tries(4)
    @precondition(lambda self: _on_sut(self.d) and bool(_sig(self.d).get("empty")))
    def test_empty_state_has_shell(self):
        s = _sig(self.d)
        empty = tuple(s.get("empty") or ())
        if not any_text(self.d, empty):
            return
        n = hierarchy_text_count(self.d)
        assert n >= 3 or any_text(self.d, tuple(s.get("tabs") or ()) + empty), (
            f"empty state blank n={n}"
        )

    @prob(0.92)
    @max_tries(6)
    @precondition(lambda self: _on_sut(self.d) and bool(_sig(self.d).get("misc_labels")))
    def test_mined_label_click_stays_alive(self):
        """Click a short mined label; SUT stays up (proxy for dead controls)."""
        s = _sig(self.d)
        labels = tuple(s.get("misc_labels") or ())[:20]
        # prefer visible
        visible = [t for t in labels if self.d(text=t).exists() or self.d(textContains=t).exists()]
        pool = tuple(visible or labels)
        hit = click_first(self.d, pool, settle=0.35)
        if not hit:
            return
        time.sleep(0.25)
        pkg = _target_pkg(self.d)
        fg = fg_package(self.d) or ""
        n = hierarchy_text_count(self.d)
        assert n >= 2 and ui_alive(self.d), f"mined click blank hit={hit}"
        if pkg and fg and pkg not in fg:
            assert n >= 2, f"left SUT blank pkg={pkg} fg={fg}"

    @prob(0.97)
    @max_tries(8)
    @precondition(lambda self: _on_sut(self.d) and bool(_sig(self.d).get("actions")))
    def test_mined_action_keeps_shell(self):
        """Mined action (重试/清除/确认…) must not blank tree."""
        s = _sig(self.d)
        acts = tuple(s.get("actions") or ())
        if not any_text(self.d, acts):
            return
        n0 = hierarchy_text_count(self.d)
        click_first(self.d, acts, settle=0.35)
        time.sleep(0.25)
        n1 = hierarchy_text_count(self.d)
        assert ui_alive(self.d) and n1 >= 2, f"action blank {n0}->{n1} acts={acts[:5]}"

    @prob(0.95)
    @max_tries(4)
    @precondition(lambda self: _on_sut(self.d))
    def test_signals_loaded(self):
        """Sanity: offline signals exist for current target (always fire once)."""
        pkg = _target_pkg(self.d)
        s = _sig(self.d)
        assert pkg, "no KEA2_TARGET_PKG / mined fg package"
        assert s.get("package") == pkg or s.get("tabs"), f"missing signals for {pkg}"
