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

    def start_ability(self, package: str, ability: str = "EntryAbility") -> str:
        # PBT_KEA_ABILITY overrides; else try common system-app ability names.
        env_ab = os.environ.get("PBT_KEA_ABILITY")
        # ponytail: short fallback list; system HAPs rarely export EntryAbility
        candidates = []
        for a in (env_ab, ability, "MainAbility", f"{package}.phone", f"{package}.MainAbility"):
            if a and a not in candidates:
                candidates.append(a)
        last = ""
        for a in candidates:
            out = self.shell(f"aa start -a {a} -b {package}")
            last = out
            if "start ability successfully" in out.lower():
                return out
            if "failed to start" not in out.lower() and "error" not in out.lower():
                return out
        # wake + swipe once, retry first candidate
        self.shell("uitest uiInput keyEvent Power")
        self.shell("uitest uiInput swipe 540 2000 540 400 300")
        return self.shell(f"aa start -a {candidates[0]} -b {package}") or last

    def package_installed(self, package: str) -> bool:
        out = self.shell("bm dump -a")
        return package in out
