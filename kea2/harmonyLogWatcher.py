"""
HarmonyOS crash/ANR watcher via hilog.

Android Kea2 uses Fastbot's crash-dump.log. Harmony has no Fastbot, so Mode A
previously always reported "No crash was found". This watcher tails hilog for
the SUT package(s), writes Fastbot-compatible crash-dump.log blocks so the
existing HTML report parsers work, and exposes has_crash_or_anr.
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from .hdcUtils import HDCDevice, _hdc_bin
from .utils import getLogger

logger = getLogger(__name__)

# Hilog / faultlogger signatures observed on HarmonyOS NEXT
_CRASH_LINE = re.compile(
    r"(JsError|JSERROR|JS Crash|js crash|jscrash|Fatal error|FATAL EXCEPTION|"
    r"appfreeze|APP_INPUT_BLOCK|Process dump|FaultLogger|"
    r"cppcrash|SIGNAL\s*\d+|SIGABRT|SIGSEGV|"
    r"NullPointerException|Error name:|Error message:|"
    r"Stack overflow|RangeError|ace_engine|ArkCompiler|HasCrashed)",
    re.I,
)
_ANR_LINE = re.compile(
    r"(APP_INPUT_BLOCK|appfreeze|not responding|ANR in |Input dispatching timed out)",
    re.I,
)


class HarmonyLogWatcher:
    """Poll hilog; emit crash-dump.log in Fastbot format for HTML reports."""

    def __init__(
        self,
        crash_dump_path: Path,
        packages: List[str],
        serial: Optional[str] = None,
        poll_interval: float = 4.0,
    ):
        self.crash_dump_path = Path(crash_dump_path)
        self.packages = list(packages or [])
        self.serial = serial or HDCDevice.serial
        self.poll_interval = poll_interval
        self.has_crash_or_anr = False
        self.end_flag = False
        self._seen: Set[str] = set()
        self._seen_fault_files: Set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        # only treat faultlogger files newer than watcher start as this-run crashes
        self._started_at = time.time()
        self.crash_dump_path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: do NOT touch empty crash-dump.log — report treats missing file as "No crash"

    def start(self):
        self._thread = threading.Thread(
            target=self._loop, name="HarmonyLogWatcher", daemon=True
        )
        self._thread.start()
        logger.info(
            f"HarmonyLogWatcher started → {self.crash_dump_path} pkgs={self.packages}"
        )

    def close(self):
        self.end_flag = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.poll_interval + 2)
        # final drain
        try:
            self._poll_once()
        except Exception as e:
            logger.debug(f"HarmonyLogWatcher final poll: {e}")
        logger.info(
            f"Close: HarmonyLogWatcher has_crash_or_anr={self.has_crash_or_anr}"
        )

    def _hdc_hilog(self) -> str:
        if not self.serial:
            return ""
        # -x: dump buffer once; -z: no block. Keep window small.
        cmd = [
            _hdc_bin(),
            "-t",
            self.serial,
            "shell",
            "hilog -x -z 2000 2>/dev/null || hilog -x 2>/dev/null | tail -n 400",
        ]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=15,
            )
            return (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            logger.debug(f"hilog poll failed: {e}")
            return ""

    def _faultlogger_snip(self) -> str:
        """Pull *new* faultlogger files for SUT (mtime after watcher start)."""
        if not self.packages:
            return ""
        out = ""
        try:
            bin_ = _hdc_bin()
            # name + epoch mtime; head enough for multi-app noise
            ls = subprocess.run(
                [
                    bin_,
                    "-t",
                    self.serial,
                    "shell",
                    "cd /data/log/faultlog/faultlogger 2>/dev/null && "
                    "ls -t 2>/dev/null | head -n 20 | while read f; do "
                    "stat -c '%Y %n' \"$f\" 2>/dev/null || stat -f '%m %N' \"$f\" 2>/dev/null; "
                    "done",
                ],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=12,
            )
            rows = []
            for line in (ls.stdout or "").splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) != 2:
                    continue
                try:
                    mt = float(parts[0])
                except ValueError:
                    continue
                rows.append((mt, parts[1].strip()))
            # grace: files from 30s before start (cold-start race)
            cutoff = self._started_at - 30
            for mt, name in rows[:12]:
                if name in self._seen_fault_files:
                    continue
                if mt < cutoff:
                    continue
                pkg_hit = any(p in name for p in self.packages)
                kind_hit = bool(re.search(r"jscrash|cppcrash|appfreeze|jserror", name, re.I))
                if not pkg_hit and not kind_hit:
                    continue
                cat = subprocess.run(
                    [
                        bin_,
                        "-t",
                        self.serial,
                        "shell",
                        f"head -n 120 /data/log/faultlog/faultlogger/{name} 2>/dev/null",
                    ],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=10,
                )
                body = cat.stdout or ""
                if not body:
                    continue
                if self.packages and not any(p in body or p in name for p in self.packages):
                    continue
                self._seen_fault_files.add(name)
                out += f"\n// faultlogger:{name}\n{body}\n"
        except Exception as e:
            logger.debug(f"faultlogger snip: {e}")
        return out

    def _relevant(self, text: str) -> bool:
        if not self.packages:
            return True
        return any(p in text for p in self.packages)

    def _fingerprint(self, kind: str, body: str) -> str:
        # collapse whitespace; keep first 240 chars
        key = re.sub(r"\s+", " ", body)[:240]
        return f"{kind}:{key}"

    def _emit_crash(self, body: str, kind: str = "crash"):
        fp = self._fingerprint(kind, body)
        with self._lock:
            if fp in self._seen:
                return
            self._seen.add(fp)
            self.has_crash_or_anr = True
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            pkg = next((p for p in self.packages if p in body), self.packages[0] if self.packages else "unknown")
            # Fastbot-compatible block for mixin CRASH_PATTERN / ANR_PATTERN
            if kind == "anr":
                block = (
                    f"{ts}\n"
                    f"anr:\n"
                    f"// ANR: {pkg}\n"
                    f"// Reason: appfreeze/APP_INPUT_BLOCK (Harmony hilog)\n"
                    f"{body}\n"
                    f"anr end\n"
                )
            else:
                # Prefer // CRASH lines so _extract_crash_info fills process/type
                if "// CRASH:" not in body and "CRASH:" not in body:
                    header = (
                        f"// CRASH: {pkg} (pid 0) (dump time: {ts})\n"
                        f"// Long Msg: HarmonyFault: detected via hilog/faultlogger\n"
                    )
                else:
                    header = ""
                stack = "\n".join(
                    ("// " + ln if not ln.startswith("//") else ln)
                    for ln in body.strip().splitlines()[:80]
                )
                block = (
                    f"{ts}\n"
                    f"crash:\n"
                    f"{header}"
                    f"{stack}\n"
                    f"// crash end\n"
                )
            with open(self.crash_dump_path, "a", encoding="utf-8") as fp_out:
                fp_out.write(block)
            logger.warning(f"[Harmony] {kind.upper()} recorded for {pkg} → {self.crash_dump_path}")
            print(f"[INFO] Harmony {kind} detected: package={pkg}", flush=True)

    def _poll_once(self):
        text = self._hdc_hilog()
        if not text:
            return
        # scan line windows
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if not self._relevant(line) and not _CRASH_LINE.search(line) and not _ANR_LINE.search(line):
                continue
            window = "\n".join(lines[max(0, i - 2) : min(len(lines), i + 15)])
            if not self._relevant(window):
                continue
            if _ANR_LINE.search(line):
                self._emit_crash(window, kind="anr")
            elif _CRASH_LINE.search(line):
                self._emit_crash(window, kind="crash")
        # faultlogger backup
        fl = self._faultlogger_snip()
        if fl and self._relevant(fl):
            if _ANR_LINE.search(fl):
                self._emit_crash(fl, kind="anr")
            else:
                self._emit_crash(fl, kind="crash")

    def _loop(self):
        while not self.end_flag:
            try:
                self._poll_once()
            except Exception as e:
                logger.debug(f"HarmonyLogWatcher poll error: {e}")
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    # ponytail: format self-check without device
    from pathlib import Path
    import tempfile

    td = Path(tempfile.mkdtemp())
    p = td / "crash-dump.log"
    w = HarmonyLogWatcher(p, ["com.example.app"], serial="fake")
    w._emit_crash("JsError: boom\nat foo.bar:1", kind="crash")
    w._emit_crash("APP_INPUT_BLOCK com.example.app", kind="anr")
    body = p.read_text()
    assert "crash:" in body and "// crash end" in body, body
    assert "anr:" in body and "anr end" in body, body
    assert w.has_crash_or_anr
    print("harmonyLogWatcher self-check ok")
