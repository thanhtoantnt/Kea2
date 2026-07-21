# Reproduce Kea2 HarmonyOS campaign results

Self-contained package to **re-run the same Kea2 property campaign** used in the lab (T0 home-tab properties on real third-party HarmonyOS apps).

| | |
|---|---|
| **Engine** | Kea2 (`--platform harmony`) |
| **Device** | USB HarmonyOS NEXT + `hdc` |
| **What is reproduced** | Non-vacuous property execution on guest-home apps; optional tongxin blank cold-start |
| **What is *not* required** | `pi-pbt`, LLM agent, AppGallery login |

---

## Prerequisites

1. **Host**
   - macOS/Linux
   - `hdc` on `PATH` (DevEco / HarmonyOS toolkit)
   - Python 3.10+
   - Kea2 installed with venv:

     ```bash
     cd /path/to/Kea2
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -e ".[harmony]"   # or project’s documented deps (hmdriver2, …)
     # confirm:
     .venv/bin/kea2 --help
     ```

2. **Device**
   - USB debugging on, one phone Connected: `hdc list targets`
   - Screen unlocked (or swipe-unlockable; script wakes + swipe)
   - **Target apps installed** (see [apps.tsv](./apps.tsv))

3. **Optional (tongxin blank only)**
   - `pip install pillow numpy`
   - App `com.csai.tongxin` installed

---

## Quick start

```bash
cd bug_reports/harmony_campaign_repro

# 1) See which campaign apps are on the phone
bash run_repro.sh --list

# 2) Run all *installed* apps from apps.tsv (default 15 events each)
bash run_repro.sh

# 3) Or only some names
bash run_repro.sh maoyan wps

# 4) Also probe tongxin blank cold-start (separate hdc script)
bash run_repro.sh --tongxin-blank
```

Outputs land in `out_<timestamp>/`:

| Path | Content |
|---|---|
| `SUMMARY.md` | Table: status / exec / fail / err vs lab |
| `RESULTS.json` | Machine-readable per-app `LAST_RUN` |
| `<app>/kea.log` | Full Kea2 log |
| `<app>/res_*/` | Kea2 result dir + bug_report.html |

Override device / Kea2 / events:

```bash
export DEVICE=5SM0125606000291          # or PBT_KEA_DEVICE
export KEA2_HOME=/path/to/Kea2
export EVENTS=20
export OUT_ROOT=/tmp/kea2-repro
bash run_repro.sh maoyan
```

---

## What the script does

For each selected app in `apps.tsv` that is **installed**:

1. Wake screen + swipe keyguard (best-effort).
2. `aa force-stop` → `aa start` (ability from `bm dump` / `EntryAbility`).
3. Best-effort dismiss: 同意 / Deny / 关闭 / …
4. Run:

   ```text
   kea2 run --platform harmony -s <serial> -p <package> \
     --max-step <EVENTS> --throttle 700 \
     -o out/<app> \
     propertytest discover -s properties/ -p prop_<app>.py
   ```

5. Write `LAST_RUN.json` + append row to `SUMMARY.md`.

Apps **not installed** are skipped (not failed).

---

## Lab baseline

Clean T0 runs from the original campaign (manual properties + Kea2 runner).  
Your repro should land near these numbers (± flake).

| name | package | lab status | lab exec | properties (idea) |
|---|---|---|---:|---|
| maoyan | `com.maoyan.hmovie` | ran_ok | 15 | 首页↔我的, 首页↔演出 |
| wps | `cn.wps.mobileoffice.hap` | ran_ok | 13 | 首页↔我, 首页↔云盘 |
| taobaomovie | `com.taobao.movie.hongmeng` | ran_ok | 15 | 首页↔我的, 首页↔影院 |
| husky | `com.yuantiku.husky.hos` | ran_ok | 15 | 首页 present, 数/语 subjects |
| meitanjianghu | `com.meitanjianghu.mtjh` | ran_ok | 15 | 首页↔我的, 推荐 visible |
| qunar | `com.qunar.hos` | ran_ok | 15 | 首页↔我的, 首页↔行程 |

### Tongxin SUT bugs (separate)

Not T0-tab pass/fail — **real app defects** with their own packages:

| Bug | Dir | Repro |
|---|---|---|
| Blank white cold start (~47% @10s) | [../com.csai.tongxin_blank_cold_start](../com.csai.tongxin_blank_cold_start/) | `bash repro_blank_cold_start.sh 15 10` |
| Tabs unresponsive | [../com.csai.tongxin_tabs_unresponsive](../com.csai.tongxin_tabs_unresponsive/) | see that README |
| WeChat handoff | [../com.csai.tongxin_wechat_handoff](../com.csai.tongxin_wechat_handoff/) | see that README |

```bash
# from this folder:
bash run_repro.sh --tongxin-blank
# or directly:
bash ../com.csai.tongxin_blank_cold_start/repro_blank_cold_start.sh 15 10
```

---

## Interpreting results

| status | meaning |
|---|---|
| **ran_ok** | exec &gt; 0, fail=0, error=0 — matches clean lab |
| **failing** | assertion failed — check flaky multi-click settle or real UI change |
| **test_bug** | driver/selector error (e.g. ElementNotFound) |
| **not_checked** / exec=0 | precondition never true (login wall, privacy, wrong language) |
| **skipped** | package not on device |

**Success criterion for “reproduced campaign”:**  
for each installed baseline app, `executed_total ≥ min_exec` in `apps.tsv` and `fail_total=0` (small flake 1/N cold-first click is known on some apps).

---

## Property files

All under [`properties/`](./properties/). Pattern:

```python
import time, unittest
from kea2 import precondition

class FooProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # dismiss privacy; land 首页
        ...

    @precondition(lambda self: self.d(text="首页").exists() and self.d(text="我的").exists())
    def test_home_me_roundtrip(self):
        self.d(text="我的").click(); time.sleep(0.6)
        assert self.d(text="我的").exists() or self.d(text="首页").exists()
        ...
```

Rules used in lab (and why scripts stay green):

- **T0 only** — bottom tabs / home chrome; no search boxes, no login.
- **Check-before-explore** is inside current Kea2 Harmony path (need recent Kea2).
- Short `sleep` after clicks (0.6–0.9s) for tab animation.

---

## Add another app

1. Install app on device.  
2. Dump UI: `hdc shell uitest dumpLayout …` — note bottom tab texts.  
3. Add `properties/prop_<name>.py` (copy maoyan template).  
4. Append a row to `apps.tsv`.  
5. `bash run_repro.sh <name>`

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no hdc device` | cable, `hdc list targets`, kill stale `hdc start` |
| `screen locked` | unlock phone; script swipe may fail with PIN |
| exec=0 always | privacy/login blocking home; dismiss manually once; check dump texts |
| empty dump JSON errors | use Kea2 ≥ commit with empty-hierarchy retry (`hmDriver.dump_hierarchy`) |
| AppGallery “can’t install” | app not compatible — cannot repro that package on this SKU |
| Retail demo / samplemanagement UI | leave demo mode; campaign STOP condition |

---

## Layout

```text
harmony_campaign_repro/
  README.md           ← this file
  run_repro.sh        ← one-shot runner
  apps.tsv            ← package ↔ property map + lab baseline
  properties/         ← unittest + @precondition modules
  out_*/              ← created at runtime (gitignored preferred)
```

Related: parent index [`../README.md`](../README.md).
