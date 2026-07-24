# BUG — Clear key does not reset display

- **Package:** com.huawei.hmos.calculator
- **Severity:** MEDIUM (core keypad data path)
- **Property:** `test_clear_resets_display`
- **Stability:** 3/3 fails in one kea2 run
- **Device:** 5SM0125606000291

## Steps
1. Cold-start Calculator (`CalculatorAbility` / `pages/main`).
2. Ensure keypad home (`id_digit_panel`, `id_global_exp`).
3. Tap Clear (`id=keyCode_16`).
4. Tap digit `7` (`id=keyCode_7`) → display `get_text()` = `"7"`.
5. Tap Clear again (`id=keyCode_16`).

## Expected
Display (`id_global_exp`) becomes `""` or `"0"`.

## Actual
Display remains `"7"` after Clear click (Driver.click center of keyCode_16 bounds).

## Evidence
- kea2 `AssertionError: clear should reset display, got '7'` ×3
- Log: Component.getText on `id_global_exp` → `"7"` before and after clear click
- Bug report: `pbt-out/kea-run/res_2026072409_0359473661/bug_report.html`

## Notes
- Digit entry works (step 4). Failure is specifically Clear → no display change.
- `keyCode_16` is the top-left symbol key on the home digit panel (no text label in dump); assumed C/AC from layout.
