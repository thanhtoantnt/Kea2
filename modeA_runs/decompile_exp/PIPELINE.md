# General pipeline: app → decompile → properties → Mode A

```
HAP/ABC  ──►  decompile (lab-vps xabc)  ──►  arkdemo*.ts
                │                              │
                └── string mine (always)  ──►  mined_all/ + signals.json
                                               │
                                               ▼
                                    generate_props_from_decompile.py
                                               │
                                               ▼
                                    properties/modeA_props/decompiled.py
                                    (+ app-specific packs when needed)
                                               │
                                               ▼
                                    kea2 run propertytest  (Mode A / phone)
```

## 1) Inputs

| input | path |
|-------|------|
| ABC | `saved_abc/<pkg>/modules.abc` |
| HAP (optional) | `saved_haps/<pkg>/` |
| xabc binary | lab-vps `/home/toan/harmonyos/out/x64.release/arkcompiler/common/xabc` |
| arkdecompiler | lab-vps `/home/toan/github/arkdecompiler` |

## 2) Decompile (lab-vps)

```bash
ssh lab-vps 'bash /home/toan/decompile_work/decompile_all.sh'
# or one app:
# XABC_NAMES_ONLY=1 XABC_SKIP_LITERALS=1 xabc modules.abc out.ts
```

### Output quality tiers

| tier | what | apps (current) |
|------|------|----------------|
| **A full AST** | real ArkTS-ish bodies | calculator |
| **B name index** | `// record:` / `// method:` lines | ctrip, amap*, dianping, zhihu, idlefish, phoenix… |
| **C mine only** | strings from abc (no xabc) | kuaishou/douyin/meituan when xabc dies |

\*amap can produce large dumps; treat as B/partial.

Env flags on xabc (store abc robustness):
- `XABC_SKIP_LITERALS=1` — skip fragile literal tables  
- `XABC_NAMES_ONLY=1` — class names only (no method bodies)

Patches live on lab-vps harmonyos tree + arkdecompiler (GetRecords skip bad class idx, ETS_IMPLEMENTS, soft literal tags, CollectInfo skip, names fallback).

## 3) Local: mine + signals + props

```bash
# string mine all abc (mac)
python modeA_runs/decompile_exp/mine_all_abc.py   # or existing mined_all/

# merge xabc dumps into signals
python modeA_runs/decompile_exp/generate_props_from_decompile.py

# offline gate
python modeA_runs/decompile_exp/offline_check.py
```

`generate_props_from_decompile.py` reads for each pkg:
1. `xabc_out/decompiled/<pkg>/arkdemo.ts` (and `.names.ts`)
2. `mined_all/<pkg>/*`
3. writes `mined_all/<pkg>/signals.json` + optional `properties/modeA_props/generated/<pkg>.py`

Runtime pack: `properties.modeA_props.decompiled` loads `signals.json` via `KEA2_TARGET_PKG`.

## 3.5) Gate (required)

**Mode A and Mode B abort** if `mined_all/<pkg>/signals.json` is missing.
Installed app alone is not enough — decompile/mine first.

```bash
PYTHONPATH=. python -m properties.modeA_props.decompile_gate com.example.app
# exit 0 = ok; exit 2 = abort
```

## 4) Mode A run (phone)

```bash
bash modeA_runs/run_decompiled_campaign.sh
```

## 5) Ctrip example paths

| artifact | path |
|----------|------|
| ABC | `saved_abc/com.ctrip.harmonynext/modules.abc` |
| xabc dump | `xabc_out/decompiled/com.ctrip.harmonynext/arkdemo.ts` (name index) |
| mine | `mined_all/com.ctrip.harmonynext/ctimage_hits.txt` |
| signals | `mined_all/com.ctrip.harmonynext/signals.json` |
| props | `properties/modeA_props/ctrip_ctimage.py` + `decompiled.py` |

## Lab-vps batch result (all saved apps)

```bash
ssh lab-vps 'bash /home/toan/decompile_work/decompile_all.sh'
# summary: modeA_runs/decompile_exp/XABC_BATCH_SUMMARY.tsv
```

| pkg | tier | size |
|-----|------|------|
| calculator | **A_ast** | 801K |
| amap | B_names | 323K |
| ctrip | B_names | 447K |
| kuaishou | B_names | 1.4M |
| phoenix | B_names | 1.2M |
| dianping | B_names | 652K |
| meituan | B_names | 798K |
| weibo | B_names | 487K |
| douyin | B_names | 2.6M |
| idlefish | B_names | 339K |
| pdd | B_names | 247K |
| youku | B_light | 6.1M |
| zhihu | B_names | 233K |

**13/13 non-empty decompiled outputs.** Props regen: `generate_props_from_decompile.py` → `ALL_OFFLINE_OK`.

## xabc robustness (arkdecompiler + runtime_core patches on lab-vps)

Env: `XABC_NAMES_ONLY=1` · `XABC_SKIP_LITERALS=1` · `XABC_LIGHT=1`

Patches: skip OOB class idx, ClampSourceLang, soft THROW_IF / unknown-lang metadata, LightDumpClassNames fallback, DumpNamesFallback always.
Notes: `/home/toan/github/arkdecompiler/XABC_ROBUST.md`

## Limits (honest)

- Full AST only calculator today; store apps = name/string index (enough for prop oracles).
- Method bodies still abort on many store abc (proto/uleb) — names path avoids that.
- Upgrade = more MethodDataAccessor soft-fail → tier A for store apps; prop pipeline unchanged.
