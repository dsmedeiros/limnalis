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

## 2026-03-25 — Milestone 3C: BaselineNode validator relocation
**Event:** Invariant-aligned design change
**Invariant:** FIXTURE-001 (Fixture corpus is conformance authority)
**Change:** Removed `_moving_requires_tracked` Pydantic model validator from `BaselineNode` in `models/ast.py`. Moved validation to runtime `resolve_baseline` in `builtins.py`. Invalid baselines now normalize successfully and emit `baseline_mode_invalid` diagnostic at runtime.
**Justification:** Fixture corpus case A4 expects `kind=moving + evaluationMode=fixed` to normalize and produce a runtime diagnostic with state `"unresolved"`. The model-level validator blocked normalization entirely, contradicting the conformance authority.
**Approved by:** Orchestrator (corpus-driven, FIXTURE-001)

## 2026-03-25 — Milestone 3C complete: full conformance pass
**Event:** Milestone completion
**Milestone:** 3C — Full conformance pass, pipeline hardening, evaluator stabilization
**Results:** 16/16 corpus cases PASS, 231 tests passing, schema validation active
**Deliverables:** evaluate CLI, conformance report CLI, schema-validated outputs, diagnostic contract tests, determinism tests, status document at docs/milestone_3c_status.md
**Approved by:** Orchestrator (pending reviewer verdict on T3-T7)

## 2026-03-25 — Milestone 4: RC Hardening complete
**Event:** Milestone completion
**Milestone:** 4 — Release Candidate hardening, interface freeze, packaging, governance
**Results:** 308 tests passing (up from 236), 16/16 conformance PASS (strict mode), package version 0.2.2rc1
**Deliverables:**
- Public API freeze: `limnalis.api.{parser, normalizer, evaluator, conformance}`
- Version/manifest metadata: `limnalis.version`, CLI `--version` and `version` command
- Packaging: pyproject.toml cleaned, extras (dev/test/docs), classifiers, URLs
- CLI stabilization: consistent exit codes, `--json`, `--strict`, `--allowlist`, clean error handling
- Conformance hardening: stable JSON/markdown reports, strict mode, deviation allowlist, version metadata
- Hardening tests: 72 new tests (public API, determinism, property/Hypothesis, parser robustness, CLI, conformance reports)
- Documentation: README quickstart, architecture.md, 4 ADRs, compatibility/deviation policy, RC status report
**Reviews:** Standard reviewer PASS, Red team PASS_WITH_ADVISORIES (all advisories resolved)
**Red team fixes:** S1 (SPEC_VERSION single-sourced), S2 (allowlist error-priority), S3 (test quality)
**Approved by:** Orchestrator (reviewer + red team verdicts received)
