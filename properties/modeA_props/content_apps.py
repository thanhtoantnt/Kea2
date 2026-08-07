"""Reading / travel / local / create / study — package gates + safe_click."""
from __future__ import annotations

import unittest

from kea2 import precondition, prob

from properties.modeA_props._util import (
    any_text,
    dismiss_noise,
    on_package,
    safe_click,
    ui_alive,
)


class ContentAppProps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = getattr(cls, "d", None)
        if d:
            dismiss_noise(d)

    @prob(0.75)
    @precondition(
        lambda self: on_package(self.d, "com.qimao.novel")
        or any_text(self.d, ("阅读赚金币", "不知道看什么小说  就上七猫必读榜"))
    )
    def test_qimao_shelf_chrome(self):
        assert ui_alive(self.d, extra=("阅读赚金币", "书城", "书架", "菜单"))

    @prob(0.8)
    @precondition(
        lambda self: on_package(self.d, "com.lemon.hm.lv")
        or (
            any_text(self.d, ("开始创作", "本地草稿"))
            and any_text(self.d, ("剪辑", "模板", "脚本"))
        )
    )
    def test_capcut_tools(self):
        if not any(
            safe_click(self.d, t)
            for t in ("模板", "剪辑", "脚本", "开始创作")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("剪辑", "模板", "脚本", "本地草稿", "热门工具", "回收站"))

    @prob(0.8)
    @precondition(
        lambda self: on_package(self.d, "cn.mucang.hm.jiakao")
        or (
            any_text(self.d, ("网约车", "资格证", "无人机"))
            and any_text(self.d, ("出租车", "货运", "客运"))
        )
    )
    def test_jiakao_category(self):
        if not any(
            safe_click(self.d, t)
            for t in ("网约车", "出租车", "货运", "资格证")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("网约车", "出租车", "货运", "资格证", "全称：", "教练员"))

    @prob(0.75)
    @precondition(
        lambda self: on_package(self.d, "com.ctrip.harmonynext")
        or (
            any_text(self.d, ("特价", "线路", "榜单"))
            and any_text(self.d, ("酒店", "机票", "火车票", "攻略/景点"))
        )
    )
    def test_ctrip_explore_tabs(self):
        if not any(
            safe_click(self.d, t) for t in ("榜单", "线路", "热点", "特价") if self.d(text=t).exists()
        ):
            # home hotel chrome alone is enough
            assert ui_alive(self.d, extra=("酒店", "机票", "火车票", "榜单"))
            return
        assert ui_alive(self.d, extra=("特价", "线路", "热点", "榜单", "酒店", "机票"))

    @prob(0.75)
    @precondition(
        lambda self: on_package(self.d, "com.sankuai.dianping")
        or (
            any_text(self.d, ("周末去哪", "离我最近的美食"))
            or (self.d(text="附近").exists() and self.d(text="热点").exists())
        )
    )
    def test_dianping_feed_tabs(self):
        if not any(
            safe_click(self.d, t)
            for t in ("热点", "附近", "旅行", "周末去哪")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("附近", "热点", "旅行", "周末去哪", "好吃", "好玩"))

    @prob(0.8)
    @precondition(
        lambda self: on_package(self.d, "com.zhihu.hmos")
        or (self.d(text="热榜").exists() and self.d(text="推荐").exists() and self.d(text="关注").exists())
    )
    def test_zhihu_tabs(self):
        if not any(
            safe_click(self.d, t)
            for t in ("热榜", "关注", "故事", "知识", "推荐")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(self.d, extra=("热榜", "关注", "故事", "知识", "推荐"))

    @prob(0.7)
    @precondition(
        lambda self: on_package(self.d, "com.meitu.meitupic")
        or any_text(self.d, ("Camera", "Edit Video", "Enhancer", "Flawless Text"))
    )
    def test_meitu_tools(self):
        if not any(
            safe_click(self.d, t)
            for t in ("拼图", "证件照", "Camera", "Enhancer", "Edit Video")
            if self.d(text=t).exists()
        ):
            return
        assert ui_alive(
            self.d,
            extra=("Camera", "拼图", "Edit Video", "Enhancer", "证件照", "相册", "取消", "Allow", "允许"),
        )

    @prob(0.7)
    @precondition(
        lambda self: any_text(self.d, ("欢迎来到闲鱼", "手机淘宝登录"))
        and any_text(self.d, ("其他登录方式", "用户服务协议", "隐私权政策", "我已阅读并同意", "软件许可"))
    )
    def test_xianyu_login_coherent(self):
        # legal line is ONE node: 您已阅读并同意《闲鱼社区用户服务协议》《隐私权政策》…
        assert any_text(
            self.d,
            (
                "欢迎来到闲鱼",
                "手机淘宝登录",
                "其他登录方式",
                "获取验证码",
                "+86",
                "登录",
                "闲鱼社区用户服务协议",
                "隐私权政策",
                "软件许可使用协议",
                "您已阅读并同意",
            ),
        ) or ui_alive(self.d)
