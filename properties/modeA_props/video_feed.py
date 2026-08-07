"""Video / audio apps — package-scoped where cross-fire hurt dumps."""
from __future__ import annotations

import time
import unittest

from kea2 import precondition, prob

from properties.modeA_props._util import (
    any_text,
    dismiss_noise,
    on_package,
    safe_click,
    ui_alive,
)


class VideoFeedProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.8)
    @precondition(
        lambda self: on_package(self.d, "yylx.danmaku.bili")
        or (
            any_text(self.d, ("追番", "影视"))
            and any_text(self.d, ("推荐", "热门", "直播"))
        )
    )
    def test_bili_channel_switch(self):
        target = None
        for t in ("热门", "直播", "追番", "影视", "推荐"):
            if self.d(text=t).exists():
                target = t
                break
        if not target or not safe_click(self.d, target):
            return
        assert ui_alive(self.d, extra=("追番", "影视", "直播", "动态", "登录"))

    @prob(0.75)
    @precondition(
        lambda self: on_package(self.d, "com.qiyi.video.hmy")
        or (
            self.d(text="视频").exists()
            and self.d(text="讨论").exists()
            and any_text(self.d, ("简介", "播放", "选集", "详情", "免费看", "更新至"))
        )
    )
    def test_iqiyi_detail_tabs(self):
        if not safe_click(self.d, "讨论"):
            return
        assert ui_alive(self.d, extra=("视频", "讨论", "简介", "详情", "播放", "刷新页面"))

    @prob(0.8)
    @precondition(
        lambda self: any_text(self.d, ("加载失败，请重试", "网络异常"))
        or (
            any_text(self.d, ("加载失败", "出错了"))
            and any_text(self.d, ("重试", "刷新页面", "刷新", "点击重试"))
        )
    )
    def test_video_error_retry_visible(self):
        # re-dump; require recovery affordance OR still-error chrome (not blank)
        ok = any_text(
            self.d,
            ("刷新页面", "重试", "加载失败，请重试", "刷新", "加载失败", "网络异常", "点击重试"),
        ) or ui_alive(self.d)
        assert ok, "video error chrome lost"

    @prob(0.7)
    @precondition(
        lambda self: on_package(self.d, "com.kugou.hmmusic")
        or (
            self.d(text="猜你喜欢").exists()
            and any_text(self.d, ("听书", "AI唱", "每日推荐", "听歌识曲"))
        )
    )
    def test_kugou_home_modules(self):
        if not any(
            safe_click(self.d, t)
            for t in ("歌单", "排行榜", "听书", "免费听", "每日推荐")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("歌单", "排行榜", "听书", "猜你喜欢", "免费听"))

    @prob(0.7)
    @precondition(
        lambda self: on_package(self.d, "com.ximalaya.ting.xmharmony")
        or (
            self.d(text="相声评书").exists()
            or (self.d(text="宝宝巴士").exists() and self.d(text="小说").exists())
        )
    )
    def test_ximalaya_channel(self):
        if not any(
            safe_click(self.d, t)
            for t in ("小说", "儿童", "相声评书", "推荐")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("相声评书", "宝宝巴士", "小说", "儿童"))

    @prob(0.65)
    @precondition(
        lambda self: on_package(self.d, "com.youku.next")
        or any_text(self.d, ("热搜榜", "上新榜", "热度榜", "今日给您的专属推荐"))
    )
    def test_youku_rank_chrome(self):
        assert ui_alive(self.d, extra=("热搜榜", "上新榜", "热度榜", "会员"))

    @prob(0.65)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme.jingxuan", "com.ss.hm.ugc.aweme")
        or any_text(self.d, ("全屏观看", "相关推荐", "稍后再看"))
    )
    def test_shortvideo_player_chrome(self):
        assert ui_alive(self.d, extra=("全屏观看", "相关推荐", "稍后再看", "作者声明"))

    # --- Douyin logged-in (com.ss.hm.ugc.aweme) ---
    _DY = ("com.ss.hm.ugc.aweme",)
    _DY_TABS = ("首页", "朋友", "消息", "我", "推荐", "关注", "精选", "直播")

    @prob(0.85)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("首页", "推荐", "关注", "朋友", "消息", "我"))
    )
    def test_douyin_home_chrome(self):
        """Logged-in shell: bottom/top chrome present."""
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("全屏观看", "搜索", "@"),
        ), "douyin home chrome missing"

    @prob(0.75)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("推荐", "关注", "精选", "直播", "朋友"))
    )
    def test_douyin_feed_tab_switch(self):
        """Switch feed tab; stay in-app."""
        target = None
        for t in ("关注", "精选", "直播", "朋友", "推荐", "首页"):
            if self.d(text=t).exists():
                target = t
                break
        if not target or not safe_click(self.d, target, settle=0.4):
            return
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("全屏观看", "登录", "搜索"),
        ), "douyin tab switch dead UI"

    @prob(0.7)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("全屏观看", "作者声明"))
    )
    def test_douyin_player_keeps_feed(self):
        """Player chrome on feed; UI stays interactive."""
        assert ui_alive(
            self.d,
            extra=("全屏观看", "作者声明", "推荐", "首页", "关注", "相关推荐"),
        )

    @prob(0.6)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("消息", "我", "朋友"))
        and any_text(self.d, ("首页", "推荐"))
    )
    def test_douyin_me_or_msg_roundtrip(self):
        """Open 消息/我 then return via 首页 — logged-in profile path."""
        dest = None
        for t in ("我", "消息", "朋友"):
            if self.d(text=t).exists():
                dest = t
                break
        if not dest or not safe_click(self.d, dest, settle=0.4):
            return
        # profile/inbox should not blank
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("编辑主页", "抖音号", "关注", "粉丝", "获赞", "设置", "登录"),
        ), "douyin me/msg blank"
        if self.d(text="首页").exists():
            safe_click(self.d, "首页", settle=0.4)
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("全屏观看", "推荐"),
        ), "douyin failed return home"

    @prob(0.7)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("综合", "用户", "图文"))
        and any_text(self.d, ("搜索", "视频", "直播", "商品"))
    )
    def test_douyin_search_results_chrome(self):
        """Search results tabs stay interactive."""
        assert ui_alive(
            self.d,
            extra=("搜索", "综合", "视频", "用户", "图文", "商品", "直播", "音乐"),
        )
        # flip a results facet if present
        for t in ("视频", "用户", "直播", "综合"):
            if self.d(text=t).exists() and safe_click(self.d, t, settle=0.35):
                break
        assert ui_alive(
            self.d,
            extra=("搜索", "综合", "视频", "用户", "直播", "取消"),
        ), "douyin search facet dead"

    @prob(0.65)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("推荐", "首页", "全屏观看"))
        and not any_text(self.d, ("综合", "图文", "选择音乐"))  # not search/camera
    )
    def test_douyin_feed_swipe_keeps_ui(self):
        """Vertical swipe on feed; still Douyin shell."""
        try:
            # mid-screen up swipe (next video)
            self.d.swipe(540, 1600, 540, 500, speed=500)
            time.sleep(0.4)
        except Exception:
            return
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("全屏观看", "@", "搜索", "评论"),
        ), "douyin swipe left dead feed"

    @prob(0.6)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("评论", "说点什么", "条评论", "暂无评论"))
    )
    def test_douyin_comment_sheet_alive(self):
        """Comment panel/chrome usable when open."""
        assert ui_alive(
            self.d,
            extra=("评论", "说点什么", "发送", "回复", "作者", "关闭", "取消", "首页"),
        ), "douyin comment sheet dead"

    @prob(0.55)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("获赞", "粉丝"))
        and any_text(self.d, ("关注", "编辑主页", "抖音号", "作品", "喜欢", "收藏"))
    )
    def test_douyin_profile_stats_chrome(self):
        """Own/other profile stats row present (logged-in)."""
        assert ui_alive(
            self.d,
            extra=("获赞", "粉丝", "关注", "作品", "喜欢", "收藏", "编辑主页", "首页"),
        )

    @prob(0.55)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and self.d(text="直播").exists()
        and any_text(self.d, ("首页", "推荐", "精选", "关注"))
    )
    def test_douyin_live_tab_keeps_shell(self):
        """Open 直播 tab; app shell survives."""
        if not safe_click(self.d, "直播", settle=0.4):
            return
        assert ui_alive(
            self.d,
            extra=self._DY_TABS + ("点击进入直播间", "直播", "推荐", "关注", "登录"),
        ), "douyin live tab dead"

    @prob(0.5)
    @precondition(
        lambda self: on_package(self.d, "com.ss.hm.ugc.aweme")
        and any_text(self.d, ("已关注", "回关", "私信", "主页"))
        and any_text(self.d, ("获赞", "粉丝", "关注", "作品"))
    )
    def test_douyin_author_profile_chrome(self):
        """Author profile opened from feed stays interactive."""
        assert ui_alive(
            self.d,
            extra=("获赞", "粉丝", "关注", "作品", "私信", "已关注", "回关", "首页"),
        )
