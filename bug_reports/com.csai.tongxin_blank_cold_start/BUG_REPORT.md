# Bug Report: Intermittent blank white screen on cold start

| Field | Value |
|---|---|
| **Product** | 通信工程师考试 (Communication Engineer Exam) |
| **Package** | `com.csai.tongxin` |
| **Version** | **1.0.1** (versionCode 101) |
| **Distribution** | Huawei AppGallery |
| **Platform** | HarmonyOS NEXT |
| **Device (lab)** | serial `5SM0125606000291` |
| **Severity** | **High** — app unusable until force-stop |
| **Component** | UNI-APP WebView shell (`EntryAbility` → local `www/` / `__UNI__AC14E7C`) |
| **Status** | Confirmed reproducible in lab |
| **Report date** | 2026-07-20 |
| **Found by** | Kea2 / hdc automated cold-start campaign |

---

## Summary

After a **cold start** (force-stop then launch), the app process reaches **FOREGROUND**, but the UI frequently stays **entirely white** (status bar only) for **≥10 seconds** with no splash, exam picker, home, loading indicator, or error message.

When the bug does **not** occur, the same build paints normal home UI within ~5 seconds on the same device.

**Lab repro rate: 7/15 (46.7%)** with a fixed 10s observation window after `aa start`.

---

## Impact

- User opens the app and sees a blank white screen.
- No recovery path inside the UI (nothing to tap).
- User must force-stop and relaunch; may need multiple attempts.
- Intermittent → hard for users to describe; easy to dismiss as “slow phone” unless multi-trial tested.

---

## Environment

- **OS:** HarmonyOS NEXT (lab phone)
- **App:** `com.csai.tongxin` 1.0.1 from AppGallery
- **Entry:** `EntryAbility`
- **UI stack:** Hybrid UNI-APP WebView loading  
  `file:///data/storage/el1/bundle/entry/resources/resfile/apps/__UNI__AC14E7C/www/`
- **Tools used for measurement:** `hdc`, `uitest screenCap`, pixel white-fraction on screenshot

---

## Steps to reproduce (manual)

1. Install **通信工程师考试** v1.0.1 from AppGallery.
2. Unlock the phone; keep the screen on.
3. Open the app once and confirm normal UI can appear (home or exam selection).
4. Leave the app (Home / Recents).
5. **Force stop** the app:  
   **Settings → Apps → 通信工程师考试 → Force stop**  
   (or `hdc shell aa force-stop com.csai.tongxin`).
6. Launch the app again from the launcher  
   (or `hdc shell aa start -a EntryAbility -b com.csai.tongxin`).
7. **Do not touch the screen.** Wait **10 seconds**.
8. Observe:
   - **Bug:** full white content area (only status bar icons/time).
   - **OK:** splash / “选择我的考试” / home (每日打卡, bottom tabs, etc.).
9. Repeat steps 5–8 **at least 10–15 times**.

### Expected
Within a few seconds, Web content paints (or a loading/error UI is shown).

### Actual
On a large fraction of cold starts (~**47%** in lab @10s): content area remains pure white; process stays foreground; no error UI.

---

## Steps to reproduce (automated / hdc)

```bash
# from this directory
bash repro_blank_cold_start.sh 15 10
# requires: hdc, python3, pillow, numpy
```

Minimal loop:

```bash
PKG=com.csai.tongxin
DEV=<serial>   # optional: hdc -t $DEV ...

for i in $(seq 0 14); do
  hdc shell aa force-stop "$PKG"
  sleep 1
  hdc shell aa start -a EntryAbility -b "$PKG"
  sleep 10
  hdc shell "uitest screenCap -p /data/local/tmp/t$i.png"
  echo "captured trial $i"
done
# Pull screenshots; blank = almost pure white image
```

Classification used in lab: downscale screenshot to 64×128 RGB; **blank** if fraction of pixels with channel value >248 is **≥ 0.92**, and app is FOREGROUND.

---

## Lab results (N=15, wait=10s)

