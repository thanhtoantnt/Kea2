"""Require offline decompile signals before Mode A / Mode B kea runs.

Decompile tree is NOT inside Kea2. Resolve order:
  1. KEA2_DECOMPILE_HOME / PBT_KEA_DECOMPILE_HOME
  2. sibling ../kea2-decompile (next to Kea2 checkout)
  3. ~/github/kea2-decompile
  4. legacy Kea2/modeA_runs/decompile_exp (compat only)

Input contract: installed package + <decompile_home>/mined_all/<pkg>/signals.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_KEA2 = Path(__file__).resolve().parents[2]


def decompile_home(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = (
        os.environ.get("KEA2_DECOMPILE_HOME")
        or os.environ.get("PBT_KEA_DECOMPILE_HOME")
        or ""
    ).strip()
    if env:
        return Path(env).expanduser().resolve()
    candidates = [
        _KEA2.parent / "kea2-decompile",
        Path.home() / "github" / "kea2-decompile",
        _KEA2 / "modeA_runs" / "decompile_exp",  # legacy
    ]
    for c in candidates:
        if (c / "mined_all").is_dir():
            return c.resolve()
    return candidates[0].resolve()


def signals_path(pkg: str, home: Path | None = None) -> Path:
    return (home or decompile_home()) / "mined_all" / pkg / "signals.json"


def has_decompile_signals(pkg: str, home: Path | None = None) -> bool:
    if not pkg or pkg in (".", "*"):
        return False
    p = signals_path(pkg, home)
    if not p.is_file() or p.stat().st_size < 8:
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("package") == pkg:
        return True
    for k in ("tabs", "search", "actions", "errors", "empty", "misc_labels", "source"):
        v = data.get(k)
        if isinstance(v, (list, str)) and len(v) > 0:
            return True
    return False


def require_decompile_signals(pkg: str | None = None, home: Path | None = None) -> str:
    pkg = (pkg or os.environ.get("KEA2_TARGET_PKG") or os.environ.get("KEA2_PACKAGE") or "").strip()
    root = home or decompile_home()
    if not pkg:
        raise FileNotFoundError(
            "decompile gate: no package (set KEA2_TARGET_PKG / KEA2_PACKAGE). "
            f"Need installed app + {root}/mined_all/<pkg>/signals.json before Mode A/B."
        )
    p = signals_path(pkg, root)
    if has_decompile_signals(pkg, root):
        return pkg
    raise FileNotFoundError(
        f"decompile gate: missing signals for {pkg}\n"
        f"  expected: {p}\n"
        f"  decompile_home: {root}\n"
        f"  Set KEA2_DECOMPILE_HOME or clone kea2-decompile next to Kea2.\n"
        f"  Prep: HAP/ABC → mine/xabc → mined_all/<pkg>/signals.json.\n"
        f"  Mode A and Mode B both abort without decompiled inputs."
    )


if __name__ == "__main__":
    import sys

    pkg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        print(require_decompile_signals(pkg))
        print(f"# home={decompile_home()}", file=sys.stderr)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(2)
