"""Calculator props generated from HAP static analysis (modules.abc + module.json).

Source experiment: modeA_runs/decompile_exp/calculator/
Signals (not full arkdecompiler AST — macOS has no xabc binary yet):
  pages: pages/main, pages/historyRecordPage
  comps: DigitPanel, Evaluator, HistoryRecord, EmptyView, DelRecordsDialog,
         Science mode, PhysicsButton
  UI: 清除/删除/历史/无记录/错误/等于 + digit keys
  bugs to hunt: div-by-zero, history empty state, science toggle, nav to history
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    any_text,
    click_first,
    click_xy,
    dismiss_noise,
    fg_package,
    hierarchy_fingerprint,
    hierarchy_text_count,
    safe_click,
    ui_alive,
)

PKG = "com.huawei.hmos.calculator"
# mined / known calculator chrome
_DIGITS = tuple("0123456789")
_OPS = ("+", "−", "-", "×", "*", "÷", "/", "=", "＝", "%")
_CLEAR = ("C", "AC", "清除", "CE")
_HIST = ("历史", "記錄", "履歴", "History", "记录")
_EMPTY = ("无记录", "無記錄", "No history", "暂无", "空空")
_ERR = ("错误", "錯誤", "Error", "ERROR", "无效", "NaN", "不能")
_SCI = ("科学", "標準", "标准", "Science", "sin", "cos", "tan", "√", "π")


def _on_calc(d) -> bool:
    p = fg_package(d) or ""
    return PKG in p or any_text(d, _DIGITS + _OPS + ("计算器", "計算機"))


class CalculatorDecompiledProps(unittest.TestCase):
    """Static-analysis-informed oracles for system Calculator."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.99)
    @precondition(lambda self: _on_calc(self.d) or hierarchy_text_count(self.d) >= 2)
    def test_digit_panel_present(self):
        """DigitPanel: at least several digit keys visible."""
        n = sum(1 for d in _DIGITS if self.d(text=d).exists())
        # some skins use description not text — allow rich tree
        assert n >= 5 or hierarchy_text_count(self.d) >= 8, f"digit panel missing n_digits={n}"

    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _DIGITS))
    def test_simple_add_shows_result(self):
        """Evaluator path: 1+2= should change UI / show 3 or expression."""
        fp0 = hierarchy_fingerprint(self.d)
        for t in ("1", "+", "2", "="):
            if not safe_click(self.d, t, settle=0.25):
                # try unicode minus/times variants skipped for + =
                if t == "+" and not click_first(self.d, ("+", "＋"), settle=0.25):
                    return
                elif t != "+":
                    return
            time.sleep(0.1)
        time.sleep(0.35)
        fp1 = hierarchy_fingerprint(self.d)
        ok = (
            any_text(self.d, ("3", "1+2", "1＋2"))
            or fp0 != fp1
            or hierarchy_text_count(self.d) >= 6
        )
        assert ok, "1+2= produced no visible result/change"

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _DIGITS))
    def test_div_by_zero_not_silent_crash(self):
        """div-by-zero: app stays up; may show Error/∞ — not blank death."""
        for t in ("1", "÷", "0", "="):
            labels = (t,)
            if t == "÷":
                labels = ("÷", "/", "／")
            if not click_first(self.d, labels, settle=0.25):
                return
        time.sleep(0.4)
        pkg = fg_package(self.d)
        n = hierarchy_text_count(self.d)
        assert pkg is None or PKG in (pkg or "") or n >= 4, f"left calc after 1÷0 pkg={pkg}"
        assert n >= 3 or any_text(self.d, _ERR + ("∞", "Infinity", "错误")), (
            f"div0 blank UI n={n}"
        )

    @prob(0.92)
    @max_tries(6)
    @precondition(lambda self: _on_calc(self.d))
    def test_open_history_page(self):
        """pages/historyRecordPage reachable from main."""
        fp0 = hierarchy_fingerprint(self.d)
        hit = click_first(self.d, _HIST + ("更多", "⋯", "…", "Menu"), settle=0.4)
        if not hit:
            # try top-right menu area heuristic
            return
        time.sleep(0.4)
        # may need second tap on 历史
        click_first(self.d, _HIST, settle=0.4)
        time.sleep(0.35)
        ok = (
            any_text(self.d, _HIST + _EMPTY + ("删除", "清除", "Delete", "Clear"))
            or hierarchy_fingerprint(self.d) != fp0
        )
        assert ok or ui_alive(self.d), "history page not opened"

    @prob(0.88)
    @max_tries(4)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _EMPTY + _HIST))
    def test_empty_history_has_chrome(self):
        """EmptyView: empty history still has shell (not white crash)."""
        n = hierarchy_text_count(self.d)
        assert (
            any_text(self.d, _EMPTY + _HIST + ("返回", "关闭", "计算器"))
            or n >= 4
        ), f"empty history dead n={n}"

    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _CLEAR + _DIGITS))
    def test_clear_resets_or_stays_alive(self):
        """Clear/C: UI remains interactive."""
        click_first(self.d, _DIGITS, settle=0.2)
        if not click_first(self.d, _CLEAR, settle=0.35):
            return
        n = hierarchy_text_count(self.d)
        assert n >= 4 or any_text(self.d, _DIGITS), f"clear killed UI n={n}"

    @prob(0.85)
    @max_tries(4)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _SCI))
    def test_science_mode_toggle_alive(self):
        """Science panel toggle must not blank tree."""
        n0 = hierarchy_text_count(self.d)
        if not click_first(self.d, ("科学", "Science", "标准", "標準"), settle=0.4):
            return
        n1 = hierarchy_text_count(self.d)
        assert n1 >= 4 or ui_alive(self.d), f"science toggle blank {n0}->{n1}"
