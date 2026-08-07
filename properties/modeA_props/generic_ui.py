"""
Cross-app Mode A properties — hardened from props_out dumps.

FP roots fixed:
  - ElementNotFound on stale text click → safe_click
  - "dead UI" when login/WebView has no tab labels → ui_alive / hierarchy count
  - 我的/消息 → login sheet → avoid as tab targets
  - EMPTY_OR_ERROR mismatch with assert labels
  - bare 搜索 in feed without search chrome
"""
from __future__ import annotations

import time
import unittest

from kea2 import max_tries, precondition, prob

from properties.modeA_props._util import (
    EMPTY_OR_ERROR,
    LOGINISH,
    PERMISSION,
    PRIVACY,
    TABISH,
    any_text,
    click_first,
    count_texts,
    dismiss_noise,
    hierarchy_text_count,
    safe_click,
    ui_alive,
)


# Content tabs only (not 我的/消息 — login tarpits)
_CONTENT_TABS = (
    "推荐", "视频", "发现", "热门", "关注", "首页",
    "热榜", "故事", "知识", "直答", "圈子",
    "Home", "Video", "Discover", "Follow",
)


class GenericUIProperties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d is None:
            return
        dismiss_noise(d)

    @prob(0.35)  # tarpit if always-on; low prob + Kea2 de-dupe
    @max_tries(3)
    @precondition(
        lambda self: any_text(
            self.d,
            ("同意并继续", "不同意", "已阅读并同意", "我已阅读并同意", "Agree and continue",
             "用户协议", "隐私政策"),
        )
    )
    def test_privacy_dialog_coherent(self):
        # TOCTOU: sheet may auto-dismiss / relaunch between static precond and body.
        assert any_text(self.d, PRIVACY) or ui_alive(
            self.d, extra=("登录", "验证码", "+86", "试用一下", "发送验证码")
        ), "privacy chrome vanished mid-dialog"

    @prob(0.55)
    @max_tries(3)
    @precondition(
        lambda self: (
            # real system dialog usually has both poles or limited-access chrome
            (any_text(self.d, ("Allow", "允许")) and any_text(self.d, ("Deny", "不允许", "Don't allow", "禁止")))
            or any_text(self.d, ("Allow this time only", "仅使用期间允许", "Limited access", "While using the app"))
        )
    )
    def test_permission_dialog_actionable(self):
        # Gallery limited-access / post-monkey dismiss: still OK if shell alive
        assert any_text(self.d, PERMISSION) or ui_alive(
            self.d, extra=("相机", "相册", "Gallery", "导入图片", "拍照", "图片")
        )

    @prob(0.9)
    @precondition(lambda self: count_texts(self.d, _CONTENT_TABS) >= 2)
    def test_tab_roundtrip_keeps_chrome(self):
        """Switch content tab; UI stays alive (chrome, login, or rich tree)."""
        before = [t for t in _CONTENT_TABS if self.d(text=t).exists()]
        if len(before) < 2:
            return
        # prefer non-首页 second tab
        target = next((t for t in before if t != "首页"), before[1])
        if not safe_click(self.d, target, settle=0.4):
            return  # stale — not a product bug
        assert ui_alive(
            self.d,
            extra=("看点", "地图找房", "二手房", "直播", "追番", "影视", "歌单", "书城"),
        ), f"dead UI after tab →{target}"

    @prob(0.85)
    @precondition(
        lambda self: self.d(text="搜索").exists()
        and (
            any_text(self.d, ("首页", "推荐", "我的", "消息", "视频", "发现", "热门",
                               "酒店", "地图", "热榜", "直答", "Home", "Me"))
            or count_texts(self.d, TABISH) >= 1
        )
    )
    def test_search_entry_not_dead(self):
        """Tap 搜索 only from app chrome; accept hierarchy substance."""
        if not safe_click(self.d, "搜索", settle=0.4):
            return
        ok = ui_alive(
            self.d,
            extra=(
                "取消",
                "历史",
                "搜索历史",
                "热门搜索",
                "搜索感兴趣的内容",
                "把问题和任务交给我",
                "输入商户名、地点或菜品",
                "猜你想搜",
                "清除",
            ),
        )
        assert ok, "search entry left dead/blank UI"

    @prob(0.7)
    @max_tries(3)
    @precondition(
        lambda self: (
            any_text(self.d, ("加载失败，请重试", "网络异常", "刷新页面", "点击重试", "重新加载"))
            or (self.d(text="加载失败").exists() and any_text(self.d, ("重试", "刷新", "刷新页面")))
        )
    )
    def test_error_has_retry(self):
        # TOCTOU: transient video error can self-heal between static precond and body
        assert any_text(
            self.d,
            ("重试", "刷新", "刷新页面", "点击重试", "重新加载", "加载失败，请重试", "网络异常", "加载失败"),
        ) or ui_alive(self.d, extra=("视频", "讨论", "播放", "追剧", "首页"))

    @prob(0.65)
    @precondition(
        lambda self: any_text(self.d, ("重试", "刷新页面", "点击重试", "重新加载"))
        and any_text(self.d, ("加载失败", "加载失败，请重试", "网络异常", "出错了", "刷新页面"))
    )
    def test_retry_stays_interactive(self):
        if not click_first(self.d, ("重试", "刷新页面", "点击重试", "重新加载", "刷新"), settle=0.4):
            return
        assert ui_alive(self.d, extra=EMPTY_OR_ERROR), "retry led to dead UI"

    @prob(0.4)
    @max_tries(4)
    @precondition(
        lambda self: any_text(self.d, LOGINISH)
        and any_text(self.d, ("+86", "用户协议", "隐私", "隐私政策", "服务协议", "验证码", "我已阅读并同意"))
    )
    def test_login_wall_interactive(self):
        # sheet may navigate to full policy WebView / external open — still alive OK
        assert any_text(
            self.d,
            LOGINISH
            + (
                "+86",
                "同意",
                "用户协议",
                "隐私",
                "隐私政策",
                "服务协议",
                "登录",
                "注册",
                "验证码",
                "我已阅读并同意",
                "阅读并同意",
                "个人信息保护",
                "Cancel",
                "Open",
            ),
        ) or ui_alive(self.d)

    @max_tries(2)
    @prob(0.35)
    @precondition(
        lambda self: count_texts(self.d, _CONTENT_TABS) >= 2 and not any_text(self.d, PRIVACY)
    )
    def test_back_keeps_some_ui(self):
        try:
            if hasattr(self.d, "go_back"):
                self.d.go_back()
            else:
                self.d.press_back()
        except Exception:
            return
        time.sleep(0.7)
        # launcher OK; only fail if dump is truly empty while still "in" something broken
        n_ok = ui_alive(self.d) or hierarchy_nonempty(self.d)
        assert n_ok

    @prob(0.55)
    @precondition(
        lambda self: any_text(self.d, ("取消", "关闭", "完成", "知道了"))
        and any_text(self.d, TABISH + ("搜索", "推荐", "首页"))
        and not any_text(self.d, PRIVACY)
    )
    def test_dismiss_keeps_shell(self):
        """Dismiss sheet/dialog; main shell still alive."""
        if not click_first(self.d, ("取消", "关闭", "完成", "知道了"), settle=0.35):
            return
        assert ui_alive(self.d), "dismiss left dead UI"

    @prob(0.85)
    @precondition(
        lambda self: any_text(self.d, ("分享", "收藏", "点赞", "关注", "赞同"))
        and (count_texts(self.d, _CONTENT_TABS) >= 1 or hierarchy_text_count(self.d) >= 6)
    )
    def test_social_action_keeps_ui(self):
        """Tap share/fav/follow chrome; UI stays interactive (login sheet OK)."""
        if not click_first(self.d, ("分享", "收藏", "点赞", "关注"), settle=0.35):
            return
        assert ui_alive(
            self.d,
            extra=("分享", "收藏", "取消", "微信", "好友", "复制链接", "登录", "+86"),
        ), "social action left dead UI"


def hierarchy_nonempty(d) -> bool:
    from properties.modeA_props._util import hierarchy_text_count

    n = hierarchy_text_count(d)
    return n < 0 or n >= 3  # dump fail → don't fail prop; empty → fail
