# BUG: Bottom navigation tabs are dead (HIGH)

- **package:** com.csai.tongxin
- **device:** 5SM0125606000291
- **severity:** HIGH
- **oracle:** touch-probe navigation (scroll works ⇒ tab tap must change UI)
- **evidence:** `pbt-out/TOUCH_PROBE.json`

## Summary
On a painted home screen, vertical scroll produces large content_diff (34.7 ≥ ε=8), proving screenshot comparison works. Tapping each bottom tab at three Y offsets yields max content_diff≈1.3 < ε — **all 4 probed tabs are dead**. Primary CTAs also showed diff=0.

## Dead controls
| control | x | y tried | max_diff | violation |
|---|---|---|---|---|
| tab1_member | 384 | 2680,2720,2750 | 1.31 | < 8.0 |
| tab2_course | 640 | 2680,2720,2750 | 1.31 | < 8.0 |
| tab3_learn | 896 | 2680,2720,2750 | 1.31 | < 8.0 |
| tab4_me | 1152 | 2680,2720,2750 | 1.31 | < 8.0 |

scroll_works=true, scroll_content_diff=34.69, handoffs=[].

## Steps to reproduce
1. Launch app; wait until home is non-white (may need retries — see blank cold start bug).
2. Swipe content area — UI changes (scroll OK).
3. Tap bottom tab region at x∈{384,640,896,1152}, y≈2720.
4. Compare before/after screenshots — no meaningful UI change.

## Expected
Tab taps navigate / repaint major sections of the hybrid Web UI.

## Actual
Tabs ignore taps (or hit wrong layer). App stays on same visual home. Accessibility dump has no tab labels (opaque WebView), so users relying on a11y are also blocked.

## Attachments
- `pbt-out/touch-probe/home_0.png`
- `pbt-out/touch-probe/tab*_*.png` (before/after pairs under touch-probe/)
