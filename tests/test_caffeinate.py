"""Caffeinate command construction is correct per platform (plan §9)."""

from __future__ import annotations

from agentic_sdlc.caffeinate import CaffeinateManager, build_command


def test_macos_command() -> None:
    assert build_command(120, "Darwin") == ["caffeinate", "-i", "-m", "-t", "120"]


def test_linux_command_uses_systemd_inhibit() -> None:
    cmd = build_command(120, "Linux")
    assert cmd is not None
    assert cmd[0] == "systemd-inhibit"
    assert "--what=idle:sleep" in cmd


def test_unknown_platform_is_noop() -> None:
    assert build_command(120, "Windows") is None


def test_disabled_manager_holds_nothing() -> None:
    mgr = CaffeinateManager(enabled=False)
    mgr.heartbeat()
    assert not mgr.held
    mgr.release()  # idempotent
    assert not mgr.held
