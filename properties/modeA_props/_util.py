"""Shared helpers for Mode A property packs — hardened from dump FPs."""
from __future__ import annotations

import time
from typing import Iterable, Sequence


def _exists(d, text: str) -> bool:
    try:
        return bool(d(text=text).exists(timeout=0))
    except TypeError:
        try:
            return bool(d(text=text).exists())
        except Exception:
            return False
    except Exception:
        return False


def _exists_contains(d, fragment: str) -> bool:
    """Match combined legal strings e.g. 您已阅读并同意《…隐私权政策…》."""
    try:
        return bool(d(textContains=fragment).exists(timeout=0))
    except TypeError:
        try:
            return bool(d(textContains=fragment).exists())
        except Exception:
            return False
    except Exception:
        return False


def any_text(d, labels: Iterable[str], contains: bool = True) -> bool:
    for t in labels:
        if _exists(d, t):
            return True
        if contains and len(t) >= 2 and _exists_contains(d, t):
            return True
    return False


def count_texts(d, labels: Sequence[str]) -> int:
    return sum(1 for t in labels if _exists(d, t))


def safe_click(d, text: str, settle: float = 0.35) -> bool:  # B8
    """Re-check then click; swallow ElementNotFound (stale hierarchy).

    Falls back to bounds center tap when node is text-only (clickable=false),
    common on 红果/Douyin tab labels.
    """
    if not _exists(d, text):
        return False
    try:
        d(text=text).click()
        time.sleep(settle)
        return True
    except Exception:
        pass
    # bounds fallback
    try:
        for a in iter_node_attrs(d):
            if (a.get("text") or "").strip() != text:
                continue
            b = _parse_bounds(a.get("bounds"))
            if not b:
                continue
            x, y = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
            d.click(x, y)
            time.sleep(settle)
            return True
    except Exception:
        return False
    return False


def click_first(d, labels: Iterable[str], settle: float = 0.35) -> str | None:
    for t in labels:
        if safe_click(d, t, settle=settle):
            return t
    return None


def fg_package(d) -> str | None:
    try:
        cur = d.app_current() or {}
        return cur.get("package")
    except Exception:
        return None


def on_package(d, *pkgs: str) -> bool:
    p = fg_package(d)
    return bool(p and p in pkgs)


def hierarchy_text_count(d, limit_walk: int = 400) -> int:
    """Count non-trivial text nodes — blank WebView / dead page ≈ 0–2."""
    try:
        h = d.dump_hierarchy()
    except Exception:
        return -1
    n = 0
    stack = [h] if isinstance(h, dict) else list(h or [])
    while stack and n < limit_walk:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        a = node.get("attributes") or node
        if isinstance(a, dict):
            t = (a.get("text") or a.get("Text") or "").strip()
            if t and len(t) > 1 and t not in {":", ",", "%", "100"}:
                n += 1
        for c in node.get("children") or []:
            stack.append(c)
    return n


def ui_alive(d, extra: Iterable[str] = ()) -> bool:
    """UI still has substance: known chrome OR enough text nodes."""
    chrome = (
        TABISH
        + PRIVACY
        + PERMISSION
        + LOGINISH
        + EMPTY_OR_ERROR
        + (
            "搜索",
            "取消",
            "设置",
            "关闭",
            "完成",
            "返回",
            "确定",
            "提交",
            "帮助",
            "分享",
            "收藏",
            "首页",
            "我的",
            "会员",
            "地图",
            "酒店",
            "机票",
            "二手房",
            "新房",
            "租房",
            "关注",
            "推荐",
            "热门",
            "直播",
            "视频",
            "消息",
            "购物车",
            "书城",
            "书架",
            "剪辑",
            "模板",
            "Camera",
            "登录",
            "注册",
            "+86",
        )
        + tuple(extra)
    )
    if any_text(d, chrome):
        return True
    n = hierarchy_text_count(d)
    return n >= 5  # ponytail: threshold; raise if blank pages slip through


def dismiss_noise(d) -> None:
    """Soft-dismiss system noise; leave privacy for properties."""
    # careful labels only — bare 取消/同意/关闭 thrash real UI (V3 regression)
    labels = (
        "Allow this time only",
        "Allow all the time",
        "Allow",
        "仅使用期间允许",
        "使用时允许",
        "我知道了",
        "知道了",
        "跳过",
        "下次再说",
        "稍后再说",
        "暂不认证",
        "以后再说",
        "暂不切换",
        "仍然关闭",
        "随便看看",
        "暂不登录",
        "游客进入",
        "跳过登录",
        "先逛逛",
        "先看看",
        "立即体验",
        "同意并继续",
    )
    for _ in range(2):
        hit = False
        for t in labels:
            if safe_click(d, t, settle=0.12):
                hit = True
                break  # one dismiss per pass
        if not hit:
            break


