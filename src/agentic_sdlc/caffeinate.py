"""Completion-aware caffeinated mode (plan §9).

Keeps the machine awake only while the orchestrator is actively working. The
wake assertion is a *heartbeat*, not a permanent hold: while working the
orchestrator re-arms a short assertion; when the work queue drains or it blocks
on a human escalation it stops re-arming and the machine sleeps on its own — even
though the process stays alive to receive the answer.

This module builds and manages the commands; it never sleeps the machine itself,
so the command-construction logic is unit-testable on any platform.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass

# Heartbeat window. A short ``-t`` so a crash/stall releases within ~2x this.
HEARTBEAT_SECONDS = 120

# Idle timeouts used by the shell session-start hook, mirrored here for parity.
AC_TIMEOUT_SECONDS = 14_400  # 4h on AC power
BATTERY_TIMEOUT_SECONDS = 1_800  # 30m on battery


def on_ac_power() -> bool:
    """Best-effort AC detection on macOS via ``pmset -g ps``."""
    if platform.system() != "Darwin" or shutil.which("pmset") is None:
        return True  # assume AC on non-Mac / when undetectable
    try:
        out = subprocess.run(  # noqa: S603,S607 - fixed, trusted command
            ["pmset", "-g", "ps"], capture_output=True, text=True, check=False
        ).stdout
        return "AC Power" in out
    except OSError:
        return True


def build_command(seconds: int, system: str | None = None) -> list[str] | None:
    """Construct the platform wake-inhibit command for a short assertion.

    macOS: ``caffeinate -i -m -t <sec>`` (system + disk idle sleep; display sleep
    deliberately allowed on a headless run). Linux: ``systemd-inhibit``. Other
    platforms return None (no-op + caller warns).
    """
    system = system or platform.system()
    if system == "Darwin":
        return ["caffeinate", "-i", "-m", "-t", str(seconds)]
    if system == "Linux":
        return [
            "systemd-inhibit",
            "--what=idle:sleep",
            "--who=agentic-sdlc",
            "--mode=block",
            "sleep",
            str(seconds),
        ]
    return None


@dataclass
class CaffeinateManager:
    """Manages the heartbeat wake assertion for one orchestrator run."""

    enabled: bool = False
    heartbeat_seconds: int = HEARTBEAT_SECONDS
    _proc: subprocess.Popen | None = None
    _held: bool = False

    @property
    def held(self) -> bool:
        return self._held

    def heartbeat(self) -> None:
        """Re-arm the short assertion. Call on a timer while actively working."""
        if not self.enabled:
            return
        self.release()  # replace any prior short assertion
        cmd = build_command(self.heartbeat_seconds)
        if cmd is None:
            return
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - fixed, trusted command
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._held = True
        except OSError:
            self._held = False

    def release(self) -> None:
        """Drop the wake assertion (machine may sleep). Idempotent."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None
        self._held = False

    def __enter__(self) -> CaffeinateManager:
        if self.enabled:
            self.heartbeat()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
