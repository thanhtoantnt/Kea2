# Bug Report: Guest home tiles hand off to WeChat / external login (leave app)

| Field | Value |
|---|---|
| **Product** | 通信工程师考试 |
| **Package** | `com.csai.tongxin` **v1.0.1** |
| **Severity** | Medium (UX / unexpected external jump) |
| **Platform** | HarmonyOS NEXT |

## Summary
From the **logged-out home** screen, several tiles (e.g. **去做题**, and previously **测试记录 / 错题本 / 试题收藏 / 电子资料**) jump the user out of the app into **WeChat** (`com.tencent.wechat`) phone-login UI, instead of an in-app login sheet or a clear “login required” state inside the exam app.

## Steps
1. Cold-start app; complete exam selection + privacy if shown; reach home **without** logging in.
2. Tap **去做题** (历年真题 card) — or **测试记录 / 错题本** (when those hit targets).
3. Observe foreground package / UI.

## Expected
- In-app login modal (希赛 SMS login was seen on other entries), **or**
- Disabled tile + message “请先登录”, **or**
- Guest-accessible content.

## Actual
- Process leaves `com.csai.tongxin` FOREGROUND.
- System/WeChat **“Log in via phone number” / Agree and Log In** UI appears.
- User must manually return; easy to perceive as crash or hijack.

## Evidence (lab)
- `aa dump` after tap: FOREGROUND `com.tencent.wechat`
- Screenshot oracle: content change + package switch on `uitest uiInput click 300 1200` (去做题 region)

## Notes
- Distinct from blank cold-start bug.
- May be intentional SSO — still a product bug if guest home advertises “去做题” as available.
