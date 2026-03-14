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
