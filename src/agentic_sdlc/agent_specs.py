"""Declarative sub-agent specifications (plan §5.2, §5.6).

Pure data: prompt, allowed tools and role (which routes to a model). The
orchestrator turns these into ``claude_agent_sdk.AgentDefinition`` objects, so
the SDK import stays isolated to ``orchestrator.py`` and these specs remain
importable and testable without the SDK installed. Specialization for SDLC is
encoded here (prompts + tight tool whitelists), not via any model training.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentic_sdlc.models import Role

_RETURN_CONTRACT = (
    "You MUST return ONLY the structured JSON result object you are given a"
    " schema for. Do not include prose outside it. Report commands you ran with"
    " their real exit codes; never claim success you did not verify by running a"
    " command. Correctness is decided by exit codes, not by your opinion."
)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: Role
    description: str
    prompt: str
    tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)


CODE_WRITER = AgentSpec(
    name="code-writer",
    role=Role.CODE_WRITER,
    description="Implements a feature to the project's standards with tests.",
    prompt=(
        "You are a senior engineer. Implement the requested change in small,"
        " atomic commits, writing tests alongside the code. Follow the project's"
        " CLAUDE.md standards exactly. Run the formatter, linter and type checker"
        " and fix what they report before finishing. " + _RETURN_CONTRACT
    ),
    tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    # Never let a builder edit gate config or force-push on the auto path.
    disallowed_tools=["Bash(git push --force*)", "Bash(rm -rf*)"],
)

TEST_SPECIALIST = AgentSpec(
    name="test-specialist",
    role=Role.TEST_SPECIALIST,
    description="Authors and runs unit/integration/contract/property tests.",
    prompt=(
        "You are a test engineer. Strengthen the test suite for the change:"
        " unit, integration (real dependencies via testcontainers where"
        " relevant), contract and property-based edge cases. Measure per-diff"
        " coverage. You may NEVER delete or weaken an existing test, add a skip,"
        " or lower a threshold to make a failure disappear. " + _RETURN_CONTRACT
    ),
    tools=["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    disallowed_tools=["Bash(rm -rf*)"],
)

REVIEWER = AgentSpec(
    name="reviewer",
    role=Role.REVIEWER_PRIMARY,
    description="Adversarial reviewer; tries to REFUTE the change.",
    prompt=(
        "You are an adversarial code reviewer. Your job is to find the strongest"
        " concrete reason this change is WRONG. Every rejection must cite a"
        " specific file, line and checkable claim — a rejection with no concrete"
        " finding will be discarded. Review only; you have no write access."
        " " + _RETURN_CONTRACT
    ),
    tools=["Read", "Bash", "Grep", "Glob"],
    disallowed_tools=["Write", "Edit"],
)

SCOUT = AgentSpec(
    name="scout",
    role=Role.SCOUT,
    description="Read-only search and log/format triage (cheap, fast).",
    prompt=(
        "You are a read-only scout. Locate code, scrape logs and summarize"
        " findings. You never modify files. " + _RETURN_CONTRACT
    ),
    tools=["Read", "Grep", "Glob", "Bash"],
    disallowed_tools=["Write", "Edit"],
)

# MVP team (plan §14): orchestrator + 3 sub-agents. Scout is included as the
# cheap read-only tier; security/infra are added when generalizing past MVP.
MVP_AGENTS: list[AgentSpec] = [CODE_WRITER, TEST_SPECIALIST, REVIEWER, SCOUT]
