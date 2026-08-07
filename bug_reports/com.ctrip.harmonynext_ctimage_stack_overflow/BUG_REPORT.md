# BUG — 携程 CTImage reactive loop → JS Stack overflow (jscrash)

| Field | Value |
|-------|--------|
| **ID** | `com.ctrip.harmonynext_ctimage_stack_overflow` |
| **Severity** | **HIGH** (foreground JS crash in shared image component) |
| **Status** | Confirmed on device; multi-day, multi-run |
| **App** | 携程旅行 HarmonyOS `com.ctrip.harmonynext` |
| **Version** | **8.94.6** (versionCode **1000164**) |
| **Component** | `@ctcommon/ctimage` **8.94.6-beta.20260729205823** |
| **Entry** | module `Phone` / ability `CTEntryAbility` |
| **Error** | `RangeError: Stack overflow!` |
| **Channel** | Hiview faultlogger **jscrash** |

---

## 1. Title (ticket)

```
[Harmony][ctimage 8.94.6-beta] CTImage onImageOptionChange ↔ transUrl synchronous loop causes RangeError Stack overflow (jscrash) on cold start / home image bind
```

---

## 2. Summary

When 携程 Harmony cold-starts into `CTEntryAbility` and home image cells bind, shared component **`@ctcommon/ctimage`** enters a **synchronous reactive feedback loop**:

`onImageOptionChange` → `configBeforeShow` → `configCommonParams` → `transUrl` → observed state `set` / ArkUI notify → **`onImageOptionChange` again** → …

until the JS engine throws:

```text
RangeError: Stack overflow!
```

Hiview records this as:

```text
/data/log/faultlog/faultlogger/jscrash-com.ctrip.harmonynext-*.log
```

### UI honesty (important for triage)

The app **often still shows a usable home UI** after the event (ability may recover).  
**“Looks normal on screen” does not refute the bug.**  
Ground truth is **faultlogger jscrash + identical CTImage stack**, not a permanent black screen.

---

## 3. Environment

| Item | Value |
|------|--------|
| Device | HUAWEI Mate 80 Pro (`SGT-AL00B`) |
| Serial (lab) | `5SM0125606000291` |
| OS build (lab) | `SGT-AL00B 7.0.0.100(SP8C00E32R3P2log)` |
| Package | `com.ctrip.harmonynext` |
| VersionName / Code | `8.94.6` / `1000164` |
| Module / Ability | `Phone` / `CTEntryAbility` |
| CTImage lib | `@ctcommon/ctimage\|8.94.6-beta.20260729205823` |
| Discovery | Kea2 Mode A property campaign + bare `hdc` cold start |

---

## 4. Steps to reproduce (no Kea required)

```bash
# 0) device unlocked, hdc connected
hdc list targets

# 1) fully stop
hdc shell aa force-stop com.ctrip.harmonynext

# 2) cold start official entry
hdc shell aa start -a CTEntryAbility -b com.ctrip.harmonynext -m Phone

# 3) wait 5–30 seconds (home / image bind)

# 4) check newest JS crash
hdc shell ls -lt /data/log/faultlog/faultlogger | head
hdc shell cat /data/log/faultlog/faultlogger/jscrash-com.ctrip.harmonynext-*.log | head -n 100
```

Or use the script in this folder:

```bash
bash bug_reports/com.ctrip.harmonynext_ctimage_stack_overflow/repro.sh
```

### Pass / fail

| Result | Criteria |
|--------|----------|
| **FAIL** | New `jscrash-com.ctrip.harmonynext-*.log` with `Error message: Stack overflow!` and CTImage frames below |
| **PASS** | No new jscrash with that signature after cold start |

UI may remain on home after FAIL — still FAIL.

---

## 5. Expected vs actual

| | |
|--|--|
| **Expected** | Image option / URL normalize runs at most once per real input change; no jscrash |
| **Actual** | Option-apply path re-enters itself until JS stack overflows; faultlogger records jscrash |
| **User-visible** | Brief hitch / silent recovery possible; **not** always a stuck dead app |
| **System-visible** | **jscrash** with stable CTImage stack |

---

## 6. Actual crash (canonical excerpt)

From device faultlogger  
`jscrash-com.ctrip.harmonynext-20020314-20260806175500312.log`  
(also mirrored in this folder):

```text
Module name: com.ctrip.harmonynext
Version: 8.94.6
VersionCode: 1000164
Foreground: Yes
Process life time: 2s
Reason: RangeError
Error name: RangeError
Error message: Stack overflow!

App frames (stable):
  at originImageAlt     (@ctcommon/ctimage|...|CTImage.ts:134:31)
  at configBeforeShow   (@ctcommon/ctimage|...|CTImage.ts:388:1)
  at onImageOptionChange(@ctcommon/ctimage|...|CTImage.ts:172:14)
  at configCommonParams (@ctcommon/ctimage|...|CTImage.ts:418:1)
  at configBeforeShow   (@ctcommon/ctimage|...|CTImage.ts:390:14)
  at onImageOptionChange(@ctcommon/ctimage|...|CTImage.ts:172:14)
  at transUrl           (@ctcommon/ctimage|...|CTImageLoader.ts:54:1)
  at configCommonParams (@ctcommon/ctimage|...|CTImage.ts:421:27)
  … ArkUI stateMgmt set / notifyPropertyHasChanged / viewPropertyHasChanged …
  … back into onImageOptionChange …
```

