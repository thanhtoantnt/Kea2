# Bug Report: Bottom navigation tabs mostly unresponsive (WebView)

| Field | Value |
|---|---|
| **Product** | 通信工程师考试 |
| **Package** | `com.csai.tongxin` **v1.0.1** |
| **Severity** | High (primary navigation broken for automation and likely flaky for users) |
| **Component** | Bottom tab bar in UNI-APP WebView |

## Summary
On the home screen, **scroll/fling works**, but **tap targets for bottom tabs 我的 / 课程 / 学习** produced **no UI change** across a dense Y scan (`y=2560..2820`, step 30) via `uitest uiInput click` and `hmdriver2 Driver.click`.

**会员** at `(400, 2560)` once opened in-app login (possible hit on 会员 tab or nearby control). Other tabs never responded.

## Steps
1. Land on home (guest).
2. Tap bottom tabs: 会员 / 课程 / 学习 / 我的 (icon + label area).
3. Observe whether content/tab selection changes.

## Expected
Tab content switches; selected tab indicator moves.

## Actual (lab)
- `uitest uiInput swipe/fling` on content: **works** (screenshot diff >15).
- Tab taps at multiple coordinates: **no change** for 我的/课程/学习.
- Same with hmdriver2 coordinate click.

## Why this matters
- Breaks core IA (cannot reach 学习 / 我的 without lucky hits).
- Blocks selector-less automation; users on WebView touch issues may see same dead taps.

## Related
Web a11y tree empty → cannot confirm hit targets via dumpLayout; screenshot + package oracle only.
