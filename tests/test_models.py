"""Model routing and illustrative cost math (plan §5.4, §8.1)."""

from __future__ import annotations

from agentic_sdlc.models import HAIKU, OPUS, SONNET, Role, estimate_cost_usd, route


def test_scouts_route_to_haiku() -> None:
    assert route(Role.SCOUT) == HAIKU
    assert route(Role.TEST_AGGREGATION) == HAIKU


def test_builders_never_haiku() -> None:
    assert route(Role.CODE_WRITER) == SONNET
    assert route(Role.SECURITY_AUDITOR) == SONNET


def test_orchestrator_and_primary_reviewer_on_opus() -> None:
    assert route(Role.ORCHESTRATOR) == OPUS
    assert route(Role.REVIEWER_PRIMARY) == OPUS


def test_output_is_five_x_input_in_cost() -> None:
    # 1M output on Opus ($25) vs 1M input ($5) -> 5x.
    assert estimate_cost_usd(OPUS, 1_000_000, 0) == 5.0
    assert estimate_cost_usd(OPUS, 0, 1_000_000) == 25.0


def test_illustrative_feature_cost() -> None:
    # 300K in + 30K out on Opus ~= $2.25 (plan §8.5).
    cost = estimate_cost_usd(OPUS, 300_000, 30_000)
    assert abs(cost - 2.25) < 1e-9
