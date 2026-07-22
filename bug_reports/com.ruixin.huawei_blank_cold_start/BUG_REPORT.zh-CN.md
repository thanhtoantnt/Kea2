# 缺陷报告：冷启动间歇性白屏

| 字段 | 值 |
|---|---|
| **产品** | 瑞新 / 真空e家 |
| **包名** | `com.ruixin.huawei` |
| **平台** | HarmonyOS NEXT |
| **设备（实验室）** | 序列号 `5SM0125606000291` |
| **严重程度** | **高** — 应用不可用，直至强制停止 |
| **组件** | 混合 Web / 不透明 WebView（`EntryAbility`） |
| **状态** | 实验室已确认可复现 |
| **报告日期** | 2026-07-21 |
| **发现方式** | Kea2 / `pi-pbt kea` cold-start-probe（不透明路径） |

---

## 摘要

**冷启动**（`aa force-stop` 后 `aa start`）后，进程已进入 **FOREGROUND**，但 UI 经常在 ≥10s 内保持**整屏全白**（无首页框架、无启动恢复 UI）。

**实验室复现率：5/8（62.5%）**，等待 10s（`white_frac ≈ 0.985`）。

当缺陷**未**发生时，同一构建绘制底部标签（`真空e家` / `供应` / `消息` / `我的`）与首页内容。

---

## 影响

- 用户打开应用 → 死白屏。
- 应用内无恢复；强制停止 + 重启可能再次白屏。
- 间歇性 → 无多轮测试时易被当作“手机慢”而忽略。

---

## 复现步骤（自动化）

```bash
cd bug_reports/com.ruixin.huawei_blank_cold_start
bash repro_blank_cold_start.sh 10 10
# needs: hdc, python3, pillow, numpy
```

手动：

1. 安装 `com.ruixin.huawei`。
2. 强制停止 → 从启动器启动（或 `aa start -a EntryAbility -b com.ruixin.huawei`）。
3. 等待 10s，勿触摸。
4. 观察白屏 vs 已绘制首页。
5. 重复 ≥8 次。

### 预期
数秒内 UI 完成绘制（或加载/错误框架）。

### 实际
约 **62%** 冷启动：内容纯白，进程仍为 FOREGROUND。

---

## 证据（实验室）

| trial | white_frac | blank |
|------:|-----------:|:-----:|
| 0 | 0.255 | ok |
| 1 | 0.985 | **BLANK** |
| 2 | 0.985 | **BLANK** |
| 3 | 0.255 | ok |
| 4 | 0.985 | **BLANK** |
| 5 | 0.262 | ok |
| 6 | 0.985 | **BLANK** |
| 7 | 0.985 | **BLANK** |

截图：`evidence/trial_XX.png`  
机器 JSON：`COLD_START.json`

---

## 相关活动备注

- 已绘制界面上游客 **标签导航** 正常（手动 Kea2 A：ran_ok e=14；touch-probe：无死标签）。
- 白屏启动独立于标签判定 — 不透明 WebView 应用须用冷启动多轮探测。
- 同类模式：`com.csai.tongxin` 冷启动白屏（约 47%）。

---

## 环境

- Kea2 Harmony 路径 + `pbt-agent` `cold-start-probe.sh`
- 设备已解锁，USB `hdc`


## 复测
第二次实验室运行：**5/10（50%）** 白屏 @10s（同设备/构建）。确认间歇性，非单次抖动。
