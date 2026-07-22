# 缺陷报告：冷启动间歇性白屏

| 字段 | 值 |
|---|---|
| **产品** | 通信工程师考试 (Communication Engineer Exam) |
| **包名** | `com.csai.tongxin` |
| **版本** | **1.0.1** (versionCode 101) |
| **分发渠道** | 华为应用市场 (Huawei AppGallery) |
| **平台** | HarmonyOS NEXT |
| **设备（实验室）** | 序列号 `5SM0125606000291` |
| **严重程度** | **高** — 应用不可用，直至强制停止 |
| **组件** | UNI-APP WebView 壳（`EntryAbility` → 本地 `www/` / `__UNI__AC14E7C`） |
| **状态** | 实验室已确认可复现 |
| **报告日期** | 2026-07-20 |
| **发现方式** | Kea2 / hdc 自动化冷启动活动 |

---

## 摘要

**冷启动**（强制停止后启动）后，应用进程已进入 **FOREGROUND**，但 UI 经常在 **≥10 秒** 内保持**整屏全白**（仅状态栏），无启动页、考试选择页、首页、加载指示或错误信息。

当缺陷**未**发生时，同一构建在同一设备上约 5 秒内绘制正常首页 UI。

**实验室复现率：7/15（46.7%）**，在 `aa start` 后固定观察 10 秒。

---

## 影响

- 用户打开应用后看到空白白屏。
- UI 内无恢复路径（无可点击内容）。
- 用户须强制停止并重新启动；可能需要多次尝试。
- 间歇性 → 用户难以描述；除非多轮测试，否则易被当作“手机慢”而忽略。

---

## 环境

- **系统：** HarmonyOS NEXT（实验室手机）
- **应用：** 来自应用市场的 `com.csai.tongxin` 1.0.1
- **入口：** `EntryAbility`
- **UI 栈：** 混合 UNI-APP WebView，加载  
  `file:///data/storage/el1/bundle/entry/resources/resfile/apps/__UNI__AC14E7C/www/`
- **测量工具：** `hdc`、`uitest screenCap`、截图像素白色占比

---

## 复现步骤（手动）

1. 从应用市场安装 **通信工程师考试** v1.0.1。
2. 解锁手机；保持屏幕常亮。
3. 打开应用一次，确认可出现正常 UI（首页或考试选择）。
4. 离开应用（主页 / 最近任务）。
5. **强制停止**应用：  
   **设置 → 应用 → 通信工程师考试 → 强制停止**  
   （或 `hdc shell aa force-stop com.csai.tongxin`）。
6. 从启动器再次启动应用  
   （或 `hdc shell aa start -a EntryAbility -b com.csai.tongxin`）。
7. **不要触摸屏幕。** 等待 **10 秒**。
8. 观察：
   - **缺陷：** 内容区全白（仅状态栏图标/时间）。
   - **正常：** 启动页 / “选择我的考试” / 首页（每日打卡、底部标签等）。
9. 重复步骤 5–8 **至少 10–15 次**。

### 预期
数秒内 Web 内容完成绘制（或显示加载/错误 UI）。

### 实际
大量冷启动中（实验室 @10s 约 **47%**）：内容区保持纯白；进程保持前台；无错误 UI。

---

## 复现步骤（自动化 / hdc）

```bash
# from this directory
bash repro_blank_cold_start.sh 15 10
# requires: hdc, python3, pillow, numpy
```

最小循环：

```bash
PKG=com.csai.tongxin
DEV=<serial>   # optional: hdc -t $DEV ...

for i in $(seq 0 14); do
  hdc shell aa force-stop "$PKG"
  sleep 1
  hdc shell aa start -a EntryAbility -b "$PKG"
  sleep 10
  hdc shell "uitest screenCap -p /data/local/tmp/t$i.png"
  echo "captured trial $i"
done
# Pull screenshots; blank = almost pure white image
```

实验室分类：将截图缩小至 64×128 RGB；若通道值 >248 的像素占比 **≥ 0.92** 且应用为 FOREGROUND，则判为 **blank**。

---

## 实验室结果（N=15，等待=10s）

