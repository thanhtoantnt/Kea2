# Decompile / mine inventory
## Full xabc AST (lab-vps)
| app | status | local path |
|-----|--------|------------|
| calculator | OK 801K ts | `calculator_xabc/` |
| store apps (ctrip, amap, …) | xabc **ABORT** UNREACHABLE on open | — |

## String mine all ABCs (local, no phone)
Path: `mined_all/<pkg>/{strings_hits,labels_cjk,methods_like,classes_like,ctimage_hits,META}.`

| pkg | abc MB | strings | hits | cjk labels | ctimage-ish |
|-----|--------|---------|------|------------|-------------|
| com.amap.hmapp | 18.51 | 177120 | 3000 | 800 | 20 |
| com.ctrip.harmonynext | 39.77 | 302022 | 3000 | 800 | 247 |
| com.huawei.hmos.calculator | 2.34 | 18293 | 1916 | 0 | 1 |
| com.kuaishou.hmapp | 90.11 | 653735 | 3000 | 800 | 148 |
| com.phoenix.read.next | 65.95 | 554855 | 3000 | 800 | 16 |
| com.sankuai.dianping | 47.59 | 371701 | 3000 | 800 | 35 |
| com.sankuai.hmeituan | 59.42 | 456647 | 3000 | 800 | 13 |
| com.sina.weibo.stage | 53.45 | 407661 | 3000 | 800 | 9 |
| com.ss.hm.ugc.aweme | 182.39 | 1265861 | 3000 | 800 | 71 |
| com.taobao.idlefish4ohos | 25.05 | 206440 | 3000 | 800 | 92 |
| com.xunmeng.pinduoduo.hos | 27.13 | 231706 | 3000 | 800 | 25 |
| com.youku.next | 106.48 | 366399 | 3000 | 800 | 30 |
| com.zhihu.hmos | 35.25 | 270408 | 3000 | 800 | 14 |

## Kea2 wiring (offline-ready)
- `build_signals.py` → `mined_all/<pkg>/signals.json`
- Props: `properties/modeA_props/{decompiled,ctrip_ctimage,calculator_decompiled}.py`
- Gate: `offline_check.py` → `ALL_OFFLINE_OK`
- Run when phone up: `bash modeA_runs/run_decompiled_campaign.sh`
- See `READY.md`

## Notes
- Calculator only app xabc fully decompiles today (system app, simpler abc).
- Store `modules.abc` trip `ABORT_AND_UNREACHABLE` immediately in panda runtime — likely newer opcode/format vs xabc tree.
- For Kea2 props: use `signals.json` (tabs/errors/search/empty); ctrip `has_ctimage=true` gates CTImage pack.
- Source ABCs: `saved_abc/`. HAPs: `saved_haps/`.