Same signature also captured in lab crash-dumps (see Evidence).

---

## 7. Root cause analysis

### 7.1 Loop (from stack)

```text
onImageOptionChange          CTImage.ts ~172
  → configBeforeShow         CTImage.ts ~388 / ~390
    → configCommonParams     CTImage.ts ~418 / ~421
      → transUrl             CTImageLoader.ts ~54
        → writes observed image option / URL / alt state
          → ArkUI notify (stateMgmt.js set/notify…)
            → onImageOptionChange   ← re-entered synchronously
              → … unbounded …
                → RangeError: Stack overflow!
```

Also on path: `originImageAlt` (`CTImage.ts:134`) writing observed alt state during configure.

### 7.2 Why this is illegal

Classic **observed-state feedback cycle**:

1. Handler runs because image **options changed**.
2. Handler (via `transUrl` / `configCommonParams`) **writes fields that are part of the same observed options** (or always look changed).
3. Write notifies subscribers **synchronously**.
4. Same handler is re-entered **before the previous call returns**.
5. Stack grows until JS throws.

This is **not** “too many images” and **not** network slowness.  
It is **unbounded synchronous recursion** through state notification.

### 7.3 Defective shape (conceptual)

```ts
// defective pattern (illustrative — not source dump)
onImageOptionChange(opt) {
  const url2 = transUrl(opt.url);  // derive
  this.option.url = url2;          // write observed option → notifies again
  this.originImageAlt = ...;       // another observed write on same path
}
```

If there is **no equality guard** before write, or `transUrl` always produces a “new” observed identity, the loop never terminates.

### 7.4 Ownership

| Layer | Role |
|-------|------|
| ArkUI `stateMgmt.js` | Notification bus (normal) |
| **`@ctcommon/ctimage`** | **Root cause** — write observed options from inside option-change path |
| Kea2 / hdc | Only launcher / crash collector |

No test-framework frames appear in the stack.

---

## 8. Suggested fix (component owners)

In `@ctcommon/ctimage` (`CTImage.ts`, `CTImageLoader.ts`), tag `8.94.6-beta.20260729205823`:

1. **Equality guard before any observed write**  
   If normalized URL/options equal current → **return** (no `set`).

2. **Do not assign back into the observed option object from `onImageOptionChange` without a change check.**

3. **Split pure compute vs commit**
   - `transUrl` = pure (no observed writes)
   - commit once at the boundary

4. **Regression test**
   - Bind `CTImage` with a URL that `transUrl` rewrites  
   - Assert option-change / set count is bounded (e.g. ≤ 1–2)

Primary lines from production stacks (verify in your tree):

| File | Lines / symbol |
|------|----------------|
| `CTImage.ts` | `onImageOptionChange` ~172 (also ~171) |
| `CTImage.ts` | `configBeforeShow` ~388 / ~390 |
| `CTImage.ts` | `configCommonParams` ~418 / ~421 |
| `CTImage.ts` | `originImageAlt` ~134 |
| `CTImageLoader.ts` | `transUrl` ~54 |

---

## 9. Evidence files (this folder)

| File | What |
|------|------|
| `jscrash-com.ctrip.harmonynext-20020314-20260806175500312.log` | **Native Hiview jscrash** pulled from device |
| `crash-dump_multiv5_20260806_170604.log` | Kea2 Mode A V5 capture (same stack family) |
| `crash-dump_b8_20260805_170832.log` | Earlier B8 capture |
| `crash-dump_b7_20260805_161018.log` | Earlier B7 capture |
| `repro.sh` | One-shot cold-start repro + crash check |
| `BUG_REPORT.md` | This document |

Lab originals also under:

```text
modeA_runs/props_out/com.ctrip.harmonynext_*/res_*/output_*/crash-dump.log
```

### Repeatability notes (lab)

- Same stack across **2026-08-05** and **2026-08-06**.
- Process life at crash often **2–12s** on cold start (also seen later).
- Bare `aa force-stop` + `aa start -a CTEntryAbility …` sufficient (no property pack required).
- Home UI can dump successfully **after** jscrash files exist → treat as **crash-with-possible-recovery**.

---

## 10. Impact

| Area | Impact |
|------|--------|
| Stability | Foreground **jscrash** in shared image stack used by home |
| UX | May glitch / recover; users may not see a dialog |
| Telemetry | Should count as JS crash even if UI self-heals |
| Blast radius | Any page using `@ctcommon/ctimage` option transform path |
| Testing | Found by Kea2 Mode A; **repro does not depend on Kea2** |

---

## 11. Rebuttals (pre-answered)

| Pushback | Response |
|----------|----------|
| “App looks normal” | Check faultlogger; recovery ≠ absence of crash |
| “Only your fuzzer” | `hdc` cold start alone reproduces |
| “ArkUI bug” | Notify is the bus; illegal write-from-observer is in CTImage |
| “Not user-facing” | Foreground jscrash on home image bind is stability debt |
| “Need screenshot of dead app” | Wrong bar; attach jscrash log + stack |

---

## 12. Reporter

- Found via **Kea2** Harmony Mode A (property + crash watcher) on real device  
- Minimal repro: **hdc only**  
- Contact / lab path: this repository folder  

**Please fix in `@ctcommon/ctimage` and ship a build where cold-start no longer emits this jscrash signature.**
