# BUG — Clear (`keyCode_16`) does not reset display

- **package:** com.huawei.hmos.calculator
- **property:** test_clear_resets_display
- **severity:** MED (functional keypad)
- **status:** candidate SUT bug (icon-only key; no a11y label in dump)

## Steps
1. Open Calculator home (CalculatorAbility).
2. Ensure expression area `id_global_exp` is ready.
3. Tap digit `7` (`keyCode_7`) → display shows `7`.
4. Tap top-left keypad key `keyCode_16` (assumed Clear/AC).

## Expected
Display `id_global_exp` becomes empty or `0`.

## Actual
Display remains `7` (`get_text()` → `"7"`).

## Evidence
- Kea2 run `pbt-out/kea-run/res_2026072314_5000336636/`
- AssertionError in property log; `LAST_RUN.json` fail=1 on this prop
- Digit entry works on same session (test_digit_appears_on_display pass)

## Note
`keyCode_16` has empty text/description in layout dump. If product maps that id to a non-clear action, this is a test mapping error — confirm against device UI label.
