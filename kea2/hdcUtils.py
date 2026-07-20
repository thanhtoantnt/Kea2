"""HarmonyOS device helpers via `hdc` (parallel to adbUtils for Android)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import List, Optional

from .utils import getLogger

logger = getLogger(__name__)


def _hdc_bin() -> str:
    env = os.environ.get("HDC_PATH") or os.environ.get("PBT_HDC")
    if env and os.path.isfile(env):
        return env
    which = shutil.which("hdc")
    if which:
        return which
    # common user install
    home = os.path.expanduser("~/.local/bin/hdc")
    if os.path.isfile(home):
        return home
    raise FileNotFoundError(
        "hdc not found on PATH. Install HarmonyOS hdc and ensure `hdc list targets` works "
        "(or set HDC_PATH)."
    )


class HDCDevice:
    """Thin hdc wrapper for one connected HarmonyOS device."""

    _instance: Optional["HDCDevice"] = None
    serial: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def setDevice(cls, serial: Optional[str] = None):
        cls.serial = serial or cls.serial

    @classmethod
    def list_targets(cls) -> List[str]:
        out = subprocess.check_output([_hdc_bin(), "list", "targets"], text=True, errors="replace")
        lines = []
        for line in out.splitlines():
            line = line.strip()
            if not line or "[Empty]" in line:
                continue
            # first token is serial
            serial = line.split()[0]
            if serial and serial != "[Empty]":
                lines.append(serial)
        return lines

    def __init__(self):
        if not HDCDevice.serial:
            targets = self.list_targets()
            if len(targets) == 0:
                raise RuntimeError("No hdc device connected (`hdc list targets` empty).")
            if len(targets) > 1:
                raise RuntimeError(
                    f"Multiple hdc devices {targets}. Pass -s/--serial."
                )
            HDCDevice.serial = targets[0]
        self.serial = HDCDevice.serial
        self.bin = _hdc_bin()
        logger.info(f"HDC device: {self.serial} ({self.bin})")

    def shell(self, cmd: str, timeout: Optional[float] = 60) -> str:
        full = [self.bin, "-t", self.serial, "shell", cmd]
        try:
            r = subprocess.run(
                full,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
            )
            return (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            logger.warning(f"hdc shell timeout: {cmd[:80]}")
            return ""

    def force_stop(self, package: str) -> None:
        self.shell(f"aa force-stop {package}")

    def unlock(self) -> None:
        """Wake + swipe up (Kea DeviceHM.unlock is Home/Back only — not enough on lock)."""
        self.shell("power-shell wakeup")
        self.shell("uitest uiInput swipe 640 2400 640 400 400")

    def resolve_main_ability(self, package: str) -> Optional[str]:
        """mainAbility from `bm dump -n` (same idea as Kea AppHM._dumpsys_package_info)."""
        out = self.shell(f"bm dump -n {package}")
        if not out:
            return None
        # prefer JSON hapModuleInfos[].mainAbility
        start = out.find("{")
        if start >= 0:
            try:
                import json

                data = json.loads(out[start:])
                haps = data.get("hapModuleInfos") or []
                # entry module first if present
                entry = data.get("entryModuleName")
                ordered = sorted(
                    haps,
                    key=lambda h: 0 if (h.get("name") or h.get("moduleName")) == entry else 1,
                ) if isinstance(haps, list) else []
                for h in ordered:
                    if not isinstance(h, dict):
                        continue
                    ab = h.get("mainAbility") or h.get("mainElement")
                    if ab:
                        return str(ab)
            except Exception as e:
                logger.debug(f"bm dump JSON parse failed for {package}: {e}")
        m = re.search(r'"mainAbility"\s*:\s*"([^"]+)"', out)
        return m.group(1) if m else None

    def get_top_ability(self) -> Optional[str]:
        """bundle/ability of FOREGROUND mission (Kea DeviceHM.get_top_activity_name)."""
        out = self.shell("aa dump -l")
        if "#FOREGROUND" not in out and "state #FOREGROUND" not in out:
            return None
        for block in out.split("Mission ID"):
            if "state #FOREGROUND" not in block:
                continue
            m = re.search(
                r"mission name #\[#(?P<bundle>[^:]+):[^:]*:(?P<ability>[^\]]+)\]",
                block,
            )
            if m:
                return f"{m.group('bundle')}/{m.group('ability')}"
            # fallback: bundle name + main name fields
            b = re.search(r"bundle name \[([^\]]+)\]", block)
            a = re.search(r"main name \[([^\]]+)\]", block)
            if b and a:
                return f"{b.group(1)}/{a.group(1)}"
        return None

    def start_ability(self, package: str, ability: str = "EntryAbility") -> str:
        # Order: env → bm-dump mainAbility → caller → common fallbacks (Kea-style).
        env_ab = os.environ.get("PBT_KEA_ABILITY")
        discovered = self.resolve_main_ability(package)
        candidates = []
        # bm dump may return FQN (clock.phone) or pkg.CalculatorAbility; aa start
        # sometimes wants short name only (CalculatorAbility). Try both.
        discovered_short = None
        if discovered and discovered.startswith(package + "."):
            discovered_short = discovered[len(package) + 1 :]
        for a in (
            env_ab,
            discovered_short,
            discovered,
            ability,
            "EntryAbility",
            "MainAbility",
            "CalculatorAbility",
            f"{package}.phone",
            f"{package}.MainAbility",
        ):
            if a and a not in candidates:
                candidates.append(a)
        last = ""
        import time as _time

        def _wait_fg(timeout_s: float = 3.0) -> bool:
            deadline = _time.time() + timeout_s
            while _time.time() < deadline:
                if self.is_package_foreground(package):
                    return True
                _time.sleep(0.4)
            return False

        self.unlock()
        for a in candidates:
            out = self.shell(f"aa start -a {a} -b {package}")
            last = out
            ok = "start ability successfully" in out.lower()
            if not ok and ("failed to start" in out.lower() or "error" in out.lower()):
                continue
            if _wait_fg():
                if discovered and a == discovered:
                    logger.info(f"Started {package} via bm-dump ability {a!r}")
                return out
            logger.warning(f"{package}/{a} started but not FOREGROUND; try next")
        # second unlock + first candidate
        self.unlock()
        out = self.shell(f"aa start -a {candidates[0]} -b {package}") or last
        if not _wait_fg(timeout_s=4.0):
            logger.warning(f"{package} still not FOREGROUND after launch attempts")
        return out

    def package_installed(self, package: str) -> bool:
        out = self.shell("bm dump -a")
        return package in out

    def is_package_foreground(self, package: str) -> bool:
        # True iff <package> mission is FOREGROUND (per-block, not whole dump).
        top = self.get_top_ability()
        if top and top.startswith(package + "/"):
            return True
        out = self.shell("aa dump -l")
        needle = f"bundle name [{package}]"
        for block in out.split("Mission ID"):
            if needle in block and "state #FOREGROUND" in block:
                return True
        return False
