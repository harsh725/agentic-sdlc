"""Agentic SDLC — a specialized orchestrator for the software development lifecycle.

Public surface kept intentionally small. The deterministic spine (risk
classification, confidence scoring, reviewer voting, gate execution, the audit
ledger and the caffeinate manager) is importable without the Claude Agent SDK
installed, so it can be unit-tested and reasoned about in isolation. The
orchestrator that wires these into the Claude Agent SDK lives in
``agentic_sdlc.orchestrator`` and requires the optional ``orchestrator`` extra.
"""

from agentic_sdlc.confidence import ConfidenceInputs, compute_confidence, should_auto_merge
from agentic_sdlc.contracts import (
    NextAction,
    Phase,
    RiskLevel,
    Status,
    SubAgentResult,
)
from agentic_sdlc.models import PRICING, Role, estimate_cost_usd, route
from agentic_sdlc.risk_classifier import RiskClassifier, RiskVerdict

__version__ = "0.1.0"

__all__ = [
    "PRICING",
    "ConfidenceInputs",
    "NextAction",
    "Phase",
    "RiskClassifier",
    "RiskLevel",
    "RiskVerdict",
    "Role",
    "Status",
    "SubAgentResult",
    "__version__",
    "compute_confidence",
    "estimate_cost_usd",
    "route",
    "should_auto_merge",
]