# Labels used across many CN apps
TABISH = (
    "首页",
    "推荐",
    "我的",
    "消息",
    "视频",
    "发现",
    "关注",
    "热门",
    "搜索",
    "直答",
    "热榜",
    "故事",
    "知识",
    "圈子",
    "社区",
    "行程",
    "购物车",
    "美团",
    "Home",
    "Me",
    "Video",
    "Discover",
    "Message",
    "Follow",
)
PRIVACY = (
    "同意并继续",
    "不同意",
    "Agree and continue",
    "已阅读并同意",
    "我已阅读并同意",
    "阅读并同意",
    "用户协议",
    "隐私政策",
    "隐私权政策",
    # bare "同意" / "Agree" too short — FPs on 已阅读并同意 checkbox lines + TOCTOU
)
PERMISSION = (
    "Allow",
    "Deny",
    "允许",
    "不允许",
    "仅使用期间允许",
    "使用时允许",
    "Allow this time only",
    "Allow all the time",
    "Limited access",
    "While using the app",
    "Only this time",
    "Don't allow",
    "禁止",
    "始终允许",
    "Manage",
    "Change",
)
EMPTY_OR_ERROR = (
    "加载失败，请重试",
    "网络异常",
    "刷新页面",
    "点击重试",
    "重新加载",
    "出错了",
)
# bare "加载失败"/"重试" alone too common in feed copy — pair in preconditions
LOGINISH = (
    "密码登录",
    "手机号登录",
    "一键登录",
    "微信登录",
    "Agree and Log In",
    "Log in via phone number",
    "获取验证码",
    "获取短信验证码",
    "账号密码登录",
    "欢迎来到闲鱼",
    "欢迎登录",
    "未注册手机号",
    "验证后自动创建",
)


# --- hierarchy / geometry (for 20 bug-class oracles) ---

def _parse_bounds(raw):
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        return [int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])]
    import re
    nums = re.findall(r"-?\d+", str(raw))
    if len(nums) >= 4:
        return [int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])]
    return None


def iter_node_attrs(d, limit: int = 800) -> list:
    """Flat list of attribute dicts from current hierarchy dump."""
    try:
        h = d.dump_hierarchy()
    except Exception:
        return []
    out = []
    stack = [h] if isinstance(h, dict) else list(h or [])
    while stack and len(out) < limit:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        a = node.get("attributes") or node
        if isinstance(a, dict) and ("bounds" in a or "text" in a or "type" in a):
            out.append(a)
        for c in node.get("children") or []:
            stack.append(c)
    return out


def screen_size(d) -> tuple:
    """(w,h) from root bounds; fallback Douyin-ish tablet."""
    for a in iter_node_attrs(d, limit=5):
        b = _parse_bounds(a.get("bounds"))
        if b and b[2] - b[0] >= 400 and b[3] - b[1] >= 800:
            return (b[2] - b[0], b[3] - b[1])
    return (1280, 2832)


def hierarchy_fingerprint(d) -> str:
    """Cheap content fingerprint for change / freeze detection."""
    parts = []
    for a in iter_node_attrs(d, limit=300):
        t = (a.get("text") or "").strip()
        if not t or t.startswith("file://") or len(t) > 40:
            t = ""
        b = a.get("bounds") or ""
        parts.append(f"{t}|{b}|{a.get('type')}|{a.get('focused')}")
    return str(hash(tuple(parts)))


def visible_text_nodes(d, min_len: int = 1) -> list:
    """(text, bounds, attrs) for on-screen text-ish nodes."""
    w, h = screen_size(d)
    out = []
    for a in iter_node_attrs(d):
        t = (a.get("text") or "").strip()
        if not t or len(t) < min_len or t.startswith("file://"):
            continue
        b = _parse_bounds(a.get("bounds"))
        if not b:
            continue
        # skip pure status-bar clock crumbs
        if t in {":", ",", "%"} or (t.isdigit() and len(t) <= 2):
            continue
        cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        if 0 <= cx <= w and 0 <= cy <= h:
            out.append((t, b, a))
    return out


def clickable_nodes(d) -> list:
    out = []
    for a in iter_node_attrs(d):
        if str(a.get("clickable") or "").lower() != "true":
            continue
        if str(a.get("enabled") or "true").lower() == "false":
            continue
        b = _parse_bounds(a.get("bounds"))
        if not b:
            continue
        area = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        if area < 400 or area > 2_000_000:
            continue
        out.append((b, a))
    return out


def _overlap_area(b1, b2) -> int:
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    if x2 <= x1 or y2 <= y1:
        return 0
    return (x2 - x1) * (y2 - y1)


