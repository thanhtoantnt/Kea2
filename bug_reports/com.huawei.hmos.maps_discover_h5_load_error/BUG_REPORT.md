# Bug Report: Maps Discover H5 rankings fails to load (traps UI)

| Field | Value |
|---|---|
| **Product** | Huawei Maps |
| **Package** | `com.huawei.hmos.maps.app` |
| **Platform** | HarmonyOS NEXT |
| **Device (lab)** | `5SM0125606000291` |
| **Severity** | **Medium** — Discover path dead-ends; user must leave app |
| **Component** | Discover tab → H5 rankings (`h5hosting-drcn.dbankcdn.cn/.../rankings`) |
| **Status** | Observed under Kea2 random explore |
| **Report date** | 2026-07-21 |
| **Found by** | `pi-pbt kea` Phase B (zero-exec campaign) |

## Summary

Opening / landing on the **Discover** rankings H5 page shows **"Loading error. Retry"** (or stays stuck loading). Under Kea2 exploration the app repeatedly fails to return to a healthy native home hierarchy (`weak/launcher hierarchy … relaunch` loops), so all T0 preconditions stay false for the rest of the run.

Cold-start blank probe: **0/8** — not a blank-paint bug; a **Discover H5 load / trap** issue.

## Impact

- User enters Discover rankings content → error / stuck.
- Recovery requires leaving the H5 surface (back / kill); random navigation easily strands the session.

## Repro (lab)

1. Launch Maps (`com.huawei.hmos.maps.app`).
2. Tap **Discover** (or explore until rankings H5 opens).
3. Observe load error / inability to get stable native home dump.

```bash
# automated signal: kea2 run with home-tab props often hits zero-exec
# when explorer enters Discover H5 — see kea.log hits
```

## Evidence

- `evidence/kea_log_hits.txt` — log lines mentioning H5 / relaunch
- Campaign: `~/harmonyy-app/maps/pbt-out/REPORT.md` (not_checked e=0)

## Notes

- Not a crash (Kea2: no crash found).
- Distinct from POI close races fixed earlier.
