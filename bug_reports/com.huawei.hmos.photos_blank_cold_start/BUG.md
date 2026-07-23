# BUG — Intermittent blank white cold start (HIGH)

- **Package:** `com.huawei.hmos.photos`
- **Ability:** `com.huawei.hmos.photos.MainAbility`
- **Device:** `5SM0125606000291`
- **Severity:** HIGH (SUT reliability)
- **Evidence:** `pbt-out/COLD_START.json`, `pbt-out/cold-start/trial_00.png`, `trial_05.png` (blank) vs `trial_01.png` (OK)

## Summary

Cold start of Gallery sometimes leaves the process **FOREGROUND** but paints an almost fully white screen (no usable UI) for ≥10s after `aa start`.

## Rate

| metric | value |
|--------|-------|
| trials | 8 |
| blank | 2 |
| blank_rate | **25.0%** |
| white_frac (blank) | ~0.986 |
| mean_pixel (blank) | ~254.3 |
| foreground on blank | true |

## Steps to reproduce

1. Force-stop / kill Gallery if running.
2. `aa start -a com.huawei.hmos.photos.MainAbility -b com.huawei.hmos.photos`
3. Wait 10s; capture screenshot.
4. Repeat; observe intermittent full-white FOREGROUND frames.

## Expected

Home chrome (Photos / Albums / Highlights) paints within a few seconds of FOREGROUND.

## Actual

~1 in 4 cold starts: FOREGROUND + blank white UI (no tabs/content).

## Classification

SUT reliability bug — intermittent blank white cold start (not PIN, not launcher).
