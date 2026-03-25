# Armature Governance Journal

This is an append-only log of governance-relevant events. It is gitignored and survives code-level rollbacks, providing institutional memory across sessions.

**Do not edit or delete entries.** Only append new entries below.

---

## 2026-03-14 — RUNTIME-001 invariant text update (12 → 13 phases)
**Event:** Invariant text change
**Invariant:** RUNTIME-001 (Phase Ordering)
**Change:** Updated phase count from 12 to 13 across registry.yaml, invariants.md, and runtime/agents.md
**Justification:** Milestone 3B spec requires compose_license integration as phase 5 in the runner pipeline. The phase ordering invariant's intent (strict ascending order) is preserved; only the count changed.
**Approved by:** Orchestrator (spec-driven change)

## 2026-03-14 — Orchestrator protocol violation: self-implemented PR review fixes
**Event:** Protocol violation (self-corrected)
**Rule violated:** "MUST NOT write application code" — orchestrator directly edited builtins.py, models.py, runner.py, compare.py instead of delegating to implementer agents
**Root cause:** Multi-fix scenario (6 issues from PR review) was treated as "quick patches" rather than delegated work. No triage/partition step was performed.
**Remediation:** Added "Multi-Fix and Bug-Fix Delegation" section to orchestrator persona with explicit protocol for batch-fix scenarios. Reinforces that even one-line fixes must be delegated.
**Approved by:** Human (escalation)
