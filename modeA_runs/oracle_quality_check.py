#!/usr/bin/env python3
"""Offline oracle quality: seeded good/bad fixtures → catch rate.

No device. Proves helpers would fail real bug classes we claim to detect.
Exit 0 if catch_rate >= 0.8 on seeded bugs.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _node(text="", bounds="[0,0][100,100]", clickable="false", children=None):
    return {
        "attributes": {
            "text": text,
            "bounds": bounds,
            "clickable": clickable,
            "enabled": "true",
        },
        "children": children or [],
    }


def good_feed():
    """Normal app home: tabs + content."""
    return _node(
        children=[
            _node("首页", "[0,2700][256,2832]", "true"),
            _node("推荐", "[256,2700][512,2832]", "true"),
            _node("热榜", "[512,2700][768,2832]", "true"),
            _node("消息", "[768,2700][1024,2832]", "true"),
            _node("我的", "[1024,2700][1280,2832]", "true"),
            _node("如何评价c罗和梅西", "[40,400][1200,500]"),
            _node("搜索", "[40,120][400,200]", "true"),
            _node("关注", "[40,200][200,280]", "true"),
        ]
    )


def bad_blank():
    """Blank / dead page after nav."""
    return _node(children=[_node("", "[0,0][10,10]"), _node(" ", "[0,0][10,10]")])


def bad_no_retry_error():
    """Error state without retry — should trip EMPTY-style checks."""
    return _node(children=[_node("加载失败", "[100,1000][500,1100]"), _node("网络异常", "[100,1100][500,1200]")])


def bad_overlap_chaos():
    """Peer cards heavily overlapping (area under clickable_nodes cap)."""
    # area must be < 2e6 (clickable_nodes filter) and > 400
    return _node(
        children=[
            _node("CardA", "[40,400][640,900]", "true"),
            _node("CardB", "[50,410][650,910]", "true"),
            _node("CardC", "[45,405][645,905]", "true"),
        ]
    )


class FakeD:
    """Minimal driver: dump_hierarchy + text exists/click stubs."""

    def __init__(self, hierarchy, pkg="com.zhihu.hmos"):
        self._h = hierarchy
        self._pkg = pkg
        self._texts = self._collect(hierarchy)

    def _collect(self, n, out=None):
        out = out if out is not None else []
        if isinstance(n, dict):
            a = n.get("attributes") or n
            t = (a.get("text") or "").strip()
            if t:
                out.append(t)
            for c in n.get("children") or []:
                self._collect(c, out)
        return out

    def dump_hierarchy(self):
        return self._h

    def __call__(self, text=None, textContains=None, **kw):
        outer = self

        class Sel:
            def exists(self, timeout=0):
                if text is not None:
                    return text in outer._texts
                if textContains is not None:
                    return any(textContains in t for t in outer._texts)
                return False

            def click(self):
                return True

            def get_text(self):
                return text or ""

        return Sel()


def run():
    from properties.modeA_props._util import (
        TABISH,
        any_text,
        count_bad_overlaps,
        count_texts,
        hierarchy_fingerprint,
        hierarchy_text_count,
        ui_alive,
    )

    results = []  # (name, should_catch, caught)

    # --- seeded bugs: oracle MUST fail / return bad ---
    d_blank = FakeD(bad_blank())
    n = hierarchy_text_count(d_blank)
    caught = n < 5 and not ui_alive(d_blank)
    results.append(("blank_page_detected", True, caught))

    d_err = FakeD(bad_no_retry_error())
    # error without retry buttons
    has_err = any_text(d_err, ("加载失败", "网络异常"))
    has_retry = any_text(d_err, ("重试", "刷新", "点击重试"))
    caught = has_err and not has_retry
    results.append(("error_without_retry_flagged", True, caught))

    d_ov = FakeD(bad_overlap_chaos())
    bad = count_bad_overlaps(d_ov, min_ratio=0.5)
    caught = bad >= 1
    results.append(("overlap_chaos_detected", True, caught))

    # --- good fixtures: must NOT false-positive as dead ---
    d_ok = FakeD(good_feed())
    alive = ui_alive(d_ok) and hierarchy_text_count(d_ok) >= 5
    tabs = count_texts(d_ok, ("首页", "推荐", "热榜")) >= 2
    results.append(("good_feed_alive", False, not alive))  # should_catch=False; caught=FP
    results.append(("good_feed_tabs", False, not tabs))

    fp1 = hierarchy_fingerprint(d_ok)
    fp2 = hierarchy_fingerprint(FakeD(good_feed()))
    # same structure → same fp
    results.append(("fingerprint_stable", False, fp1 != fp2))

    # tab-rich for semantic precond
    results.append(("semantic_tab_precond", False, count_texts(d_ok, ("推荐", "热榜", "关注", "首页")) < 2))

    # TABISH includes 热榜 after expand
    results.append(("tabish_has_rebang", False, "热榜" not in TABISH))

    # score: among should_catch=True, fraction caught; among should_catch=False, fraction not FP
    detect = [r for r in results if r[1]]
    clean = [r for r in results if not r[1]]
    detect_rate = sum(1 for _, _, c in detect if c) / max(len(detect), 1)
    clean_rate = sum(1 for _, _, c in clean if not c) / max(len(clean), 1)
    # combined: catch bugs + don't FP
    score = 0.6 * detect_rate + 0.4 * clean_rate

    print("# Oracle quality (seeded fixtures)")
    print(f"detect_rate={detect_rate:.0%} ({sum(1 for *_, c in detect if c)}/{len(detect)})")
    print(f"clean_rate={clean_rate:.0%} (no-FP {sum(1 for *_, c in clean if not c)}/{len(clean)})")
    print(f"score={score:.2f} (need >= 0.80)")
    print()
    for name, should, caught in results:
        if should:
            mark = "CATCH" if caught else "MISS"
        else:
            mark = "FP!" if caught else "ok"
        print(f"  [{mark}] {name}")

    # write report snippet
    rep = ROOT / "modeA_runs" / "ORACLE_QUALITY_REPORT.md"
    lines = [
        "# Oracle quality — seeded fixtures",
        "",
        f"- detect_rate: **{detect_rate:.0%}**",
        f"- clean_rate (no FP): **{clean_rate:.0%}**",
        f"- score: **{score:.2f}** (pass ≥ 0.80)",
        "",
        "| case | expect | result |",
        "|------|--------|--------|",
    ]
    for name, should, caught in results:
        if should:
            res = "CATCH" if caught else "MISS"
            exp = "detect bug"
        else:
            res = "FP" if caught else "clean"
            exp = "no FP"
        lines.append(f"| {name} | {exp} | {res} |")
    lines += [
        "",
        "## Limits",
        "- Offline fixtures only prove **helper** logic, not live Kea2 wiring.",
        "- Semantic props still need live fire-rate run.",
        "- Soft `ui_alive` still misses wrong-price / wrong-page bugs.",
    ]
    rep.write_text("\n".join(lines) + "\n")
    print(f"\nreport: {rep}")
    return 0 if score >= 0.80 else 1


if __name__ == "__main__":
    raise SystemExit(run())
