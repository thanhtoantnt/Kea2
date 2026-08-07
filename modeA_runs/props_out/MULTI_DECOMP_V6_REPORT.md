# Mode A V6 multi-app report

## Setup
- 13 decompiled-signal apps, 5 min / max 60 steps, throttle 200
- packs: lean decompiled+bug_find+flow (+ ctrip_ctimage / calculator_decompiled)
- 1 prop/step, dump-cache fixes from V5
- batch never aborts on single-app fail
- device unlocked mid-session; idlefish uninstalled after batch (HK login wall)

## KPI vs prior full batches

| metric | V2 | V5 | **V6** |
|--------|----|----|--------|
| avg fire% | 54.6 | 46.1 | **58.0** |
| avg steps | 27 | 24.7 | **54.6** |
| avg execs | 77.6 | 24.5 | **54.6** |
| avg decomp_ex | 45.1 | 16.8 | **35.8** |
| fails sum | 3 | 0 | **1** |
| crash sum | 0 | 1 | **0** |
| avg widgets | 13.3 | 12.8 | **19.2** |

V6 decomp share ≈ **65.6%** of execs.

## Per-app V6

| app | steps | fire% | execs | decomp | fails | crash | widgets |
|-----|------:|------:|------:|-------:|------:|------:|--------:|
| `com.amap.hmapp` | 59 | 70.8 | 58 | 31 | 0 | 0 | 15 |
| `com.sankuai.dianping` | 59 | 70.8 | 59 | 31 | 0 | 0 | 22 |
| `com.zhihu.hmos` | 59 | 50.0 | 58 | 41 | 0 | 0 | 21 |
| `com.sina.weibo.stage` | 59 | 66.7 | 60 | 33 | 0 | 0 | 22 |
| `com.sankuai.hmeituan` | 59 | 50.0 | 59 | 42 | 0 | 0 | 31 |
| `com.phoenix.read.next` | 24 | 45.8 | 24 | 16 | 1 | 0 | 5 |
| `com.youku.next` | 59 | 41.7 | 57 | 43 | 0 | 0 | 3 |
| `com.xunmeng.pinduoduo.hos` | 59 | 50.0 | 59 | 41 | 0 | 0 | 24 |
| `com.kuaishou.hmapp` | 59 | 45.8 | 60 | 41 | 0 | 0 | 33 |
| `com.ss.hm.ugc.aweme` | 59 | 58.3 | 60 | 42 | 0 | 0 | 21 |
| `com.huawei.hmos.calculator` | 59 | 73.9 | 60 | 49 | 0 | 0 | 15 |
| `com.ctrip.harmonynext` | 59 | 71.4 | 60 | 39 | 0 | 0 | 20 |
| `com.taobao.idlefish4ohos` | 37 | 58.3 | 36 | 16 | 0 | 0 | 17 |

## Headline

- **Best throughput so far:** avg steps **54.6** (hit max-step 60 on most apps; ~2–4s/step when unlocked).
- **fire% 58.0** — beats V5 (46.1) and V2 (54.6) at same lean pack.
- **fails=1** (phoenix only); **crash flag sum=0** this TSV (ctrip no crash bit this run).
- decomp_execs avg **35.8** (share ~65.6%).
- phoenix still thinner (24 steps) — login tarpit.
- idlefish finished in batch then user uninstalled (Mainland login / HK).
- remaining installed still has 12/13 decomp targets (no idlefish).

## Queue change (post-V6)

Dropped from `run_multi_decomp_v6.sh` default QUEUE:
- `com.taobao.idlefish4ohos` — Mainland-only login / unusable in HK
- `com.phoenix.read.next` — hard login tarpit (thin steps)

Future multi-app default = **11 apps** (guest-usable + ctrip/calculator).

## Files

- TSV: `modeA_runs/props_out/MULTI_DECOMP_V6_20260807_092014.tsv`
- script: `modeA_runs/run_multi_decomp_v6.sh`
