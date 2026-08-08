#!/usr/bin/env python3
"""Offline gate: signals + prop modules importable. No phone / hdc."""
from __future__ import annotations

import importlib
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MINED = Path(__file__).resolve().parent / "mined_all"
SAVED_APPS = [
    "com.huawei.hmos.calculator",
    "com.ctrip.harmonynext",
    "com.amap.hmapp",
    "com.sankuai.dianping",
    "com.sankuai.hmeituan",
    "com.sina.weibo.stage",
    "com.taobao.idlefish4ohos",
    "com.zhihu.hmos",
    "com.ss.hm.ugc.aweme",
    "com.kuaishou.hmapp",
    "com.phoenix.read.next",
    "com.youku.next",
    "com.xunmeng.pinduoduo.hos",
]


def check_signals() -> list[str]:
    errs = []
    for pkg in SAVED_APPS:
        p = MINED / pkg / "signals.json"
        if not p.exists():
            errs.append(f"missing signals {pkg}")
            continue
        s = json.loads(p.read_text(encoding="utf-8"))
        if s.get("package") != pkg:
            errs.append(f"pkg mismatch {pkg}")
        if not s.get("tabs"):
            errs.append(f"no tabs {pkg}")
        if not s.get("errors"):
            errs.append(f"no errors {pkg}")
    # ctrip CTImage hard requirement
    ct = json.loads((MINED / "com.ctrip.harmonynext" / "signals.json").read_text(encoding="utf-8"))
    if not ct.get("has_ctimage"):
        errs.append("ctrip has_ctimage=false")
    hits = MINED / "com.ctrip.harmonynext" / "ctimage_hits.txt"
    if not hits.exists() or "CTImage" not in hits.read_text(encoding="utf-8", errors="ignore"):
        errs.append("ctrip ctimage_hits missing CTImage")
    return errs


def check_imports() -> list[str]:
    errs = []
    mods = [
        "properties.modeA_props.decompiled",
        "properties.modeA_props.ctrip_ctimage",
        "properties.modeA_props.calculator_decompiled",
        "properties.modeA_props.semantic",
        "properties.modeA_props.bug_find",
        "properties.modeA_props.flow",
    ]
    for m in mods:
        try:
            mod = importlib.import_module(m)
        except Exception as e:
            errs.append(f"import {m}: {e}")
            continue
        # must expose at least one TestCase
        tests = [
            getattr(mod, n)
            for n in dir(mod)
            if isinstance(getattr(mod, n, None), type)
            and issubclass(getattr(mod, n), unittest.TestCase)
            and getattr(mod, n) is not unittest.TestCase
        ]
        if not tests:
            errs.append(f"no TestCase in {m}")
            continue
        # count test_* methods
        n = sum(
            1
            for t in tests
            for name in dir(t)
            if name.startswith("test_")
        )
        if n < 1:
            errs.append(f"no tests in {m}")
        print(f"  OK {m} classes={len(tests)} tests={n}")
    return errs


def check_decompiled_loader() -> list[str]:
    errs = []
    from properties.modeA_props import decompiled as d

    os.environ["KEA2_TARGET_PKG"] = "com.ctrip.harmonynext"
    d._load_signals.cache_clear()
    s = d._load_signals("com.ctrip.harmonynext")
    if not s.get("tabs"):
        errs.append("loader empty ctrip tabs")
    # calculator
    s2 = d._load_signals("com.huawei.hmos.calculator")
    if not s2:
        errs.append("loader empty calculator")
    # missing pkg
    s3 = d._load_signals("com.no.such.app")
    if s3:
        errs.append("loader should be empty for unknown")
    print(f"  OK loader ctrip_tabs={len(s.get('tabs',[]))} calc_keys={list(s2)[:5]}")
    return errs


def check_calculator_xabc() -> list[str]:
    errs = []
    ts = Path(__file__).resolve().parent / "calculator_xabc" / "arkdemo_app.ts"
    if not ts.exists():
        errs.append("missing calculator_xabc/arkdemo_app.ts")
        return errs
    text = ts.read_text(encoding="utf-8", errors="ignore")
    for needle in ("HistoryRecord", "PhysicsButton", "PanelSize", "calculator"):
        if needle not in text:
            errs.append(f"xabc ts missing {needle}")
    print(f"  OK xabc ts bytes={ts.stat().st_size}")
    return errs


def main() -> int:
    print("== rebuild signals ==")
    import runpy

    try:
        runpy.run_path(str(Path(__file__).parent / "build_signals.py"), run_name="__main__")
    except SystemExit as e:
        if e.code not in (0, None):
            return int(e.code or 1)

    print("== signals ==")
    e1 = check_signals()
    print("== imports ==")
    e2 = check_imports()
    print("== loader ==")
    e3 = check_decompiled_loader()
    print("== xabc calculator ==")
    e4 = check_calculator_xabc()

    errs = e1 + e2 + e3 + e4
    if errs:
        print("FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print("ALL_OFFLINE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
