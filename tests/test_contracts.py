"""Sub-agent contract parsing fails closed; phase progression is correct."""

from __future__ import annotations

from agentic_sdlc.contracts import (
    NextAction,
    Phase,
    Status,
    next_phase,
    parse_sub_agent_result,
)


def test_valid_payload_parses() -> None:
    r = parse_sub_agent_result(
        {
            "status": "ok",
            "phase": "CODE",
            "commands_run": [{"cmd": "pytest", "exit_code": 0}],
            "next_action": "advance",
        }
    )
    assert r.status is Status.OK
    assert r.all_commands_passed
    assert r.next_action is NextAction.ADVANCE


def test_garbage_fails_closed_to_escalate() -> None:
    r = parse_sub_agent_result("not json at all {")
    assert r.status is Status.ERROR
    assert r.phase is Phase.FAILED
    assert r.next_action is NextAction.ESCALATE


def test_non_string_non_dict_fails_closed() -> None:
    r = parse_sub_agent_result(12345)
    assert r.status is Status.ERROR
    assert r.next_action is NextAction.ESCALATE


def test_commands_not_all_passed() -> None:
    r = parse_sub_agent_result(
        {
            "status": "gate_failed",
            "phase": "TEST",
            "commands_run": [{"cmd": "pytest", "exit_code": 1}],
        }
    )
    assert not r.all_commands_passed


def test_phase_progression() -> None:
    assert next_phase(Phase.PLAN) is Phase.CODE
    assert next_phase(Phase.REVIEW) is Phase.STAGING
    assert next_phase(Phase.MONITOR) is Phase.DONE
    assert next_phase(Phase.DONE) is Phase.DONE
