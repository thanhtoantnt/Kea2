# BUG-cold-start-jscrash — HIGH

## Summary

`com.huawei.hmos.myhuawei` (My Huawei) **crashes on every cold start** with a JS `TypeError` during UI component module load. The process never reaches a stable FOREGROUND UI.

## Severity

**HIGH** — app is unusable; 100% launch failure on this device/build.

## Environment

| Item | Value |
|---|---|
| Device | HUAWEI Mate 80 Pro (SGT-AL00) serial `5SM0125606000291` |
| OS build | 6.1.0.21TW(C00E21R2P3log) |
| Package | com.huawei.hmos.myhuawei |
| Version | 20.126.6.301 (versionCode 2012606301) |
| Ability | entry / EntryAbility |
| Pre-installed system app | yes |

## Steps to reproduce

1. `hdc shell aa force-stop com.huawei.hmos.myhuawei`
2. `hdc shell aa start -a EntryAbility -b com.huawei.hmos.myhuawei -m entry`
3. Observe: tool prints `start ability successfully`
4. Within ~3s process is gone; new file under `/data/log/faultlog/faultlogger/jscrash-com.huawei.hmos.myhuawei-*.log`
5. `aa dump -a` shows **no** myhuawei FOREGROUND mission

## Expected

EntryAbility stays FOREGROUND and shows My Huawei home UI.

## Actual

Process dies with:

```
Reason: TypeError
Error name: TypeError
Error message: Cannot read property TOUCH of undefined
Stacktrace:
    at MaterialOptions (entry|ui_components|1.0.0|src/main/ets/common/u18/o40.ts:0:1)
    at HdsStyle (entry|ui_components|1.0.0|src/main/ets/common/u18/o40.ts:0:1)
    at func_main_0 (entry|ui_components|1.0.0|src/main/ets/common/u18/o40.ts:0:1)
```

Faultlogger: process life time ~3s, Foreground:No.

## Evidence

| Artifact | Path |
|---|---|
| Cold-start probe | `pbt-out/COLD_START.json` — **8/8 dead**, crash_rate **1.0** |
| Fault log (copied) | `pbt-out/bug_reports/jscrash-com.huawei.hmos.myhuawei-20020079-20260723133232393.log` |
| Excerpt | `pbt-out/bug_reports/crash_excerpt.txt` |
| Launch gate | `ensure-screen.sh` → `LAUNCH_FAIL` |

## Notes

- Not a PIN/keyguard issue (screen AWAKE, no password pad).
- `com.huawei.hmsapp.samplemanagement` is keepAlive/READY but does not own FG and shows no clock-in UI; SceneBoard logs `SampleManager: isSampleMg: false`.
- `aa start` return code is success; failure is in-app JS during `ui_components` init (`MaterialOptions`/`HdsStyle` reading `.TOUCH` on undefined — likely missing enum/constant for touch material style).
- Reproduced repeatedly in one session (10+ jscrash files before probe; +8 during probe).

## Impact on PBT

Kea2 GUI property campaign cannot execute (zero FOREGROUND dumps, zero T0 preconditions). Campaign stops after filing this bug.
