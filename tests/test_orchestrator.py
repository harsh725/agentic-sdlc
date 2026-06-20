"""Orchestrator state machine, exercised with a stubbed sub-agent (no SDK).

Verifies the phase walk actually reaches REVIEW (the loop bug regression), the
conservative default escalates, a lowered threshold auto-merges, and a red gate
escalates after the self-heal cap.
"""

from __future__ import annotations

import asyncio

from agentic_sdlc.agent_specs import AgentSpec
from agentic_sdlc.config import OrchestratorConfig
from agentic_sdlc.contracts import CoverageDelta, NextAction, Phase, Status, SubAgentResult
from agentic_sdlc.gates import GateResult, GateRunReport
from agentic_sdlc.orchestrator import MVP_PHASES, Orchestrator

NOW = "2026-06-20T00:00:00Z"


class _StubOrch(Orchestrator):
    """Replaces the SDK delegation and gate execution with deterministic stubs."""

    def __init__(self, config: OrchestratorConfig, *, gates_pass: bool = True) -> None:
        super().__init__(config)
        self._gates_pass = gates_pass

    async def _delegate(self, spec: AgentSpec, task: str) -> SubAgentResult:
        return SubAgentResult(
            status=Status.OK,
            phase=Phase.CODE,
            files_changed=["src/widgets/button.py"],  # low risk
            coverage_delta=CoverageDelta(diff_pct=95.0, total_pct=85.0),
            next_action=NextAction.ADVANCE,
            summary="stub change",
        )

    def _run_phase_gates(self, phase: Phase) -> GateRunReport:
        if self._gates_pass:
            return GateRunReport([])  # empty -> all blocking passed
        return GateRunReport([GateResult("unit", exit_code=1, blocking=True)])


def _run(orch: Orchestrator) -> Phase:
    return asyncio.run(orch.run_feature("do the thing", now=NOW))


def test_walks_all_mvp_phases_then_escalates_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    orch = _StubOrch(OrchestratorConfig(feature_id="t1"))
    terminal = _run(orch)
    # Conservative default: REVIEW confidence < 0.90 (no mutation data) -> escalate.
    assert terminal is Phase.ESCALATED
    transitions = [e.from_state for e in orch.ledger.read() if e.event == "transition"]
    # Crucially, TEST and REVIEW were actually reached (the loop-bug regression).
    assert [p.value for p in MVP_PHASES] == ["PLAN", "CODE", "TEST", "REVIEW"]
    assert "TEST" in transitions
    assert "REVIEW" in transitions


def test_auto_merges_when_threshold_lowered(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    orch = _StubOrch(OrchestratorConfig(feature_id="t2", auto_merge_threshold=0.5))
    assert _run(orch) is Phase.DONE


def test_red_gate_escalates_after_self_heal_cap(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    orch = _StubOrch(OrchestratorConfig(feature_id="t3", max_retries=2), gates_pass=False)
    assert _run(orch) is Phase.ESCALATED


def test_resume_index_from_ledger(tmp_path, monkeypatch) -> None:
    from agentic_sdlc.ledger import LedgerEvent

    monkeypatch.chdir(tmp_path)
    orch = _StubOrch(OrchestratorConfig(feature_id="t4"))
    # Simulate a prior run that committed through CODE (next phase = TEST).
    orch.ledger.record(
        LedgerEvent(ts=NOW, feature_id="t4", event="transition", from_state="CODE", to_state="TEST")
    )
    assert orch._resume_index() == MVP_PHASES.index(Phase.TEST)