| Trial | Result @10s | white_frac | mean pixel | FOREGROUND | file |
|---:|---|---:|---:|---|---|
| 0 | ok | 0.374 | 217.7 | True | `trial_00.png` |
| 1 | ok | 0.374 | 217.7 | True | `trial_01.png` |
| 2 | ok | 0.374 | 217.7 | True | `trial_02.png` |
| 3 | **BLANK** | 0.985 | 254.2 | True | `trial_03.png` |
| 4 | **BLANK** | 0.986 | 254.2 | True | `trial_04.png` |
| 5 | ok | 0.374 | 217.8 | True | `trial_05.png` |
| 6 | **BLANK** | 0.986 | 254.2 | True | `trial_06.png` |
| 7 | ok | 0.374 | 217.7 | True | `trial_07.png` |
| 8 | ok | 0.374 | 217.7 | True | `trial_08.png` |
| 9 | ok | 0.374 | 217.7 | True | `trial_09.png` |
| 10 | **BLANK** | 0.985 | 254.2 | True | `trial_10.png` |
| 11 | **BLANK** | 0.985 | 254.2 | True | `trial_11.png` |
| 12 | **BLANK** | 0.985 | 254.2 | True | `trial_12.png` |
| 13 | **BLANK** | 0.985 | 254.2 | True | `trial_13.png` |
| 14 | ok | 0.374 | 217.7 | True | `trial_14.png` |

- **BLANK:** 7  
- **OK:** 8  
- **Rate:** 7/15 (46.7%)  
- Raw JSON: [`REPRO_RESULTS.json`](./REPRO_RESULTS.json)

### Visual evidence

| | |
|---|---|
| **Bug** | [`evidence/BLANK_trial_03.png`](./evidence/BLANK_trial_03.png) (also trials 04, 06, 10–13) |
| **OK control** | [`evidence/OK_contrast_trial_00.png`](./evidence/OK_contrast_trial_00.png) — normal home, same procedure |

**BLANK (trial 03):** pure white content.  
**OK (trial 00):** full home — 初级通信工程师, 每日打卡, 全真模拟, bottom tabs 会员/课程/学习/我的.

---

## Technical observations

1. **Not a native crash / ANR**  
   - `aa dump` shows package **FOREGROUND** on blank trials.  
   - Separate Kea2 smoke (coord taps after successful land) reported **no crash** in 20 steps.

2. **WebView shell fails to paint**  
   - `uitest dumpLayout` on blank/loaded shell shows a `Web` node → empty `rootWebArea` / `genericContainer` (no accessible children/text).  
   - Blank is confirmed by **screenshot pixels**, not selector flake.

3. **Intermittent on identical build**  
   - Same version, device, start command; OK and BLANK alternate.  
   - Suggests race / WebView or UNI-APP runtime init issue, not a permanent bad install.

4. **OK path timing**  
   - Successful starts typically leave “mostly white” splash phase by ~2s and show real UI by ~5–6s (`white_frac ≈ 0.37`).  
   - Blank trials remain `white_frac ≈ 0.985` at 10s (and previously observed through 12s).

---

## Suggested direction for developers (non-prescriptive)

- Ensure WebView first-paint timeout shows a **native loading or error** surface (never infinite white).  
- Log UNI-APP / WebView console and Harmony hilog on cold start when first content paint exceeds N seconds.  
- Check race between `EntryAbility` lifecycle and Web engine init after `force-stop` (full process death).  
- Consider native splash until JS bridge / first page `ready`.  
- Verify whether blank correlates with memory pressure, first launch after reboot, or concurrent Web processes.

---

## Attachments in this folder

```
com.csai.tongxin_blank_cold_start/
├── BUG_REPORT.md                 (this file)
├── REPRO_RESULTS.json            (full trial metrics)
├── repro_blank_cold_start.sh     (repro script)
└── evidence/
    ├── BLANK_trial_03.png
    ├── BLANK_trial_04.png
    ├── BLANK_trial_06.png
    ├── BLANK_trial_10.png
    ├── BLANK_trial_11.png
    ├── BLANK_trial_12.png
    ├── BLANK_trial_13.png
    └── OK_contrast_trial_00.png
```

---

## Contact / method note

Found during HarmonyOS GUI property-based testing with **Kea2** (`hdc` + screenshot oracle). Functional deep-links inside the WebView were not required to expose this bug; **cold-start + screenshot** is sufficient.

Please re-run the 15× force-stop/start loop on your devices; a ~30–50% blank rate at 10s should be easy to confirm if the issue is general.
