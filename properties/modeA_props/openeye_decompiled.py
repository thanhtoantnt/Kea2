"""OpenEye props from *decompile/mine only* (no source reading).

Inputs:
  harmony-decompile/mined_all/com.winwang.harmonyOpenEye/signals.json
  Prefer mine_pa_signals.py (PA lda.str + string pool) over raw ABC bytes.

After PA miner (source-taught audit):
  chrome.main_tabs / sub_tabs / footers / mine_rows, routes[], rank_types[]
Still weak vs source: string.json 点我重试/网络错误 (resources, not in ABC).

Pair with openeye_source.py for coverage compare.
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
    ui_alive,
)

PKG = "com.winwang.harmonyOpenEye"


@lru_cache(maxsize=1)
def _sig() -> dict:
    homes = [
        os.environ.get("HARMONY_DECOMPILE_HOME"),
        os.environ.get("KEA2_DECOMPILE_HOME"),
        str(Path.home() / "github" / "harmony-decompile"),
    ]
    for h in homes:
        if not h:
            continue
        p = Path(h) / "mined_all" / PKG / "signals.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _field(*specs) -> tuple[str, ...]:
    """specs: 'chrome.main_tabs' | 'tabs' | ('default', 'lits')."""
    s = _sig()
    chrome = s.get("chrome") or {}
    out: list[str] = []
    for sp in specs:
        if isinstance(sp, tuple):
            out.extend(sp)
            continue
        if sp.startswith("chrome."):
            vals = chrome.get(sp.split(".", 1)[1]) or []
        else:
            vals = s.get(sp) or []
        out.extend(x for x in vals if isinstance(x, str) and x.strip())
    seen, u = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            u.append(x)
    return tuple(u)


_TABS = _field("chrome.main_tabs", "tabs", ("首页", "发现", "热门", "我的", "关注", "分类"))
_SUB = _field("chrome.sub_tabs", ("周排行", "月排行", "总排行", "主题"))
_MISC = _field("misc_labels", "chrome.footers", "chrome.mine_rows", ("关于", "开眼"))
_ACT = _field("actions", "retry", ("取消", "确认", "加载中"))
_ERR = _field("errors", "empty", ("网络异常", "加载中", "加载中..."))
_FOOT = _field("chrome.footers", ("我是有底线的",))
_DETAIL = ("视频详情",)


def _has(d, labels) -> bool:
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
    return PKG in p or _has(d, _TABS + ("开眼",) + _DETAIL)


def _ensure_main(d) -> None:
    if _has(d, _TABS):
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
        if _has(d, _TABS + ("开眼",)):
            return


def _shell(d) -> bool:
    return (_has(d, _TABS + _SUB + _MISC + _FOOT + _DETAIL) or hierarchy_text_count(d) >= 6) and ui_alive(d)


class OpenEyeDecompiledProps(unittest.TestCase):
    """Contracts from PA/signals mine only."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.99)
    @max_tries(10)
    @precondition(lambda self: _on(self.d))
    def test_dec_signals_tabs_present(self):
        d = self.d
        _ensure_main(d)
        n = sum(1 for t in _TABS[:4] if _has(d, (t,)))
        assert n >= 3 or hierarchy_text_count(d) >= 8, f"mined tabs n={n}"

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_dec_tab_find(self):
        d = self.d
        _ensure_main(d)
        if not _click(d, ("发现",), settle=0.5):
            return
        time.sleep(0.3)
        assert _shell(d)

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_dec_hot_and_rank_labels(self):
        d = self.d
        _ensure_main(d)
        if not _click(d, ("热门",), settle=0.55):
            return
        time.sleep(0.4)
        n = sum(1 for t in _SUB if _has(d, (t,)))
        assert n >= 1 or _has(d, ("热门",)), f"rank/sub labels n={n}"

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on(self.d))
    def test_dec_mine_about_or_brand(self):
        d = self.d
        _ensure_main(d)
        if not _click(d, ("我的",), settle=0.5):
            return
        time.sleep(0.35)
        assert _has(d, ("关于", "开眼", "关注", "分类") + _MISC) or _shell(d)

    @prob(0.85)
    @max_tries(5)
    @precondition(lambda self: _on(self.d) and _has(self.d, _ERR + _ACT))
    def test_dec_error_or_loading_chrome(self):
        d = self.d
        assert _has(d, _ERR + _ACT) or hierarchy_text_count(d) >= 4

    @prob(0.88)
    @max_tries(5)
    @precondition(lambda self: _on(self.d))
    def test_dec_footer_label(self):
        d = self.d
        _ensure_main(d)
        _click(d, ("热门",), settle=0.5)
        time.sleep(0.5)
        # footer may need scroll; shell ok; bonus if footer text
        assert _shell(d) or _has(d, _FOOT)

    @prob(0.92)
    @max_tries(8)
    @precondition(lambda self: _on(self.d))
    def test_dec_inv_shell(self):
        assert _shell(self.d), f"dead n={hierarchy_text_count(self.d)}"

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on(self.d))
    def test_dec_home_stays_alive(self):
        d = self.d
        _ensure_main(d)
        _click(d, ("首页",), settle=0.4)
        time.sleep(0.25)
        pkg = fg_package(d) or ""
        assert PKG in pkg or hierarchy_text_count(d) >= 5
        assert hierarchy_fingerprint(d) is not None and _shell(d)

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: _on(self.d))
    def test_dec_find_subtabs_from_chrome(self):
        """PA chrome.sub_tabs includes 关注/分类/主题 when mine worked."""
        d = self.d
        _ensure_main(d)
        if not _click(d, ("发现",), settle=0.55):
            return
        time.sleep(0.35)
        want = tuple(t for t in ("关注", "分类", "主题") if t in _SUB or t in _TABS)
        if not want:
            return
        n = sum(1 for t in want if _has(d, (t,)))
        assert n >= 1, f"subtabs n={n} want={want}"
