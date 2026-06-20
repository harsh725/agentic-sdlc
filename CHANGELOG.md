# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-06-20

### Added

- Initial MVP scaffold: a specialized SDLC orchestrator on the Claude Agent SDK.
- **Deterministic spine** (unit-tested, no SDK/API needed to run):
  - Fail-closed, versioned **risk classifier** (`risk_classifier/rules.yaml`).
  - **Confidence scoring** with an explicit weighted formula and the three-part
    auto-merge predicate (gates green AND confidence ≥ threshold AND risk LOW).
  - **Adversarial reviewer ensemble** with reliability-weighted voting and a
    concrete-finding requirement.
  - **Gate runner** branching on exit codes + anti-gaming regression invariants.
  - **Self-heal controller** with retry caps and no-progress/oscillation abort.
  - Append-only **audit ledger** (`runs/<id>/state.jsonl`).
  - Completion-aware **caffeinate manager** for unattended runs.
  - Role-based **model routing** across Opus 4.8 / Sonnet 4.6 / Haiku 4.5.
- `agentic-sdlc demo` CLI exercising the spine offline; `agentic-sdlc run` for
  live orchestration.
- Session hooks for caffeinated mode (`.claude/hooks/session-{start,end}.sh`).
- CI: `ruff format --check`, `ruff check`, `pytest`, and `gitleaks`.
- The full design document at `docs/PLAN.md` (supersedes the v0.1 plan; corrects
  every fabricated figure and adds the verification spine, adversarial review,
  caffeinated mode, and MVP-first roadmap).

[0.1.0]: https://github.com/harsh725/agentic-sdlc/releases/tag/v0.1.0
