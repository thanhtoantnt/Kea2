#!/usr/bin/env python3
"""Merge xabc dumps + mined_all → signals.json (input for decompiled.py props).

General approach:
  decompiled files (arkdemo.ts / .names.ts) + abc string mine → signals → Mode A props.

Usage:
  python modeA_runs/decompile_exp/generate_props_from_decompile.py
  python modeA_runs/decompile_exp/generate_props_from_decompile.py --pkg com.ctrip.harmonynext
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MINED = ROOT / "mined_all"
XABC = ROOT / "xabc_out" / "decompiled"
# also accept flat calculator_xabc
XABC_ALT = {
    "com.huawei.hmos.calculator": ROOT / "calculator_xabc",
}

REC_RE = re.compile(r"^// record:\s*(.+)$")
METH_RE = re.compile(r"^// method:\s*(.+)$")
CT_RE = re.compile(r"(?:ctcommon/ctimage|(?<![A-Za-z])CTImage(?![a-z]))")
TAB_OK = {
    "首页", "我的", "消息", "发现", "推荐", "视频", "直播", "关注", "热门", "热榜",
    "行程", "酒店", "门票", "火车票", "机票", "美食", "地图", "导航", "打车",
    "闲鱼", "知乎", "美团", "点评", "商城", "同城", "分类", "订单", "会员",
    "短剧", "朋友", "我", "Search", "Home", "Me", "Message", "Feed", "Live",
}
SEARCH_OK = {"搜索", "Search", "搜一搜", "查地点", "找公交"}
ACT_OK = {"取消", "确认", "重试", "刷新", "返回", "关闭", "删除", "清除", "登录", "知道了"}
ERR_KW = re.compile(r"(失败|异常|错误|网络|重试|超时|无法|error|fail)", re.I)
EMPTY_KW = re.compile(r"(暂无|无记录|空空|无内容|empty)", re.I)


def uniq(xs, n=50):
    s, o = set(), []
    for x in xs:
        if not x or x in s:
            continue
        s.add(x)
        o.append(x)
        if len(o) >= n:
            break
    return o


def parse_xabc_ts(path: Path) -> dict:
    if not path.exists():
        return {}
    records, methods, texts = [], [], []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = REC_RE.match(line.strip())
        if m:
            records.append(m.group(1).strip())
            continue
        m = METH_RE.match(line.strip())
        if m:
            methods.append(m.group(1).strip())
            continue
        # free text / imports
        for zh in re.findall(r"[\u4e00-\u9fff]{2,12}", line):
            texts.append(zh)
        if "CTImage" in line or "ctcommon/ctimage" in line:
            texts.append(line.strip()[:120])
    comps = []
    for r in records + methods:
        comps += re.findall(
            r"([A-Z][A-Za-z0-9]{3,40}(?:Page|Ability|View|Component|Panel|Loader|Record|Button))",
            r,
        )
    return {
        "records": uniq(records, 5000),
        "methods": uniq(methods, 20000),
        "texts": uniq(texts, 2000),
        "comps": uniq(comps, 200),
        "has_ctimage": any(CT_RE.search(x) for x in records + methods + texts),
        "source_file": str(path),
    }


def load_mine(pkg: str) -> dict:
    d = MINED / pkg
    if not d.exists():
        return {}
    out = {}
    for name in ("labels_cjk.txt", "strings_hits.txt", "methods_like.txt", "classes_like.txt", "ctimage_hits.txt"):
        p = d / name
        if p.exists():
            out[name] = [
                ln.strip()
                for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if ln.strip()
            ]
    return out


def build_signals(pkg: str) -> dict:
    # prefer richest xabc file
    candidates = []
    base = XABC / pkg
    if pkg in XABC_ALT:
        base2 = XABC_ALT[pkg]
        candidates += list(base2.glob("arkdemo*.ts"))
    if base.exists():
        candidates += [
            base / "arkdemo.ts",
            base / "arkdemo_app.ts",
            base / "arkdemo.ts.names.ts",
        ]
    xabc = {}
    best_score = -1
    for c in candidates:
        if not (c.exists() and c.stat().st_size > 0):
            continue
        parsed = parse_xabc_ts(c)
        head = c.read_text(encoding="utf-8", errors="ignore")[:300]
        # prefer full AST over names-only dump
        score = len(parsed.get("records") or []) + len(parsed.get("methods") or [])
        if "fallback dump" in head or "// record:" in head:
            score += 1  # names dump
        else:
            score += 100000 + c.stat().st_size // 1000  # full AST wins
        if score > best_score:
            best_score = score
            xabc = parsed
            xabc["picked"] = str(c)

    mine = load_mine(pkg)
    labels = mine.get("labels_cjk.txt") or []
    hits = mine.get("strings_hits.txt") or []
    pool = labels + hits + list(xabc.get("texts") or [])

    tabs, search, errs, empty, actions, misc = [], [], [], [], [], []
    for s in pool:
        if len(s) > 16:
            continue
        if s in TAB_OK:
            tabs.append(s)
        if s in SEARCH_OK or (len(s) <= 6 and "搜索" in s):
            search.append(s if len(s) <= 8 else "搜索")
        if EMPTY_KW.search(s):
            empty.append(s)
        if ERR_KW.search(s):
            errs.append(s)
        if s in ACT_OK:
            actions.append(s)
        if 2 <= len(s) <= 6 and re.fullmatch(r"[\u4e00-\u9fff]+", s):
            misc.append(s)

    ct_syms = []
    for s in (mine.get("ctimage_hits.txt") or []) + (xabc.get("records") or []) + (xabc.get("methods") or []):
        if CT_RE.search(s):
            ct_syms.append(s[:120])

    # pages from xabc records
    pages = list(xabc.get("comps") or [])
    for r in (xabc.get("records") or [])[:500]:
        if "Page" in r or "Ability" in r:
            pages.append(r.split("/")[-1][:80])

    tier = "C_mine"
    if xabc.get("records") or xabc.get("methods"):
        tier = "B_names"
    picked = Path(xabc["picked"]) if xabc.get("picked") else None
    # full AST: large file without // record dump markers
    if picked and picked.exists() and picked.stat().st_size > 200_000:
        head = picked.read_text(encoding="utf-8", errors="ignore")[:500]
        if "// record:" not in head and "fallback dump" not in head:
            tier = "A_ast"

    sig = {
        "package": pkg,
        "decompile_tier": tier,
        "xabc_source": xabc.get("picked"),
        "xabc_records": len(xabc.get("records") or []),
        "xabc_methods": len(xabc.get("methods") or []),
        "tabs": uniq(tabs, 20) or ["首页", "我的", "消息"],
        "search": uniq(search, 12) or ["搜索", "Search"],
        "errors": uniq(errs, 40) or ["网络异常", "加载失败", "请重试"],
        "empty": uniq(empty, 20) or ["暂无", "无内容"],
        "actions": uniq(actions, 25),
        "misc_labels": uniq(misc, 50),
        "pages_or_comps": uniq(pages, 40),
        "has_ctimage": bool(ct_syms) or bool(xabc.get("has_ctimage")),
        "ctimage_symbols": uniq(ct_syms, 25),
        "record_samples": (xabc.get("records") or [])[:30],
        "method_samples": (xabc.get("methods") or [])[:30],
        "source": "xabc+mine",
    }
    return sig


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", action="append", default=[])
    args = ap.parse_args(argv)

    pkgs = args.pkg
    if not pkgs:
        pkgs = sorted({p.name for p in MINED.iterdir() if p.is_dir()} | {p.name for p in XABC.iterdir() if p.is_dir()}) if XABC.exists() else sorted(p.name for p in MINED.iterdir() if p.is_dir())

    summary = {}
    for pkg in pkgs:
        if pkg in ("calculator",):
            pkg = "com.huawei.hmos.calculator"
        sig = build_signals(pkg)
        out_dir = MINED / pkg
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "signals.json").write_text(json.dumps(sig, ensure_ascii=False, indent=2), encoding="utf-8")
        summary[pkg] = {
            "tier": sig["decompile_tier"],
            "tabs": len(sig["tabs"]),
            "records": sig["xabc_records"],
            "methods": sig["xabc_methods"],
            "ct": sig["has_ctimage"],
            "xabc": sig.get("xabc_source"),
        }
        print(
            f"{pkg}: tier={sig['decompile_tier']} tabs={len(sig['tabs'])} "
            f"rec={sig['xabc_records']} meth={sig['xabc_methods']} ct={sig['has_ctimage']}"
        )

    (ROOT / "DECOMPILE_PROPS_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote", ROOT / "DECOMPILE_PROPS_SUMMARY.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