| 轮次 | @10s 结果 | white_frac | 平均像素 | FOREGROUND | 文件 |
|---:|---|---:|---:|---|---|
| 0 | ok | 0.374 | 217.7 | True | `trial_00.png` |
| 1 | ok | 0.374 | 217.7 | True | `trial_01.png` |
| 2 | ok | 0.374 | 217.7 | True | `trial_02.png` |
| 3 | **BLANK** | 0.985 | 254.2 | True | `trial_03.png` |
| 4 | **BLANK** | 0.986 | 254.2 | True | `trial_04.png` |
| 5 | ok | 0.374 | 217.8 | True | `trial_05.png` |
| 6 | **BLANK** | 0.986 | 254.2 | True | `trial_06.png` |
| 7 | ok | 0.374 | 217.7 | True | `trial_07.png` |
| 8 | ok | 0.374 | 217.7 | True | `trial_08.png` |
| 9 | ok | 0.374 | 217.7 | True | `trial_09.png` |
| 10 | **BLANK** | 0.985 | 254.2 | True | `trial_10.png` |
| 11 | **BLANK** | 0.985 | 254.2 | True | `trial_11.png` |
| 12 | **BLANK** | 0.985 | 254.2 | True | `trial_12.png` |
| 13 | **BLANK** | 0.985 | 254.2 | True | `trial_13.png` |
| 14 | ok | 0.374 | 217.7 | True | `trial_14.png` |

- **BLANK：** 7  
- **OK：** 8  
- **比率：** 7/15（46.7%）  
- 原始 JSON：[`REPRO_RESULTS.json`](./REPRO_RESULTS.json)

### 视觉证据

| | |
|---|---|
| **缺陷** | [`evidence/BLANK_trial_03.png`](./evidence/BLANK_trial_03.png)（亦见 trials 04、06、10–13） |
| **正常对照** | [`evidence/OK_contrast_trial_00.png`](./evidence/OK_contrast_trial_00.png) — 正常首页，同一流程 |

**BLANK（trial 03）：** 内容纯白。  
**OK（trial 00）：** 完整首页 — 初级通信工程师、每日打卡、全真模拟、底部标签 会员/课程/学习/我的。

---

## 技术观察

1. **非原生崩溃 / ANR**  
   - 白屏轮次中 `aa dump` 显示包处于 **FOREGROUND**。  
   - 另一次 Kea2 冒烟（成功落地后坐标点击）20 步内**无崩溃**。

2. **WebView 壳未绘制**  
   - 空白/已加载壳上 `uitest dumpLayout` 显示 `Web` 节点 → 空的 `rootWebArea` / `genericContainer`（无可访问子节点/文本）。  
   - 空白由**截图像素**确认，非选择器抖动。

3. **同一构建上间歇出现**  
   - 同版本、同设备、同启动命令；OK 与 BLANK 交替。  
   - 提示竞态 / WebView 或 UNI-APP 运行时初始化问题，而非永久坏安装。

4. **OK 路径时序**  
   - 成功启动通常约 2s 离开“大多为白”的启动阶段，约 5–6s 显示真实 UI（`white_frac ≈ 0.37`）。  
   - 白屏轮次在 10s 时仍为 `white_frac ≈ 0.985`（此前亦观察到持续至 12s）。

---

## 开发者建议方向（非规定性）

- 确保 WebView 首绘超时后展示**原生加载或错误**界面（永不无限白屏）。  
- 冷启动时，当首内容绘制超过 N 秒，记录 UNI-APP / WebView 控制台与 Harmony hilog。  
- 检查 `force-stop`（完整进程死亡）后 `EntryAbility` 生命周期与 Web 引擎初始化之间的竞态。  
- 考虑在 JS bridge / 首页 `ready` 前保留原生启动页。  
- 验证白屏是否与内存压力、重启后首次启动或并发 Web 进程相关。

---

## 本文件夹附件

```
com.csai.tongxin_blank_cold_start/
├── BUG_REPORT.md                 (this file)
├── REPRO_RESULTS.json            (full trial metrics)
├── repro_blank_cold_start.sh     (repro script)
└── evidence/
    ├── BLANK_trial_03.png
    ├── BLANK_trial_04.png
    ├── BLANK_trial_06.png
    ├── BLANK_trial_10.png
    ├── BLANK_trial_11.png
    ├── BLANK_trial_12.png
    ├── BLANK_trial_13.png
    └── OK_contrast_trial_00.png
```

---

## 联系 / 方法说明

在 HarmonyOS GUI 基于属性测试中由 **Kea2**（`hdc` + 截图判定）发现。暴露此缺陷无需 WebView 内功能深链；**冷启动 + 截图** 即足够。

请在贵方设备上重跑 15× 强制停止/启动循环；若问题普遍，10s 时约 30–50% 白屏率应易于确认。
