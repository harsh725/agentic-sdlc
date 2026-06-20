# Agentic SDLC — project memory

This repo IS the agentic-SDLC framework: a specialized orchestrator that drives
features through deterministic gates and auto-merges low-risk changes. Read
`docs/PLAN.md` for the full design before making non-trivial changes.

## Commands

```bash
pip install -e '.[dev]'   # spine + dev tools (no API key)
ruff format . && ruff check . && pytest
agentic-sdlc demo         # exercise the deterministic spine offline
```

## Conventions

- **Code is the oracle.** Gates branch on real exit codes; never gate on an LLM's
  self-assessment.
- **Pin concrete model IDs** (`claude-opus-4-8`, `claude-sonnet-4-6`,
  `claude-haiku-4-5`); never version-less "opus"/"haiku".
- **No fabricated numbers** in docs — cite with a capture date or label
  *illustrative*.
- Python: type hints on signatures, no bare `except`, `ruff` clean, line length
  100. Pydantic v2.
- The deterministic spine must not import the Claude Agent SDK; keep SDK use in
  `orchestrator.py` only.

## Safety-critical (always human-reviewed, never on the auto-merge path)

`risk_classifier/`, `gates/`, `.github/workflows/`, `CODEOWNERS`,
`src/agentic_sdlc/risk_classifier.py`, `src/agentic_sdlc/confidence.py`.

## Commit format

`type(scope): description`; atomic; imperative. Never commit secrets
(`gitleaks` gates it).
