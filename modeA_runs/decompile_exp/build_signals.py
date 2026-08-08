#!/usr/bin/env python3
"""Build signals.json per pkg from mined_all/* text dumps. Offline, no phone."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "mined_all"

TAB_HINT = re.compile(
    r"^(首页|我的|消息|发现|推荐|视频|直播|关注|热门|热榜|行程|酒店|门票|火车票|"
    r"机票|美食|景点|购物车|订单|搜索|设置|市集|闲鱼|微博|知乎|美团|点评|地图|"
    r"附近|打车|导航|电影|演出|会员|钱包|客服|社区|问答|想法|同城|商城|分类|"
    r"领券|聊天|个人中心|Home|Me|Message|Search|Feed|Live|Map)$"
)
ERR_HINT = re.compile(
    r"(失败|异常|错误|网络|重试|超时|无法|不能|崩溃|crash|error|fail|timeout|"
    r"invalid|empty|无内容|暂无|加载失败|请检查)",
    re.I,
)
EMPTY_HINT = re.compile(r"(暂无|无记录|空空|没有[了啦]?|no\s*data|empty|什么都没有|尚未)", re.I)
SEARCH_HINT = re.compile(r"(搜索|搜一搜|search|查询|找一找)", re.I)
ACTION_HINT = re.compile(
    r"^(登录|注册|提交|确认|取消|删除|清除|重试|刷新|返回|关闭|完成|下一步|"
    r"立即|去看看|查看更多|加载更多|login|retry|cancel|ok|submit)$",
    re.I,
)
BAD = re.compile(r"[@&/;\\]|L&|pkg_modules|ohpm|beta\.|https?://|^\d+$|function |class ")
# strict: Ctrip CTImage module (avoid selectImage false positive via ctImage substring)
CT_RE = re.compile(
    r"(?:ctcommon/ctimage|@ctcommon/ctimage|/CTImage(?:Loader|Option|UrlTrans|Initializer|Covert)?\b|onImageOptionChange|CTImageLoader\.transUrl)",
    re.I,
)

FALLBACK = {
    "tabs": ["首页", "我的", "消息", "发现", "推荐", "视频"],
    "search": ["搜索", "Search", "搜一搜"],
    "errors": ["网络异常", "加载失败", "请重试", "出错了", "失败"],
    "empty": ["暂无", "无内容", "空空如也", "暂无数据"],
}


def clean_lines(path: Path, limit: int = 2000) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or BAD.search(s) or len(s) > 24:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def uniq(xs, n=40):
    seen, o = set(), []
    for x in xs:
        if x in seen:
            continue
        seen.add(x)
        o.append(x)
        if len(o) >= n:
            break
    return o


def build_one(pkg_dir: Path) -> dict:
    pkg = pkg_dir.name
    labels = clean_lines(pkg_dir / "labels_cjk.txt")
    hits = clean_lines(pkg_dir / "strings_hits.txt", 5000)
    methods = clean_lines(pkg_dir / "methods_like.txt", 3000)
    classes = clean_lines(pkg_dir / "classes_like.txt", 3000)
    ct_raw = clean_lines(pkg_dir / "ctimage_hits.txt", 500) if (pkg_dir / "ctimage_hits.txt").exists() else []

    tabs, errs, empty, search, actions, misc = [], [], [], [], [], []
    for s in labels + hits:
        if TAB_HINT.search(s):
            tabs.append(s)
        elif SEARCH_HINT.search(s):
            search.append(s)
        elif EMPTY_HINT.search(s):
            empty.append(s)
        elif ERR_HINT.search(s):
            errs.append(s)
        elif ACTION_HINT.search(s):
            actions.append(s)
        elif 2 <= len(s) <= 8 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]+", s):
            misc.append(s)

    pages = []
    for s in methods + classes:
        pages.extend(re.findall(r"pages/[A-Za-z0-9_]+", s))
        pages.extend(
            re.findall(r"([A-Z][A-Za-z0-9]{3,40}(?:Page|Ability|View|Component|Panel|Loader))", s)
        )

    ct_syms = [s[:120] for s in ct_raw if CT_RE.search(s)]
    # also scan methods/classes for true CTImage (not generic Image)
    for s in methods + classes + hits:
        if CT_RE.search(s):
            ct_syms.append(s[:120])

    return {
        "package": pkg,
        "tabs": uniq(tabs) or FALLBACK["tabs"][:],
        "search": uniq(search) or FALLBACK["search"][:],
        "errors": uniq(errs, 50) or FALLBACK["errors"][:],
        "empty": uniq(empty) or FALLBACK["empty"][:],
        "actions": uniq(actions, 30),
        "misc_labels": uniq(misc, 60),
        "pages_or_comps": uniq(pages, 40),
        "has_ctimage": any(CT_RE.search(s) for s in ct_syms),
        "ctimage_symbols": uniq(ct_syms, 30),
        "source": "mined_all",
    }


def main() -> int:
    if not ROOT.exists():
        print("missing", ROOT, file=sys.stderr)
        return 2
    n = 0
    for pkg_dir in sorted(ROOT.iterdir()):
        if not pkg_dir.is_dir():
            continue
        sig = build_one(pkg_dir)
        (pkg_dir / "signals.json").write_text(
            json.dumps(sig, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"{sig['package']}: tabs={len(sig['tabs'])} err={len(sig['errors'])} "
            f"search={len(sig['search'])} ct={sig['has_ctimage']} comps={len(sig['pages_or_comps'])}"
        )
        n += 1
    print(f"built {n} signals.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
