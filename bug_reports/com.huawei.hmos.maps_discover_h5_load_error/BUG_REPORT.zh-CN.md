# 缺陷报告：地图发现 H5 榜单加载失败（困住 UI）

| 字段 | 值 |
|---|---|
| **产品** | 华为地图 |
| **包名** | `com.huawei.hmos.maps.app` |
| **平台** | HarmonyOS NEXT |
| **设备（实验室）** | `5SM0125606000291` |
| **严重程度** | **中** — 发现路径死胡同；用户须离开应用 |
| **组件** | 发现标签 → H5 榜单（`h5hosting-drcn.dbankcdn.cn/.../rankings`） |
| **状态** | Kea2 随机探索中观察到 |
| **报告日期** | 2026-07-21 |
| **发现方式** | `pi-pbt kea` Phase B（零执行活动） |

## 摘要

打开 / 进入 **发现** 榜单 H5 页时显示 **“Loading error. Retry”**（或卡在加载中）。在 Kea2 探索下，应用反复无法回到健康的原生首页层级（`weak/launcher hierarchy … relaunch` 循环），导致本轮剩余时间所有 T0 前置条件均为 false。

冷启动白屏探测：**0/8** — 非白屏绘制缺陷；属 **发现 H5 加载 / 困住** 问题。

## 影响

- 用户进入发现榜单内容 → 错误 / 卡住。
- 恢复须离开 H5 界面（返回 / 杀进程）；随机导航易使会话搁浅。

## 复现（实验室）

1. 启动地图（`com.huawei.hmos.maps.app`）。
2. 点击 **发现**（或探索直至榜单 H5 打开）。
3. 观察加载错误 / 无法得到稳定原生首页 dump。

```bash
# automated signal: kea2 run with home-tab props often hits zero-exec
# when explorer enters Discover H5 — see kea.log hits
```

## 证据

- `evidence/kea_log_hits.txt` — 提及 H5 / relaunch 的日志行
- 活动：`~/harmonyy-app/maps/pbt-out/REPORT.md`（not_checked e=0）

## 备注

- 非崩溃（Kea2：未发现崩溃）。
- 与此前修复的 POI 关闭竞态不同。
