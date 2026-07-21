# Bug Report: Intermittent blank white screen on cold start

| Field | Value |
|---|---|
| **Product** | 瑞新 / 真空e家 |
| **Package** | `com.ruixin.huawei` |
| **Platform** | HarmonyOS NEXT |
| **Device (lab)** | serial `5SM0125606000291` |
| **Severity** | **High** — app unusable until force-stop |
| **Component** | Hybrid Web / opaque WebView (`EntryAbility`) |
| **Status** | Confirmed reproducible in lab |
| **Report date** | 2026-07-21 |
| **Found by** | Kea2 / `pi-pbt kea` cold-start-probe (opaque path) |

---

## Summary

After a **cold start** (`aa force-stop` then `aa start`), the process reaches **FOREGROUND**, but the UI frequently stays **entirely white** for ≥10s (no home chrome, no splash recovery UI).

**Lab repro rate: 5/8 (62.5%)** @ 10s wait (`white_frac ≈ 0.985`).

When the bug does **not** occur, the same build paints bottom tabs (`真空e家` / `供应` / `消息` / `我的`) and home content.

---

## Impact

- User opens app → dead white screen.
- No in-app recovery; force-stop + relaunch may blank again.
- Intermittent → easy to dismiss as “slow phone” without multi-trial test.

---

## Steps to reproduce (automated)

```bash
cd bug_reports/com.ruixin.huawei_blank_cold_start
bash repro_blank_cold_start.sh 10 10
# needs: hdc, python3, pillow, numpy
```

Manual:

1. Install `com.ruixin.huawei`.
2. Force-stop → launch from launcher (or `aa start -a EntryAbility -b com.ruixin.huawei`).
3. Wait 10s, do not touch.
4. Observe blank white vs painted home.
5. Repeat ≥8 times.

### Expected
UI paints within a few seconds (or loading/error chrome).

### Actual
~**62%** cold starts: pure white content, process still FOREGROUND.

---

## Evidence (lab)

| trial | white_frac | blank |
|------:|-----------:|:-----:|
| 0 | 0.255 | ok |
| 1 | 0.985 | **BLANK** |
| 2 | 0.985 | **BLANK** |
| 3 | 0.255 | ok |
| 4 | 0.985 | **BLANK** |
| 5 | 0.262 | ok |
| 6 | 0.985 | **BLANK** |
| 7 | 0.985 | **BLANK** |

Screenshots: `evidence/trial_XX.png`  
Machine JSON: `COLD_START.json`

---

## Related campaign notes

- Guest **tab navigation** on a painted surface is OK (manual Kea2 A: ran_ok e=14; touch-probe: no dead tabs).
- Blank-start is independent of tab oracles — must use cold-start multi-trial probe on opaque WebView apps.
- Sibling pattern: `com.csai.tongxin` blank cold start (~47%).

---

## Environment

- Kea2 Harmony path + `pbt-agent` `cold-start-probe.sh`
- Device unlocked, USB `hdc`
