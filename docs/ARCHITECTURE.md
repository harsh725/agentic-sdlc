# Architecture (overview)

This is a map of the code. The authoritative design rationale is in
[PLAN.md](PLAN.md); this file points to where each idea lives.

```
feature request
      │
      ▼
┌──────────────────────────────────────────────────────────────┐
│ Orchestrator (Opus 4.8) — durable 7-phase state machine       │  orchestrator.py
│   PLAN → CODE → VALIDATE → TEST → REVIEW → STAGING → MONITOR   │  contracts.py (Phase)
│   • delegates each phase to ONE role-tiered sub-agent          │  agent_specs.py
│   • branches only on structured JSON + gate exit codes         │  models.py (routing)
└───────────────┬──────────────────────────────────────────────┘
                │ each phase:
                ▼
   ┌───────────────────────────┐
   │ deterministic gates        │  gates.py + gates/gateset.yaml
   │  run real cmds, exit codes │
   └─────────────┬─────────────┘
                 │ green?
        ┌────────┴─────────┐
        │ no               │ yes
        ▼                  ▼
  self-heal loop      risk classify  ──  risk_classifier.py + rules.yaml
  (caps + no-progress) confidence score ─ confidence.py
   self_heal.py         reviewer vote  ── reviewers.py
        │                  │
        │           auto_merge?  (green AND confidence≥t AND risk=LOW)
        │            ┌──────┴───────┐
        ▼            ▼              ▼
   escalate → human  merge        escalate → human
        │            │              │
        └────────────┴──────────────┘
                     ▼
        append-only audit ledger  ──  ledger.py → runs/<id>/state.jsonl
```

Cross-cutting:

- **Caffeinate** (`caffeinate.py`, `.claude/hooks/`): a completion-aware wake
  heartbeat that releases on idle/escalation so a long human wait doesn't hold
  the machine awake.
- **Config** (`config.py`): conservative defaults — high auto-merge threshold,
  small budget cap, caffeinate opt-in.
- **Benchmarks** (`benchmarks/`): the eval substrate that calibrates the
  confidence threshold and reviewer-reliability weights from measured runs.

## Why these boundaries

The deterministic spine (everything except `orchestrator.py` and the SDK
delegation) has **no dependency on the Claude Agent SDK**. That keeps the
safety-critical logic — risk classification, the auto-merge predicate, gate
enforcement — plain, fast, and unit-testable, with the non-deterministic LLM
calls confined to a single, replaceable layer.
