# BUG-blank-cold-start — com.sctv.scfocushm

| Field | Value |
|---|---|
| Severity | **HIGH** |
| Package | `com.sctv.scfocushm` |
| Ability | `EntryAbility` |
| Device | `5SM0125606000291` |
| Classification | SUT reliability bug: intermittent blank white cold start |

## Summary
Cold start of SC Focus frequently leaves the ability **FOREGROUND** with a near-white empty surface (no home chrome / bottom nav). Measured by `cold-start-probe.sh`.

## Evidence
- Probe: `pbt-out/COLD_START.json`
- **blank_rate: 4/8 (50.0%)** at wait=12s, white_frac threshold 0.92
- Blank trials (FG=true, white≈0.95): `cold-start/trial_00.png` … `trial_03.png`
- Non-blank trials: `trial_04.png`, `trial_06.png`
- Copies: `bug_reports/blank_trial_00.png`, `bug_reports/ok_trial_04.png`

### Trial table
| trial | white_frac | mean | foreground | blank |
|---:|---:|---:|---|---|
| 0 | 0.949 | 251.8 | true | **yes** |
| 1 | 0.949 | 251.8 | true | **yes** |
| 2 | 0.949 | 251.8 | true | **yes** |
| 3 | 0.955 | 251.5 | true | **yes** |
| 4 | 0.692 | 246.6 | true | no |
| 5 | 0.004 | 9.7 | false | no |
| 6 | 0.028 | 107.7 | true | no |
| 7 | 0.004 | 9.7 | false | no |

## Steps to reproduce
1. `aa force-stop com.sctv.scfocushm`
2. `aa start -a EntryAbility -b com.sctv.scfocushm -m entry`
3. Wait ~12s with screen AWAKE
4. Snapshot display / dumpLayout
5. Observe blank white FOREGROUND (~50% of trials) or process exit / no paint

## Expected
Home UI with bottom nav (`首页` / `视界` / `社区` / `畅听` / `我的`) within a few seconds of FOREGROUND.

## Actual
Often FOREGROUND with white empty surface; dumpLayout shows only system clock chrome or nothing usable. Process sometimes exits shortly after FOREGROUND (`window attached #0`, WMS `WINDOW_STATE_ATTACH_EXCEPTION`).

## Impact
Blocks automated GUI PBT (Kea2 launch gate / property preconditions never fire). Real users see blank or bounced launches on cold start.

## Notes
- Device UI also showed **Ultra battery saver** during diagnosis; may amplify kill/attach races but blank FOREGROUND is still an app paint failure.
- Initial home dump earlier in the session (when warm) showed full nav — defect is cold-start specific / intermittent.
