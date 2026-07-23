# BUG-js-crash-mainpage — HIGH

| Field | Value |
|---|---|
| package | `com.huawei.hmos.ailife` |
| version | 17.0.3.313 (versionCode 1703313) |
| device | 5SM0125606000291 / SGT-AL00 6.1.0.21TW |
| severity | **HIGH** — app unusable; process killed on every cold start of main UI |
| component | `phone` / `EntryAbility` → `MainPage` |
| classification | **SUT bug** (JS crash), not test/infra |

## Summary

After privacy consent (or on cold start once consent is stored), AI Life navigates to `MainPage` and immediately throws:

```text
TypeError: undefined is not callable
```

AppKit then exits the process (`Kill Reason:Js Error, foreground=1`). Process lifetime ≈ **3 seconds**. The user never reaches a stable home/tab UI.

## Steps to reproduce

1. Ensure device awake, no PIN.
2. `aa force-stop com.huawei.hmos.ailife`
3. `aa start -a EntryAbility -b com.huawei.hmos.ailife`
4. If shown, tap **Agree** on the privacy sheet.
5. Within ~3s the process dies; launcher returns (or empty gray frame briefly).

Reproduced multiple times in this campaign (hilog + faultlogger).

## Evidence

### Faultlogger (excerpt)

```text
Build info: SGT-AL00 6.1.0.21TW(C00E21R2P3log)
Version: 17.0.3.313
VersionCode: 1703313
Process life time: 3s
Reason: TypeError
Error name: TypeError
Error message: undefined is not callable
Stacktrace:
    at anonymous (phone|phone|1.0.0|src/main/ets/pages/MainPage.ts:2:24521)
    at updateFunc (.../stateMgmt.js:8865:1)
    at observeComponentCreation2 (...)
    at newTabContentHdsBuilder (phone|phone|1.0.0|src/main/ets/pages/MainPage.ts:2:23593)
    at anonymous (phone|phone|1.0.0|src/main/ets/pages/MainPage.ts:2:13834)
    at ifElseBranchUpdateFunction (...)
    at tabPages (phone|phone|1.0.0|src/main/ets/pages/MainPage.ts:2:13692)
    ...
```

Full dump: `pbt-out/fault_ailife.txt`  
Compact: `pbt-out/bug_reports/fault_summary.txt`

### Hilog (same failure)

```text
AceStateMgmt: @Component 'MainPage'[19] has error in update func: undefined is not callable
ArkCompiler: TypeError: undefined is not callable
  at newTabContentHdsBuilder (.../MainPage.ts:2:23593)
  at tabPages (.../MainPage.ts:2:13692)
AppKit: com.huawei.hmos.ailife is about to exit due to RuntimeError
hisysevent PROCESS_KILL msg=Kill Reason:Js Error, foreground=1
```

### Related module load errors (same launch, non-fatal noise)

Many HSP load failures immediately before the crash, e.g.:

- `ReferenceError: Observed is not defined` — `@ohos/homeservice`, `@hw-ailifehmos/devicecontrol_ui`, `@hw-ailifehmos/ailife_entity`, …
- `SyntaxError: … '@ohos:arkui.modifier' does not provide an export name 'CommonModifier'`
- `ReferenceError: Navigation is not defined` — `hdsBaseComponent.js`
- `ReferenceError: CustomDialogController is not defined`

These suggest a **runtime/API mismatch** between AI Life 17.0.3.313 (and bundled HSPs) and the device ArkUI/HDS stack on HarmonyOS 6.1.0.21TW. The fatal path is still the uncaught TypeError in `MainPage` tab builder.

### Probe corroboration

| Probe | Result |
|---|---|
| `COLD_START.json` | blank=0/8, but **foreground=false on 8/8** — process not retained after start |
| `TOUCH_PROBE.json` | `ok=false`, `error=could not land non-blank home` |
| `dump-ui` post-start | usable_texts=0 (status bar only) |

Screenshots: `pbt-out/cold-start/trial_*.png`, `pbt-out/home_shot.jpeg`, `pbt-out/touch-probe/land_*.png`.

## Expected

MainPage builds tab contents; app stays FOREGROUND with interactive home UI (device list / scenes / discover / me).

## Actual

Uncaught `TypeError` in `newTabContentHdsBuilder` / `tabPages` → process kill → no usable home.

## Suggested fix direction (for app owners)

1. Guard `newTabContentHdsBuilder` against undefined HDS tab builders; fail soft instead of throwing in updateFunc.
2. Align HSP versions (`devicecontrol_ui`, `homeservice`, HDS base) with OS 6.1 ArkUI exports (`Observed`, `Navigation`, modifiers).
3. Add crash telemetry for MainPage updateFunc errors; regression test cold start on 6.1.0.x.
