"""Local stdio MCP server exposing the deterministic spine to Claude Code.

Runs as a subprocess of an interactive Claude Code session, so it works with
your subscription login — **no API key**. Register it at user scope:

    claude mcp add agentic-sdlc --scope user -- \
        /path/to/.venv/bin/agentic-sdlc-mcp

Then the tools below are callable in any project as
``mcp__agentic-sdlc__<tool>``.

Requires the optional ``mcp`` extra: ``pip install 'agentic-sdlc[mcp]'``.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from agentic_sdlc import service

mcp = FastMCP("agentic-sdlc")


@mcp.tool()
def classify_risk(files: list[str], diff_text: str = "") -> dict[str, Any]:
    """Classify a change as LOW or HIGH risk from its changed file paths (and
    optional diff text). Deterministic and fail-closed: auth, crypto, DB
    migrations, IaC, payments and public-API changes are forced to HIGH, meaning
    they must get human review regardless of confidence."""
    return service.classify_risk(files, diff_text)


@mcp.tool()
def run_gates(repo: str = ".", gateset_path: str = "") -> dict[str, Any]:
    """Run the deterministic gate commands (format/lint/types/tests/secrets) for a
    repo and report each exit code. 'all_blocking_passed' is the ground-truth
    'is it green' signal. Returns found=false if the repo has no gates/gateset.yaml."""
    return service.run_gates(repo, gateset_path or None)


@mcp.tool()
def score_confidence(
    reviewer_approve: int = 0,
    reviewer_refute: int = 0,
    reviewer_n: int = 0,
    diff_coverage_pct: float = 0.0,
    mutation_total: int = 0,
    mutation_survived: int = 0,
    blast_lines: int = 0,
) -> dict[str, Any]:
    """Compute the normalized confidence score (0..1) from objective signals:
    reviewer agreement, per-diff coverage, mutation score, and blast radius."""
    return service.score_confidence(
        reviewer_approve=reviewer_approve,
        reviewer_refute=reviewer_refute,
        reviewer_n=reviewer_n,
        diff_coverage_pct=diff_coverage_pct,
        mutation_total=mutation_total,
        mutation_survived=mutation_survived,
        blast_lines=blast_lines,
    )


@mcp.tool()
def decide_merge(
    files: list[str],
    repo: str = ".",
    gateset_path: str = "",
    diff_text: str = "",
    reviewer_approve: int = 0,
    reviewer_refute: int = 0,
    reviewer_n: int = 0,
    diff_coverage_pct: float = 0.0,
    mutation_total: int = 0,
    mutation_survived: int = 0,
) -> dict[str, Any]:
    """The auto-merge verdict for a change: returns decision='auto_merge' only if
    gates are green AND confidence >= threshold AND risk is LOW; otherwise
    'escalate' (a human must review), with the reasons why. Fail-closed."""
    return service.decide_merge(
        files,
        repo=repo,
        gateset_path=gateset_path or None,
        diff_text=diff_text,
        reviewer_approve=reviewer_approve,
        reviewer_refute=reviewer_refute,
        reviewer_n=reviewer_n,
        diff_coverage_pct=diff_coverage_pct,
        mutation_total=mutation_total,
        mutation_survived=mutation_survived,
    )


def main() -> None:
    """Entry point for the ``agentic-sdlc-mcp`` console script (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
