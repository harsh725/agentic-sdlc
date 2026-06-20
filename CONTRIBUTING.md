# Contributing

Thanks for your interest. This project is MVP-stage; the priority is proving the
pipeline on one stack with measured evidence before broadening scope (see
[docs/PLAN.md §14](docs/PLAN.md#14-mvp-first-roadmap)).

## Ground rules

- **Code is the oracle.** New gates must branch on a real exit code, not an LLM
  judgement. New "quality" claims must be backed by a runnable check.
- **No fabricated numbers.** Every quantitative claim in docs is either cited
  with a capture date or labelled *illustrative — validate via `benchmarks/`*.
- **The risk classifier and gate config are safety-critical.** Changes to
  `risk_classifier/`, `gates/`, `.github/workflows/`, or `CODEOWNERS` always
  require human review — they are deliberately on the escalate path.

## Local development

```bash
pip install -e '.[dev]'
ruff format .        # auto-format
ruff check .         # lint
pytest               # unit tests (no API key required)
agentic-sdlc demo    # exercise the deterministic spine offline
```

All of `ruff format --check`, `ruff check`, and `pytest` must pass before a PR
merges; CI enforces them (`.github/workflows/ci.yml`).

## Commit style

Atomic commits, imperative mood, `type(scope): description`
(`feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `security`, `perf`).
Never commit secrets; `gitleaks` gates the diff.

## Adding a stack

Don't add stack #2 until ≥3 real features have shipped through the gates on
stack #1 with token/time recorded in `benchmarks/`. When you do, add a
`gateset.<stack>.yaml` and stack-specific gate commands; do not weaken the
deterministic-gate guarantees to accommodate a harder target (notably mobile —
see the plan's mobile caveat).
