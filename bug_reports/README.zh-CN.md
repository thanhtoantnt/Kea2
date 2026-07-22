# Kea2 缺陷报告与活动复现

基于真实设备 HarmonyOS 测试的产物，**Kea2** 作为运行器。

## 复现实验室活动（从这里开始）

**[harmony_campaign_repro/](./harmony_campaign_repro/)** — 脚本 + 文档 + 属性文件。

```bash
cd bug_reports/harmony_campaign_repro
bash run_repro.sh --list          # 哪些应用已安装
bash run_repro.sh                 # 运行所有已安装的基线应用
bash run_repro.sh maoyan wps      # 子集
bash run_repro.sh --tongxin-blank # + 同欣空白冷启动探测
```

完整说明：**[harmony_campaign_repro/README.md](./harmony_campaign_repro/README.md)**。

---

## 已确认的 SUT 缺陷（`com.csai.tongxin`）

| ID | 摘要 | 路径 |
|---|---|---|
| blank cold start | 强制停止/启动后间歇性全白界面（约 47% @10s） | [com.csai.tongxin_blank_cold_start](./com.csai.tongxin_blank_cold_start/) |
| tabs unresponsive | 底部标签：可滚动，点击无内容变化 | [com.csai.tongxin_tabs_unresponsive](./com.csai.tongxin_tabs_unresponsive/) |
| WeChat handoff | 主 CTA 离开 SUT → 微信 | [com.csai.tongxin_wechat_handoff](./com.csai.tongxin_wechat_handoff/) |
| blank cold start | 强制停止/启动后间歇性全白界面（约 62% @10s） | [com.ruixin.huawei_blank_cold_start](./com.ruixin.huawei_blank_cold_start/) |

各文件夹含 `BUG_REPORT.md`，适用时含 `repro_*.sh`。

---

## 环境要求（所有复现）

- HarmonyOS NEXT 手机 + USB `hdc`
- 已检出 Kea2 且 `.venv` 可用（`kea2 run --platform harmony …`）
- 被测应用**已安装**在设备上
- 屏幕已解锁

复现这些结果**不需要** Agent/`pi-pbt`。

### 地图发现 H5

| load error trap | 发现榜单 H5 | [com.huawei.hmos.maps_discover_h5_load_error](./com.huawei.hmos.maps_discover_h5_load_error/) |
