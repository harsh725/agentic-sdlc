"""Model IDs, verified pricing, and role-based routing (plan §5.4, §8.1).

Pricing captured 2026-06-20 from platform.claude.com, in USD per million tokens
(input / output). Output is 5x input on every model, so the model chosen for
output-heavy steps dominates the bill far more than any compression tool.
Re-verify before relying on these for billing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Concrete model IDs — never use version-less "opus"/"haiku" (plan Appendix A3).
OPUS = "claude-opus-4-8"
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5"
FABLE = "claude-fable-5"


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float
    context_tokens: int


# Source: platform.claude.com pricing, captured 2026-06-20. Illustrative for
# planning; treat client-side cost estimates as approximate, not billing-grade.
PRICING: dict[str, Price] = {
    OPUS: Price(input=5.0, output=25.0, context_tokens=1_000_000),
    SONNET: Price(input=3.0, output=15.0, context_tokens=1_000_000),
    HAIKU: Price(input=1.0, output=5.0, context_tokens=200_000),
    FABLE: Price(input=10.0, output=50.0, context_tokens=1_000_000),
}


class Role(str, Enum):
    """Sub-agent roles, routed to a model by cost/capability fit."""

    ORCHESTRATOR = "orchestrator"
    CODE_WRITER = "code_writer"
    CODE_WRITER_HARD = "code_writer_hard"
    TEST_SPECIALIST = "test_specialist"
    TEST_AGGREGATION = "test_aggregation"
    SECURITY_AUDITOR = "security_auditor"
    SECURITY_AUDITOR_HARD = "security_auditor_hard"
    REVIEWER_PRIMARY = "reviewer_primary"
    REVIEWER_SECONDARY = "reviewer_secondary"
    INFRA = "infra"
    SCOUT = "scout"


# Role -> model. Haiku only for read-only / mechanical work; builders, reviewers
# and security never run on Haiku (cheap-but-wrong code raises the retry tax).
_ROUTING: dict[Role, str] = {
    Role.ORCHESTRATOR: OPUS,
    Role.CODE_WRITER: SONNET,
    Role.CODE_WRITER_HARD: OPUS,
    Role.TEST_SPECIALIST: SONNET,
    Role.TEST_AGGREGATION: HAIKU,
    Role.SECURITY_AUDITOR: SONNET,
    Role.SECURITY_AUDITOR_HARD: OPUS,
    Role.REVIEWER_PRIMARY: OPUS,
    Role.REVIEWER_SECONDARY: SONNET,
    Role.INFRA: SONNET,
    Role.SCOUT: HAIKU,
}


def route(role: Role) -> str:
    """Return the model ID for a role."""
    return _ROUTING[role]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Illustrative cost estimate for a single model call."""
    price = PRICING[model]
    return (input_tokens / 1_000_000) * price.input + (output_tokens / 1_000_000) * price.output


def cache_read_cost_usd(model: str, cached_input_tokens: int) -> float:
    """Cached-prefix read is 0.1x input (90% off the cached portion only)."""
    return (cached_input_tokens / 1_000_000) * PRICING[model].input * 0.1
