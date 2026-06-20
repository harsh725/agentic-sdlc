"""Canonical data contracts shared across the orchestrator and its sub-agents.

The ``SubAgentResult`` is the single JSON shape every delegated agent must
return (see plan §5.3). The orchestrator branches on the *deterministic* fields
(``commands_run[].exit_code``, ``test_results``) and on values **it** computes
(``confidence``, ``risk_flags``) — never on a sub-agent's self-assessment of its
own quality. A malformed or missing-field response is treated as ``escalate``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Phase(str, Enum):
    """The seven SDLC phases plus terminal/exception states."""

    PLAN = "PLAN"
    CODE = "CODE"
    VALIDATE = "VALIDATE"
    TEST = "TEST"
    REVIEW = "REVIEW"
    STAGING = "STAGING"
    MONITOR = "MONITOR"
    DONE = "DONE"
    ESCALATED = "ESCALATED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    FAILED = "FAILED"


# Ordered happy-path progression. Terminal/exception states are not part of it.
PHASE_ORDER: tuple[Phase, ...] = (
    Phase.PLAN,
    Phase.CODE,
    Phase.VALIDATE,
    Phase.TEST,
    Phase.REVIEW,
    Phase.STAGING,
    Phase.MONITOR,
    Phase.DONE,
)


def next_phase(current: Phase) -> Phase:
    """Return the next happy-path phase, or DONE if already at the end."""
    if current not in PHASE_ORDER:
        raise ValueError(f"{current} is not an advanceable phase")
    idx = PHASE_ORDER.index(current)
    return PHASE_ORDER[min(idx + 1, len(PHASE_ORDER) - 1)]


class Status(str, Enum):
    OK = "ok"
    GATE_FAILED = "gate_failed"
    NEEDS_INPUT = "needs_input"
    ERROR = "error"


class NextAction(str, Enum):
    ADVANCE = "advance"
    RETRY = "retry"
    ESCALATE = "escalate"
    HALT = "halt"


class RiskLevel(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"


class CommandRun(BaseModel):
    cmd: str
    exit_code: int


class TestResults(BaseModel):
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


class CoverageDelta(BaseModel):
    diff_pct: float = 0.0
    total_pct: float = 0.0


class SubAgentResult(BaseModel):
    """The mandatory return shape for every delegated sub-agent."""

    status: Status
    phase: Phase
    files_changed: list[str] = Field(default_factory=list)
    commands_run: list[CommandRun] = Field(default_factory=list)
    test_results: TestResults = Field(default_factory=TestResults)
    coverage_delta: CoverageDelta = Field(default_factory=CoverageDelta)
    # Advisory only when self-reported; the orchestrator recomputes the
    # authoritative values from objective signals before acting.
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    summary: str = ""
    next_action: NextAction = NextAction.ESCALATE

    @property
    def all_commands_passed(self) -> bool:
        return all(c.exit_code == 0 for c in self.commands_run)


def parse_sub_agent_result(payload: object) -> SubAgentResult:
    """Validate an untrusted sub-agent payload.

    Fail closed: anything that does not parse cleanly becomes an ``error`` +
    ``escalate`` result rather than being trusted or silently advanced.
    """
    try:
        if isinstance(payload, SubAgentResult):
            return payload
        if isinstance(payload, dict):
            return SubAgentResult.model_validate(payload)
        return SubAgentResult.model_validate_json(str(payload))
    except Exception as exc:  # noqa: BLE001 - intentional fail-closed boundary
        return SubAgentResult(
            status=Status.ERROR,
            phase=Phase.FAILED,
            summary=f"unparseable sub-agent response: {exc}",
            next_action=NextAction.ESCALATE,
        )
