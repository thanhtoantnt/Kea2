"""Require offline decompile signals before Mode A / Mode B kea runs.

Input contract: installed package + modeA_runs/decompile_exp/mined_all/<pkg>/signals.json
(from HAP/ABC mine and/or xabc). No signals → abort; do not run boost-only shells.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_MINED = _REPO / "modeA_runs" / "decompile_exp" / "mined_all"


def signals_path(pkg: str, repo: Path | None = None) -> Path:
    root = repo or _REPO
    return root / "modeA_runs" / "decompile_exp" / "mined_all" / pkg / "signals.json"


def has_decompile_signals(pkg: str, repo: Path | None = None) -> bool:
    """True if signals.json exists and is non-empty JSON object with package or labels."""
    if not pkg or pkg in (".", "*"):
        return False
    p = signals_path(pkg, repo)
    if not p.is_file() or p.stat().st_size < 8:
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    # real mine/xabc output — not an empty stub
    if data.get("package") == pkg:
        return True
    for k in ("tabs", "search", "actions", "errors", "empty", "misc_labels", "source"):
        v = data.get(k)
        if isinstance(v, (list, str)) and len(v) > 0:
            return True
    return False


def require_decompile_signals(pkg: str | None = None, repo: Path | None = None) -> str:
    """Return pkg if ok; raise FileNotFoundError with prep hint otherwise."""
    pkg = (pkg or os.environ.get("KEA2_TARGET_PKG") or os.environ.get("KEA2_PACKAGE") or "").strip()
    if not pkg:
        raise FileNotFoundError(
            "decompile gate: no package (set KEA2_TARGET_PKG / KEA2_PACKAGE). "
            "Need installed app + mined_all/<pkg>/signals.json before Mode A/B."
        )
    p = signals_path(pkg, repo)
    if has_decompile_signals(pkg, repo):
        return pkg
    raise FileNotFoundError(
        f"decompile gate: missing signals for {pkg}\n"
        f"  expected: {p}\n"
        f"  Prep offline: HAP/ABC → mine/xabc → signals.json "
        f"(see modeA_runs/decompile_exp/PIPELINE.md / PREPARE_BEFORE_KEA.md).\n"
        f"  Mode A and Mode B both abort without decompiled inputs."
    )


if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        print(require_decompile_signals(pkg))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
