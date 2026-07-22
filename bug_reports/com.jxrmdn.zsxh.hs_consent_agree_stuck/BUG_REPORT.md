# BUG — Agree path does not dismiss privacy consent dialog (掌上西湖)

- **Severity:** HIGH
- **App:** com.jxrmdn.zsxh.hs (掌上西湖 / Zhangshang Xihu)
- **Device:** 5SM0125606000291 (HarmonyOS, hdc 3.2.0b)
- **Property:** `test_consent_agree_dismisses_dialog` → FAIL (assertion)
- **Oracle:** data_manipulation

## Symptom
On cold start, the privacy consent dialog (`温馨提示`) is shown. After checking the
agreement checkbox and tapping `同意并继续` (Agree and continue), the consent dialog
remains on screen — home is not reached.

## Steps
1. Launch `com.jxrmdn.zsxh.hs` (EntryAbility, SplashPage).
2. Wait for the `温馨提示` consent dialog.
3. Tap the agreement `Checkbox` at [244,1792][300,1848].
4. Tap `同意并继续` at [640,1950][1120,1999].
5. Observe: `温馨提示` dialog is still present after >1.2s.

## Evidence
- Kea2 assertion failed:
  `consent dialog still shown after 同意并继续` (`not self.d(text="温馨提示").exists()`).
- Reproduced manually during Scan: coordinate taps on checkbox + `同意并继续`
  (and on `不同意`) did not dismiss the dialog across multiple attempts.
- Run result: `pbt-out/kea-run/res_2026072212_5756264495/result_*.json`
  (executed=1, fail=1, error=0).
- Bug report HTML: `pbt-out/kea-run/res_2026072212_5756264495/bug_report.html`

## Impact
User cannot pass the first-run consent gate via the primary "Agree" action, so the
app is effectively blocked at cold start on this device/build (home unreachable).

## Caveat / classification
Assertion-violation → candidate **SUT bug**. If the checkbox requires a specific
checked state and `Checkbox` selector toggled it off, this could instead be a
weak test setup; however the manual reproduction (identical non-dismissal) makes a
genuine SUT defect the more likely cause.