def count_bad_overlaps(d, min_ratio: float = 0.55) -> int:
    """Clickable peers heavily overlapping (not parent/child same center)."""
    nodes = clickable_nodes(d)
    # ponytail: O(n^2) ok for n<=80
    nodes = nodes[:80]
    bad = 0
    for i in range(len(nodes)):
        b1, a1 = nodes[i]
        a1_area = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
        t1 = (a1.get("text") or "")[:20]
        for j in range(i + 1, len(nodes)):
            b2, a2 = nodes[j]
            a2_area = max(1, (b2[2] - b2[0]) * (b2[3] - b2[1]))
            ov = _overlap_area(b1, b2)
            if ov <= 0:
                continue
            # same label stack tabs often share — skip identical text
            t2 = (a2.get("text") or "")[:20]
            if t1 and t1 == t2:
                continue
            r = ov / min(a1_area, a2_area)
            if r >= min_ratio and abs(a1_area - a2_area) / max(a1_area, a2_area) < 0.5:
                bad += 1
    return bad


def count_clipped_text(d) -> int:
    """Text nodes whose bounds spill past screen (截断/显示不全 proxy)."""
    w, h = screen_size(d)
    n = 0
    for t, b, a in visible_text_nodes(d, min_len=2):
        # ignore tiny overflow (shadow/aa)
        if b[0] < -20 or b[1] < -20 or b[2] > w + 20 or b[3] > h + 20:
            if len(t) >= 2:
                n += 1
        # zero-height / zero-width text with content
        elif (b[2] - b[0]) < 2 or (b[3] - b[1]) < 2:
            n += 1
    return n


def count_offscreen_clickables(d) -> int:
    w, h = screen_size(d)
    n = 0
    for b, a in clickable_nodes(d):
        cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
        if cx < 0 or cy < 0 or cx > w or cy > h:
            n += 1
    return n


def focused_input(d) -> bool:
    for a in iter_node_attrs(d):
        typ = str(a.get("type") or "")
        if str(a.get("focused") or "").lower() == "true":
            if "Input" in typ or "Edit" in typ or "Field" in typ or "Search" in typ:
                return True
            # some OHOS text fields
            if typ in ("TextInput", "TextArea", "SearchField", "RichEditor"):
                return True
    return False


def has_input_field(d) -> bool:
    for a in iter_node_attrs(d):
        typ = str(a.get("type") or "")
        if any(k in typ for k in ("TextInput", "TextArea", "SearchField", "Edit", "RichEditor")):
            return True
        if str(a.get("focused") or "").lower() == "true" and "Text" in typ:
            return True
    return any_text(d, ("搜索", "说点什么", "请输入", "Search", "输入"))


def primary_cta_disabled(d) -> bool:
    """Visible primary action labels that are enabled=false (控件状态)."""
    labels = ("发布", "发送", "完成", "下一步", "提交", "确认", "登录", "关注")
    for a in iter_node_attrs(d):
        t = (a.get("text") or "").strip()
        if t not in labels:
            continue
        if str(a.get("enabled") or "true").lower() == "false":
            # disabled 发布 with empty draft is normal — only flag if also clickable tree weird
            # ponytail: report soft — caller decides
            return True
    return False


def click_xy(d, x: int, y: int, settle: float = 0.3) -> bool:
    try:
        d.click(int(x), int(y))
        time.sleep(settle)
        return True
    except Exception:
        return False


def all_texts(d, limit: int = 400) -> list:
    """All non-trivial texts in current dump (for query⊂results checks)."""
    out = []
    for a in iter_node_attrs(d, limit=limit):
        t = (a.get("text") or "").strip()
        if t and len(t) > 1 and not t.startswith("file://"):
            out.append(t)
    return out


def texts_blob(d, limit: int = 400) -> str:
    return " ".join(all_texts(d, limit=limit))


def type_into_search(d, query: str, settle: float = 0.45) -> bool:
    """Open search if needed, focus field, type query. Returns True if typed."""
    # try focused / known search field types first
    try:
        if hasattr(d, "__call__"):
            for sel in (
                {"type": "TextInput"},
                {"type": "SearchField"},
                {"type": "TextArea"},
            ):
                try:
                    w = d(**sel)
                    if w.exists() if hasattr(w, "exists") else True:
                        try:
                            w.click()
                        except Exception:
                            pass
                        w.set_text(query)
                        time.sleep(settle)
                        return True
                except Exception:
                    continue
            # placeholder text click then set_text on TextInput
            for ph in ("搜索", "Search", "搜一搜", "请输入", "搜索感兴趣的内容"):
                if _exists(d, ph):
                    try:
                        d(text=ph).click()
                        time.sleep(0.4)
                    except Exception:
                        pass
                    try:
                        d(type="TextInput").set_text(query)
                        time.sleep(settle)
                        return True
                    except Exception:
                        try:
                            d(text=ph).set_text(query)
                            time.sleep(settle)
                            return True
                        except Exception:
                            pass
    except Exception:
        return False
    return False


def query_reflected(d, query: str) -> bool:
    """Query string (or first 2+ chars) appears in hierarchy after search."""
    if not query:
        return False
    blob = texts_blob(d)
    if query in blob:
        return True
    # Chinese/EN token: first 2 chars often enough
    if len(query) >= 2 and query[:2] in blob:
        return True
    return False
