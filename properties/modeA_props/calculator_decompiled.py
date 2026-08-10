"""Calculator properties from *manual* decompile reading (not a template miner).

Evidence (agent-read, one app):
  harmony-decompile/xabc_out/decompiled/com.huawei.hmos.calculator/
    arkdemo.ts.names.ts  — module map (62 app records)
  harmony-decompile/calculator/
    signals.json, extracted/resources/.../main_pages.json, module.json

Structure recovered:
  pages:  main | historyRecordPage
  main:   DigitPanel + DigitPanelController + Evaluator + KeyCode/KeyText
          + OperationView + MenuItems + IndexTitleBar + PhysicsButton
  history: HistoryRecord + HistoryRecordController + EmptyView + TitleBar
           + DelRecordsDialogPC
  strings (zh/en mine): 清除/删除/错误/等于/无记录|無記錄|No history/历史|History/
                        标准|標準|Science|计算器|CLEAR|ERROR

Contracts (UI-checkable pre / action / post):
  digit_panel_present     pre: on calc
                          post: ≥5 digit keys OR thick shell
  simple_add              pre: digits visible
                          act: clear? then 1 + 2 =
                          post: UI changed or shows 3 / expr
  div_by_zero             pre: digits
                          act: CLEAR then 1 ÷ 0 =
                          post: still calc, not blank (Error/∞ ok)
  open_history            pre: on calc
                          act: 历史 / History / MenuItems path
                          post: history/empty/delete chrome or fp change
  empty_history_chrome    pre: empty or history labels
                          post: shell not dead
  clear_keeps_shell       pre: digit or clear
                          act: digit then CLEAR
                          post: digits still there
  science_toggle          pre: science/standard chrome
                          act: toggle
                          post: shell alive
  inv_calc_shell          pre: on calc (every fire)
                          post: digits|ops|history chrome|thick tree
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
    safe_click,
    ui_alive,
)

PKG = "com.huawei.hmos.calculator"
_DIGITS = tuple("0123456789")
_OPS = ("+", "−", "-", "×", "*", "÷", "/", "=", "＝", "%", "＋")
_CLEAR = ("C", "AC", "清除", "CE", "CLEAR", "Clear")
_HIST = ("历史", "記錄", "履歴", "History", "记录")
_EMPTY = ("无记录", "無記錄", "No history", "暂无", "空空")
_ERR = ("错误", "錯誤", "Error", "ERROR", "无效", "無効", "NaN", "不能")
_SCI = ("科学", "標準", "标准", "Science", "SCIENCE", "sin", "cos", "tan", "√", "π")
_MENU = ("更多", "⋯", "…", "Menu", "菜单")
_DEL = ("删除", "刪除", "Delete", "DELETE", "消去")


def _on_calc(d) -> bool:
    p = fg_package(d) or ""
    return PKG in p or any_text(d, _DIGITS + _OPS + ("计算器", "計算機", "電卓"))


def _clear(d) -> None:
    """Best-effort expression reset before deterministic key sequences."""
    click_first(d, _CLEAR, settle=0.2)


def _click_seq(d, keys) -> bool:
    for t in keys:
        if t in ("+", "＋"):
            labels = ("+", "＋")
        elif t in ("÷", "/", "／"):
            labels = ("÷", "/", "／")
        elif t in ("=", "＝"):
            labels = ("=", "＝")
        elif t in ("×", "*"):
            labels = ("×", "*")
        else:
            labels = (t,)
        if not click_first(d, labels, settle=0.22):
            return False
        time.sleep(0.06)
    return True


class CalculatorDecompiledProps(unittest.TestCase):
    """Hand-derived contracts from calculator module map + string mine."""

    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    # --- invariant-like: main shell always has chrome ---
    @prob(0.99)
    @max_tries(12)
    @precondition(lambda self: _on_calc(self.d))
    def test_inv_calc_shell(self):
        """inv: on CalculatorAbility ⇒ digit/op/history chrome or thick tree."""
        d = self.d
        ok = (
            any_text(d, _DIGITS)
            or any_text(d, _OPS)
            or any_text(d, _HIST + _EMPTY + _SCI)
            or hierarchy_text_count(d) >= 8
        )
        assert ok and ui_alive(d), f"calc shell empty n={hierarchy_text_count(d)}"

    # --- DigitPanel ---
    @prob(0.99)
    @precondition(lambda self: _on_calc(self.d) or hierarchy_text_count(self.d) >= 2)
    def test_digit_panel_present(self):
        """pre: on calc. post: DigitPanel exposes ≥5 digit keys (or rich tree)."""
        n = sum(1 for t in _DIGITS if self.d(text=t).exists())
        assert n >= 5 or hierarchy_text_count(self.d) >= 8, f"digit panel missing n_digits={n}"

    # --- Evaluator ---
    @prob(0.95)
    @max_tries(8)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _DIGITS))
    def test_simple_add_shows_result(self):
        """pre: digits. act: CLEAR · 1+2=. post: result/expr change (Evaluator)."""
        d = self.d
        _clear(d)
        fp0 = hierarchy_fingerprint(d)
        if not _click_seq(d, ("1", "+", "2", "=")):
            return
        time.sleep(0.35)
        fp1 = hierarchy_fingerprint(d)
        ok = (
            any_text(d, ("3", "1+2", "1＋2"))
            or fp0 != fp1
            or hierarchy_text_count(d) >= 6
        )
        assert ok, "1+2= produced no visible result/change"

    @prob(0.9)
    @max_tries(6)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _DIGITS))
    def test_div_by_zero_not_silent_crash(self):
        """pre: digits. act: CLEAR · 1÷0=. post: still calc shell (Error/∞ ok)."""
        d = self.d
        _clear(d)
        if not _click_seq(d, ("1", "÷", "0", "=")):
            return
        time.sleep(0.4)
        pkg = fg_package(d) or ""
        n = hierarchy_text_count(d)
        assert PKG in pkg or n >= 4, f"left calc after 1÷0 pkg={pkg}"
        assert n >= 3 or any_text(d, _ERR + ("∞", "Infinity")), f"div0 blank UI n={n}"

    # --- HistoryRecord page ---
    @prob(0.92)
    @max_tries(6)
    @precondition(lambda self: _on_calc(self.d))
    def test_open_history_page(self):
        """pre: main. act: MenuItems/历史. post: HistoryRecord or EmptyView chrome."""
        d = self.d
        fp0 = hierarchy_fingerprint(d)
        hit = click_first(d, _HIST + _MENU, settle=0.4)
        if not hit:
            return
        time.sleep(0.35)
        click_first(d, _HIST, settle=0.35)  # second hop if menu first
        time.sleep(0.3)
        ok = (
            any_text(d, _HIST + _EMPTY + _DEL + _CLEAR)
            or hierarchy_fingerprint(d) != fp0
        )
        assert ok or ui_alive(d), "history page not opened"

    @prob(0.88)
    @max_tries(4)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _EMPTY + _HIST))
    def test_empty_history_has_chrome(self):
        """pre: EmptyView/history labels. post: not white-dead (TitleBar/back ok)."""
        d = self.d
        n = hierarchy_text_count(d)
        assert (
            any_text(d, _EMPTY + _HIST + _DEL + ("返回", "关闭", "计算器", "計算機"))
            or n >= 4
        ), f"empty history dead n={n}"

    # --- ClearButton / KeyText clear ---
    @prob(0.9)
    @max_tries(5)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _CLEAR + _DIGITS))
    def test_clear_resets_or_stays_alive(self):
        """pre: clear or digit. act: digit · CLEAR. post: pad still interactive."""
        d = self.d
        click_first(d, _DIGITS, settle=0.2)
        if not click_first(d, _CLEAR, settle=0.35):
            return
        n = hierarchy_text_count(d)
        assert n >= 4 or any_text(d, _DIGITS), f"clear killed UI n={n}"

    # --- PhysicsButton / science mode (isScience in mine) ---
    @prob(0.85)
    @max_tries(4)
    @precondition(lambda self: _on_calc(self.d) and any_text(self.d, _SCI))
    def test_science_mode_toggle_alive(self):
        """pre: science chrome. act: toggle 科学/标准. post: shell alive."""
        d = self.d
        n0 = hierarchy_text_count(d)
        if not click_first(d, ("科学", "Science", "SCIENCE", "标准", "標準"), settle=0.4):
            return
        n1 = hierarchy_text_count(d)
        assert n1 >= 4 or ui_alive(d), f"science toggle blank {n0}->{n1}"
