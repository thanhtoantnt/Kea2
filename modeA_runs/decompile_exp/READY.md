# Decompile → Kea2 — ready when phone connects

## Offline (done, no phone)

| asset | path |
|-------|------|
| ABC dumps (13 apps) | `saved_abc/<pkg>/modules.abc` |
| String mine | `mined_all/<pkg>/{labels,hits,methods,classes,ctimage}*` |
| Clean signals | `mined_all/<pkg>/signals.json` |
| Calculator xabc AST | `calculator_xabc/arkdemo{,_app}.ts` |
| Generic mine props | `properties/modeA_props/decompiled.py` |
| Ctrip CTImage props | `properties/modeA_props/ctrip_ctimage.py` |
| Calculator props | `properties/modeA_props/calculator_decompiled.py` |
| Offline gate | `python modeA_runs/decompile_exp/offline_check.py` → `ALL_OFFLINE_OK` |
| Campaign | `modeA_runs/run_decompiled_campaign.sh` |
| Queue | auto-created `modeA_runs/decompiled_queue.txt` |

Rebuild signals after re-mine:
```bash
python modeA_runs/decompile_exp/build_signals.py
python modeA_runs/decompile_exp/offline_check.py
```

## Phone connect — one command

```bash
# optional: SERIAL=... MINS=4 MAXSTEP=50
bash modeA_runs/run_decompiled_campaign.sh
```

Runs offline_check first, then each queue pkg with:
`KEA2_TARGET_PKG=<pkg> kea2 run -p <pkg> propertytest decompiled [+ specialized]`

Ctrip pack stresses home image scroll/tab hop (B7 CTImage path).
Calculator pack uses digit/history/div0 oracles.

## Limits

- Full xabc `.ts` only for calculator (store abc → runtime UNREACHABLE).
- Store apps use **string mine signals**, not full AST — enough for label/error/search oracles + CTImage symbol gate.
- Device still required to **execute** props; everything else is pre-baked.
