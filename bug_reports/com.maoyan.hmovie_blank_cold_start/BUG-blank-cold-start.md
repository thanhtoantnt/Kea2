# BUG: Intermittent blank white cold start — com.maoyan.hmovie

- **Severity:** HIGH
- **Package:** com.maoyan.hmovie
- **Device:** 5SM0125606000291
- **Classification:** SUT reliability bug (FOREGROUND, no UI paint)

## Summary
Cold start sometimes leaves the app FOREGROUND with an almost entirely white screen (no bottom nav / home chrome). Observed **2/8 (25%)** blank trials after `aa start` + 10s wait.

## Evidence
- `pbt-out/COLD_START.json` — blank_count=2, blank_rate_pct=25.0
- Blank screenshots: `cold-start/trial_00.png`, `cold-start/trial_04.png` (white_frac≈0.959)
- OK screenshots: `cold-start/trial_01.png` … (white_frac≈0.27–0.29)
- Copies: `bug_reports/blank_trial_00.png`, `bug_reports/ok_trial_01.png`

## Steps to reproduce
1. `aa force-stop com.maoyan.hmovie`
2. `aa start -a EntryAbility -b com.maoyan.hmovie` (module maoyan)
3. Wait 10s, capture display
4. Repeat; blank appears intermittently while process/mission is FOREGROUND

## Impact
Kea2 explorer often sees only `加载中` / weak hierarchy and never satisfies T0 tab preconditions → `executed_total=0` for nav properties on affected launches. Users see a stuck white/loading shell after open.
