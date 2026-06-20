"""The SDLC orchestrator — a durable state machine on the Claude Agent SDK.

Plan §5. The orchestrator *drives* the phases itself and branches only on
structured JSON returns and deterministic exit codes — it does not hand control
to an LLM to decide what happens next. Each phase delegates to a single
role-tiered sub-agent via the SDK; the deterministic spine (gates, risk,
confidence, ledger, self-heal) decides advance / retry / escalate.

Requires the optional ``orchestrator`` extra (``pip install 'agentic-sdlc[orchestrator]'``).
The Claude Agent SDK is imported lazily so the rest of the package stays usable
without it.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_sdlc.agent_specs import CODE_WRITER, REVIEWER, TEST_SPECIALIST, AgentSpec
from agentic_sdlc.caffeinate import CaffeinateManager
from agentic_sdlc.confidence import ConfidenceInputs, compute_confidence, should_auto_merge
from agentic_sdlc.config import OrchestratorConfig
from agentic_sdlc.contracts import (
    NextAction,
    Phase,
    Status,
    SubAgentResult,
    next_phase,
    parse_sub_agent_result,
)
from agentic_sdlc.gates import run_gateset
from agentic_sdlc.ledger import Ledger, LedgerEvent
from agentic_sdlc.models import route
from agentic_sdlc.risk_classifier import RiskClassifier
from agentic_sdlc.self_heal import HealController

ORCHESTRATOR_SYSTEM_PROMPT = (
    "You are the Agentic SDLC orchestrator. You coordinate specialized"
    " sub-agents through PLAN, CODE, VALIDATE, TEST, REVIEW, STAGING and MONITOR."
    " You never assert correctness yourself — correctness is decided by gate exit"
    " codes. You delegate; you do not write feature code directly."
)


@dataclass
class PhaseOutcome:
    phase: Phase
    result: SubAgentResult
    gates_passed: bool
    confidence: float
    risk_high: bool
    decision: str  # advance | retry | escalate | auto_merge | halt
    cost_usd: float = 0.0


class Orchestrator:
    """Drives one feature through the SDLC state machine."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.ledger = Ledger(config.feature_id)
        self.risk = RiskClassifier.from_yaml()
        self.caffeine = CaffeinateManager(enabled=config.caffeinate)
        self._spent_usd = 0.0

    # -- public API --------------------------------------------------------

    async def run_feature(self, request: str, *, now: str) -> Phase:
        """Run the full pipeline for a feature request. Returns the terminal phase.

        ``now`` is an ISO timestamp supplied by the caller (keeps the core pure
        and resume-safe). Resumes from the last committed phase if the ledger
        already has progress.
        """
        resume = self.ledger.last_committed_phase()
        phase = Phase[resume] if resume else Phase.PLAN
        with self.caffeine:
            while phase in (Phase.CODE, Phase.TEST, Phase.REVIEW) or phase is Phase.PLAN:
                self.caffeine.heartbeat()
                outcome = await self._run_phase(phase, request, now=now)
                self._commit(phase, outcome, now=now)
                if outcome.decision in ("escalate", "halt"):
                    return Phase.ESCALATED if outcome.decision == "escalate" else Phase.FAILED
                if self._spent_usd >= self.config.max_budget_usd:
                    return Phase.BUDGET_EXHAUSTED
                if phase is Phase.REVIEW and outcome.decision == "auto_merge":
                    return Phase.DONE
                phase = next_phase(phase)
            return Phase.DONE

    # -- phase execution ---------------------------------------------------

    async def _run_phase(self, phase: Phase, request: str, *, now: str) -> PhaseOutcome:
        spec = self._spec_for(phase)
        heal = HealController(max_retries=self.config.max_retries)

        while True:
            result = await self._delegate(spec, self._task_for(phase, request))
            gate_report = self._run_phase_gates(phase)
            gates_passed = gate_report.all_blocking_passed and result.all_commands_passed

            verdict = self.risk.classify(result.files_changed)
            confidence = self._score_confidence(result, gates_passed)

            if gates_passed:
                if phase is Phase.REVIEW:
                    auto = should_auto_merge(
                        gates_green=True,
                        confidence=confidence,
                        risk_level=verdict.level,
                        threshold=self.config.auto_merge_threshold,
                    )
                    decision = "auto_merge" if auto else "escalate"
                else:
                    decision = "advance"
                return PhaseOutcome(phase, result, True, confidence, verdict.is_high, decision)

            # Gate failed -> self-heal, with anti-gaming + no-progress guards.
            failing = {f.name for f in gate_report.failures()}
            cont, reason = heal.register_attempt(result.summary, failing)
            self.ledger.record(
                LedgerEvent(
                    ts=now,
                    feature_id=self.config.feature_id,
                    event="gate",
                    agent=spec.name,
                    gate=",".join(failing) or "unknown",
                    exit_code=1,
                    decision="retry" if cont else "escalate",
                    reason=reason,
                )
            )
            if not cont:
                return PhaseOutcome(phase, result, False, confidence, verdict.is_high, "escalate")

    def _run_phase_gates(self, phase: Phase):  # noqa: ANN202 - GateRunReport
        # Only the phases that have local exit-code gates run them; PLAN/REVIEW
        # gate on AC/structured signals rather than a build command.
        if phase in (Phase.CODE, Phase.VALIDATE, Phase.TEST):
            return run_gateset(self.config.load_gateset(), cwd=self.config.repo)
        return run_gateset([], cwd=self.config.repo)

    def _score_confidence(self, result: SubAgentResult, gates_passed: bool) -> float:
        inputs = ConfidenceInputs(
            reviewer_approve=self.config.reviewer_n if gates_passed else 0,
            reviewer_refute=0 if gates_passed else self.config.reviewer_n,
            reviewer_n=self.config.reviewer_n,
            diff_coverage_pct=result.coverage_delta.diff_pct,
            coverage_target_pct=self.config.coverage_target_pct,
            blast_lines=len(result.files_changed) * 20,
        )
        return compute_confidence(inputs)

    # -- SDK delegation (lazy import) --------------------------------------

    async def _delegate(self, spec: AgentSpec, task: str) -> SubAgentResult:
        """Run one sub-agent via the Claude Agent SDK and parse its JSON result."""
        try:
            from claude_agent_sdk import (  # type: ignore[import-not-found]
                ClaudeAgentOptions,
                ResultMessage,
                query,
            )
        except ImportError as exc:  # pragma: no cover - requires optional extra
            raise RuntimeError(
                "The Claude Agent SDK is required to run the orchestrator. "
                "Install it with: pip install 'agentic-sdlc[orchestrator]'"
            ) from exc

        options = ClaudeAgentOptions(
            system_prompt=spec.prompt,
            model=route(spec.role),
            allowed_tools=spec.tools,
            disallowed_tools=spec.disallowed_tools,
            cwd=str(self.config.repo),
            max_turns=self.config.max_turns,
            max_budget_usd=max(self.config.max_budget_usd - self._spent_usd, 0.01),
            enable_file_checkpointing=True,
            permission_mode="acceptEdits",
            output_format={
                "type": "json_schema",
                "schema": SubAgentResult.model_json_schema(),
            },
        )

        structured: object | None = None
        async for message in query(prompt=task, options=options):
            if isinstance(message, ResultMessage):
                self._spent_usd += float(getattr(message, "total_cost_usd", 0.0) or 0.0)
                structured = getattr(message, "structured_output", None)

        if structured is None:
            return SubAgentResult(
                status=Status.ERROR,
                phase=spec_phase_default,
                summary="sub-agent returned no structured output",
                next_action=NextAction.ESCALATE,
            )
        return parse_sub_agent_result(structured)

    # -- helpers -----------------------------------------------------------

    def _spec_for(self, phase: Phase) -> AgentSpec:
        return {
            Phase.PLAN: CODE_WRITER,
            Phase.CODE: CODE_WRITER,
            Phase.TEST: TEST_SPECIALIST,
            Phase.REVIEW: REVIEWER,
        }.get(phase, CODE_WRITER)

    def _task_for(self, phase: Phase, request: str) -> str:
        return f"[{phase.value}] Feature request:\n{request}"

    def _commit(self, phase: Phase, outcome: PhaseOutcome, *, now: str) -> None:
        self.ledger.record(
            LedgerEvent(
                ts=now,
                feature_id=self.config.feature_id,
                event="transition",
                from_state=phase.value,
                to_state=(
                    Phase.DONE.value
                    if outcome.decision == "auto_merge"
                    else next_phase(phase).value
                    if outcome.decision == "advance"
                    else Phase.ESCALATED.value
                ),
                trigger=outcome.decision,
                agent=self._spec_for(phase).name,
                model=route(self._spec_for(phase).role),
                cost_usd=outcome.cost_usd,
                confidence=outcome.confidence,
                risk="HIGH" if outcome.risk_high else "LOW",
                decision=outcome.decision,
            )
        )


# Default phase used when a malformed sub-agent response can't name its phase.
spec_phase_default = Phase.FAILED
