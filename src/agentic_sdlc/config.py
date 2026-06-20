"""Runtime configuration for an orchestrator run.

Defaults are deliberately conservative (high auto-merge threshold, small budget,
caffeinate off) so the system *earns* autonomy as it accumulates measured
evidence in ``benchmarks/``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agentic_sdlc.confidence import DEFAULT_AUTO_MERGE_THRESHOLD
from agentic_sdlc.gates import GateSpec

DEFAULT_GATESET_PATH = Path("gates/gateset.yaml")


@dataclass
class OrchestratorConfig:
    repo: Path = field(default_factory=lambda: Path("."))
    feature_id: str = "feature"
    # Budget rails (plan §8.4). Per-feature USD cap handed to the SDK.
    max_budget_usd: float = 5.0
    max_turns: int = 60
    # Auto-merge gate (plan §6.2, §7).
    auto_merge_threshold: float = DEFAULT_AUTO_MERGE_THRESHOLD
    coverage_target_pct: float = 80.0
    # Self-heal (plan §6.5).
    max_retries: int = 3
    # Caffeinated mode (plan §9). Opt-in; off by default.
    caffeinate: bool = field(default_factory=lambda: os.environ.get("CAFFEINATE_MODE") == "1")
    # Reviewer ensemble size (plan §6.3).
    reviewer_n: int = 3

    def load_gateset(self, path: Path | str = DEFAULT_GATESET_PATH) -> list[GateSpec]:
        """Load the deterministic gate commands for this stack."""
        data = yaml.safe_load(Path(path).read_text()) or {}
        return [
            GateSpec(
                name=g["name"],
                cmd=g["cmd"],
                blocking=g.get("blocking", True),
            )
            for g in data.get("gates", [])
        ]
