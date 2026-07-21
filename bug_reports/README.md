# Kea2 bug reports & campaign repro

Artifacts from real-device HarmonyOS testing with **Kea2** as the runner.

## Reproduce the lab campaign (start here)

**[harmony_campaign_repro/](./harmony_campaign_repro/)** — script + doc + property files.

```bash
cd bug_reports/harmony_campaign_repro
bash run_repro.sh --list          # which apps installed
bash run_repro.sh                 # run all installed baseline apps
bash run_repro.sh maoyan wps      # subset
bash run_repro.sh --tongxin-blank # + tongxin blank cold-start probe
```

Full instructions: **[harmony_campaign_repro/README.md](./harmony_campaign_repro/README.md)**.

---

## Confirmed SUT bugs (`com.csai.tongxin`)

| ID | Summary | Path |
|---|---|---|
| blank cold start | Intermittent full-white UI after force-stop/start (~47% @10s) | [com.csai.tongxin_blank_cold_start](./com.csai.tongxin_blank_cold_start/) |
| tabs unresponsive | Bottom tabs: scroll works, tap no content change | [com.csai.tongxin_tabs_unresponsive](./com.csai.tongxin_tabs_unresponsive/) |
| WeChat handoff | Primary CTA leaves SUT → WeChat | [com.csai.tongxin_wechat_handoff](./com.csai.tongxin_wechat_handoff/) |
| blank cold start | Intermittent full-white UI after force-stop/start (~62% @10s) | [com.ruixin.huawei_blank_cold_start](./com.ruixin.huawei_blank_cold_start/) |

Each folder has `BUG_REPORT.md` and a `repro_*.sh` where applicable.

---

## Requirements (all repros)

- HarmonyOS NEXT phone + USB `hdc`
- Kea2 checkout with working `.venv` (`kea2 run --platform harmony …`)
- Apps under test **installed** on the device
- Unlocked screen

Agent/`pi-pbt` is **not** required to reproduce these results.
