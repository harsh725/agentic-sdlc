# Agentic SDLC

A custom **orchestrator agent**, specialized (not fine-tuned) for the software
development lifecycle. It drives a feature from a one-line request through code →
test → security → review → staging → monitoring, **auto-merging low-risk changes
with no human in the loop** and escalating only the changes that genuinely need a
human.

> **Status: MVP (single stack).** The deterministic spine — risk classification,
> confidence scoring, reviewer voting, gate execution, the audit ledger, and the
> caffeinate manager — is implemented and unit-tested. The Claude Agent SDK
> orchestrator that wires them together is in place and runs on top of it.

It rests on three load-bearing ideas:

1. **Code is the oracle, never the LLM.** Every gate keys off a *real exit code*
   (compiler, tests, linter, scanner), enforced by hooks and GitHub required
   checks. An LLM's opinion of its own work is never a correctness signal.
2. **Adversarial multi-agent review + confidence scoring + a deterministic risk
   classifier** replace the human reviewer for the majority of changes — while
   *guaranteeing* a human sees anything touching auth, data, money, or infra.
3. **The real ROI is engineer time, not tokens.** API spend is a rounding error
   (~$30–220/year, illustrative) next to the engineer-hours it returns.

It runs **unattended and overnight** in [caffeinated mode](docs/PLAN.md#9-caffeinated-mode):
the laptop stays awake only while the orchestrator is actively working and sleeps
the moment the work queue drains.

## Quickstart

```bash
# Install the deterministic spine + dev tools (no API key needed)
pip install -e '.[dev]'

# See the gates -> risk -> confidence -> auto-merge decision pipeline, offline:
agentic-sdlc demo

# Run the test suite (this is what CI runs green)
pytest

# To run the live orchestrator you also need the Claude Agent SDK + an API key:
pip install -e '.[orchestrator]'
export ANTHROPIC_API_KEY=...
agentic-sdlc run "Add a /health endpoint that returns build SHA" --repo ../my-app --feature health-endpoint
```

`agentic-sdlc demo` prints the real decision logic with no network calls — the
risk classifier escalating an auth change, the reviewer ensemble discarding a
no-evidence rejection, the confidence score, and the three-part auto-merge gate.

## How it works

| Layer | What it does | Where |
|---|---|---|
| **Orchestrator** | Durable 7-phase state machine; delegates to role-tiered sub-agents; branches only on structured JSON + exit codes | `src/agentic_sdlc/orchestrator.py` |
| **Risk classifier** | Deterministic, fail-closed; forces auth/PII/migration/IaC/payment/public-API → human | `src/agentic_sdlc/risk_classifier.py`, `risk_classifier/rules.yaml` |
| **Confidence** | Normalized weighted score from reviewer agreement, coverage, mutation, blast radius, defect history | `src/agentic_sdlc/confidence.py` |
| **Reviewers** | N heterogeneous adversarial reviewers; reliability-weighted vote; concrete-finding requirement | `src/agentic_sdlc/reviewers.py`, `reviewers/*.md` |
| **Gates** | Run real commands, branch on exit codes; anti-gaming invariants | `src/agentic_sdlc/gates.py`, `gates/gateset.yaml` |
| **Self-heal** | Bounded retries + no-progress/oscillation abort | `src/agentic_sdlc/self_heal.py` |
| **Ledger** | Append-only per-feature audit trail → `runs/<id>/state.jsonl` | `src/agentic_sdlc/ledger.py` |
| **Caffeinate** | Completion-aware wake-lock (heartbeat releases on idle/escalation) | `src/agentic_sdlc/caffeinate.py`, `.claude/hooks/` |
| **Model routing** | Opus 4.8 orchestration, Sonnet 4.6 builders/reviewers, Haiku 4.5 scouts | `src/agentic_sdlc/models.py` |

The auto-merge decision (no human) requires **all three**:

```
auto_merge  ⟺  all gates GREEN  AND  confidence ≥ threshold  AND  risk == LOW
```

Anything else escalates to a human (fail closed).

## The plan

The full design — corrected facts, architecture, the foolproof quality engine,
token economics, caffeinated mode, security for unattended runs, and the
MVP-first roadmap — lives in **[docs/PLAN.md](docs/PLAN.md)**. Read it before
extending the system.

## Contributing & license

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed (see [LICENSE](LICENSE)).
Built with [Claude Code](https://claude.com/claude-code).
