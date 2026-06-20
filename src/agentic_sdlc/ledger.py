"""Append-only run/audit ledger (plan §5.3, §11).

Every phase transition and every agent step is recorded as one JSON line under
``runs/<feature-id>/state.jsonl``. This is the durable source of truth for which
phase passed (crash-resume reads it), the audit trail that makes every
auto-merge decision root-causable, and the raw data that populates
``benchmarks/``. Timestamps are injected by the caller so the module stays pure
and testable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class LedgerEvent:
    ts: str
    feature_id: str
    event: str  # "transition" | "agent_step" | "decision" | "gate"
    from_state: str | None = None
    to_state: str | None = None
    trigger: str | None = None
    agent: str | None = None
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    gate: str | None = None
    exit_code: int | None = None
    confidence: float | None = None
    risk: str | None = None
    decision: str | None = None
    reason: str | None = None
    extra: dict = field(default_factory=dict)


class Ledger:
    """Append-only JSONL writer for a single feature run."""

    def __init__(self, feature_id: str, runs_dir: Path | str = "runs") -> None:
        self.feature_id = feature_id
        self.dir = Path(runs_dir) / feature_id
        self.path = self.dir / "state.jsonl"

    def record(self, event: LedgerEvent) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), separators=(",", ":")) + "\n")

    def read(self) -> list[LedgerEvent]:
        if not self.path.exists():
            return []
        events: list[LedgerEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(LedgerEvent(**json.loads(line)))
        return events

    def last_committed_phase(self) -> str | None:
        """The ``to_state`` of the most recent successful transition (resume point)."""
        last: str | None = None
        for ev in self.read():
            if ev.event == "transition" and ev.to_state:
                last = ev.to_state
        return last

    def totals(self) -> dict[str, float]:
        tin = tout = 0
        cost = 0.0
        for ev in self.read():
            tin += ev.tokens_in
            tout += ev.tokens_out
            cost += ev.cost_usd
        return {"tokens_in": tin, "tokens_out": tout, "cost_usd": round(cost, 6)}
