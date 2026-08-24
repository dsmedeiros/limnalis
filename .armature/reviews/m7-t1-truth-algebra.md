# Review Verdict: m7-t1-truth-algebra

**Task:** Milestone 7, T1 — True Belnap–Dunn pair algebra in the runtime
**PRD:** `.taskmaster/docs/milestone-7-remediation-track-c.md` (T1, Wave 1)
**Reviewer scope note:** A concurrent implementer (T2) is modifying `src/limnalis/normalizer.py` in the same working tree. This review covers **only** the T1 changeset — `src/limnalis/runtime/builtins.py` and `tests/test_runtime_primitives.py` — obtained via `git diff -- src/limnalis/runtime/builtins.py tests/test_runtime_primitives.py`. T2's normalizer/test_operator_precedence work is not reviewed, judged, or reported on here.

## Scope Compliance
- Declared scope (T1, per PRD): `src/limnalis/runtime/`, est. 80-150 LOC.
- `agents.md` scope of record: `src/limnalis/runtime` (`src/limnalis/runtime/agents.md`), `enforced-by: tests/test_runtime_primitives.py, tests/test_runtime_runner.py`, `restricted: [cross-cutting-changes, model-changes]`.
- Files touched by T1's diff:
  - `src/limnalis/runtime/builtins.py` — +48/-23 (confirmed via `git diff --numstat`, matches implementer's reported figures exactly)
  - `tests/test_runtime_primitives.py` — +112/-0 (confirmed; zero deletions, consistent with "none rewritten/deleted")
- Out-of-scope modifications: **none**. `builtins.py` contains exactly two contiguous diff hunks, both confined to lines 1423-1518 (the truth-ordering block and its two call sites in `_eval_logical_expr`). No model changes (`src/limnalis/models/` untouched), no cross-cutting changes (single file, single self-contained algebra swap).
- Concurrent-work guard: `git status --porcelain=v1 --untracked-files=all` shows exactly three modified files repo-wide: `src/limnalis/normalizer.py` (T2, not reviewed here), `src/limnalis/runtime/builtins.py` (T1), `tests/test_runtime_primitives.py` (T1). No untracked files. **T1's own diff does not touch `normalizer.py` or any file beyond its declared two** — verified directly from the pathspec-scoped diff (2 files, 6 hunks total, all accounted for below).

## VERIFY 1 — Algebra correctness

Read `_TRUTH_TO_PAIR`/`_PAIR_TO_TRUTH`/`_truth_and`/`_truth_or`/`_truth_flip` (builtins.py:1429-1476) and the updated `_eval_logical_expr` dispatch (builtins.py:1500-1514), and hand-derived the induced tables from the pair formulas.

- **Pair encoding** (line 1429-1434): `T=(1,0), F=(0,1), B=(1,1), N=(0,0)` — matches spec §4 (`spec/Limnalis-v0.2.2.md:612`) exactly.
- **`_truth_and`** computes `t = min(truth-bits)`, `f = max(falsity-bits)` over all operands at once (not a pairwise fold) — this is `X∧Y=(tX∧tY, fX∨fY)` generalized n-arily via bitwise-AND-as-min / bitwise-OR-as-max, which is mathematically exact for 0/1 bits and correct for n-ary because min/max are associative+commutative.
- **`_truth_or`** computes `t = max`, `f = min` — the dual, matching `X∨Y=(tX∨tY, fX∧fY)`.
- **`_truth_flip`** swaps the pair `(t,f) -> (f,t)` — matches `¬X=(fX,tX)`.
- Hand-derived the full 4x4 AND table from these formulas and it matches the spec's table (`spec/Limnalis-v0.2.2.md:614-639`) cell-for-cell, including the two flagship entries: **B∧N=(min(1,0), max(1,0))=(0,1)=F**, **N∧B=F** (symmetric). Also derived the OR table: **B∨N=(max(1,0), min(1,0))=(1,0)=T**, **F∨N=(max(0,0), min(1,0))=(0,0)=N**. Negation fixpoints confirmed: **¬B=(1,1)=B**, **¬N=(0,0)=N**.
- **implies/iff derivation** (lines 1506-1514): `implies` = `¬X∨Y` and `iff` = `(X→Y)∧(Y→X)`, coded exactly as the formula reads, using the already-verified `_truth_flip`/`_truth_or`/`_truth_and`. Hand-checked **B→N**: ¬B=B (fixpoint), B∨N=T, so **B→N=T** — matches the spec-cited verification target. Hand-checked **B↔N**: B→N=T, N→B=¬N∨B=N∨B=T, T∧T=T, so **B↔N=T** — matches.
- **Test-table cross-check**: the 16-entry dict literals in `test_conjunction_full_table_matches_spec` and `test_disjunction_full_table_matches_spec` were compared cell-by-cell against my independent hand derivation above — identical in all 32 cells (16 AND + 16 OR).
- **Empty-input / n-ary fold**: `_truth_and([])`/`_truth_or([])` both return `"N"`, explicitly preserving prior behavior (comment says so; confirmed against the deleted `_truth_min`/`_truth_max`, which had the same `if not values: return "N"` guard). This path is provably unreachable through the validated AST construction path — `LogicalExprNode._enforce_arity` (`src/limnalis/models/ast.py:249-255`) rejects `and`/`or`/`implies`/`iff` with fewer than 2 args and `not` with anything but exactly 1, so `eval_expr` can never invoke these helpers with an empty list in practice. The n-ary case (>2 args) is computed by a single min/max over all operands, not a pairwise reduce, so it is order-independent and deterministic by construction (confirmed empirically too: `test_nary_connectives_fold_pairwise` hand-checks `and(T,B,N)=F`, `or(F,N,B)=T`, both of which I re-derived independently and match). Spec §4 defines only the binary connectives; it is silent on nullary identity elements, so "N" is a reasonable, non-regressive placeholder rather than a spec-mandated value — noted as a minor forward-looking observation below, not a defect.

**Finding: algebra is correct and matches spec §4 exactly, including every verification target listed in the review brief (B∧N=F, N∧B=F, B∨N=T, F∨N=N, ¬B=B, ¬N=N, B→N=T, B↔N=T, full 16-entry conjunction table).**

## VERIFY 2 — Scope guards held

`builtins.py`'s diff contains exactly two hunks (`git diff` hunk headers: `@@ -1423,32 +1423,57 @@` and `@@ -1473,20 +1498,20 @@`), both confined to the 1423-1518 line range. Confirmed each named scope guard sits well outside that range and is absent from the diff:

| Symbol | Location (post-diff) | In diff? |
|---|---|---|
| `_TRUTH_JOIN` | builtins.py:335 | No |
| `_aggregate_truth` | builtins.py:355 | No |
| `_fold_block_truth` | builtins.py:500 | No |
| `_SEVERITY_ORDER` (licensing, F>B>N>T) | builtins.py:1088 | No |
| `_SUMMARY_SEVERITY_ORDER` | builtins.py:3037 | No |

Also grepped the full repo for `_TRUTH_ORDER`, `_ORDER_TO_TRUTH`, `_truth_min`, `_truth_max` (the removed symbols) — zero remaining references anywhere, confirming a clean rename with no dangling call sites. Grepped for the new symbol names (`_truth_and`, `_truth_or`, `_truth_flip`, `_TRUTH_TO_PAIR`, `_PAIR_TO_TRUTH`) — all definitions and all call sites are inside the two diff hunks; no duplicate definitions or stray external callers. `apply_resolution_policy`, `execute_transport`, `build_evidence_view`, `assemble_eval`, and the resolution-policy machinery are untouched (no hunks anywhere near them). Spec §4 itself corroborates the guard's rationale: "This is the strict connective. Softer summary behavior requires a declared policy" (`spec/Limnalis-v0.2.2.md:640-642`) — i.e., the spec itself treats the logical connectives and the summary/severity policies as distinct, so leaving `_SEVERITY_ORDER`/`_SUMMARY_SEVERITY_ORDER` untouched is not just scope discipline but spec-correct.

**Finding: all named scope guards are byte-unchanged, verified structurally via diff-hunk boundaries, not just by inspection.**

## VERIFY 3 — Tests

- 9 new tests in `TestEvalLogicalConnectives` (`tests/test_runtime_primitives.py`), confirmed by running `pytest tests/test_runtime_primitives.py -v -k TestEvalLogicalConnectives` -> **9 passed, 110 deselected**.
- **End-to-end, not tautological**: the test helper `_eval_logical` drives the public `eval_expr` primitive (builtins.py:1645) with a real `ClaimNode(kind="logical", expr=LogicalExprNode(...))` whose leaves are `DeclarationExprNode` nodes. `DeclarationExpr` resolution (`_eval_declaration_expr`, builtins.py:1525-1539, pre-existing/untouched code) maps `declaredAs` to a `TruthValue` via a literal dict, independent of the AND/OR machinery under test. So the tests exercise the real dispatch path (`eval_expr -> _eval_expr_inner -> _eval_logical_expr -> _truth_and/_truth_or/_truth_flip`) end-to-end, and the expected tables in the tests are hard-coded literal dicts, not derived from the implementation being tested — not circular.
- Verified all model constructions are valid against current schemas (`DeclarationExprNode(term=SymbolTermNode(value=...), declaredAs=...)`, `LogicalExprNode(op=..., args=[...])`, `ClaimNode(kind="logical", ...)` all match field definitions in `src/limnalis/models/ast.py`, including the `_enforce_arity` validator's arity requirements for each op used).
- All 9 docstrings cite "spec §4" explicitly, and all of the PRD's named verification targets (B∧N=F, N∧B=F, B∨N=T, ¬B=B, ¬N=N, B→N=T, B↔N=T, full 16-entry table) are covered by name in a dedicated test.
- **No existing test deleted or weakened**: `tests/test_runtime_primitives.py` diff has 0 deletions (`git diff --numstat`: `112  0`). Grepped no helper/class name collisions between the new additions (`_decl_expr`, `_eval_logical`, `TestEvalLogicalConnectives`) and the pre-existing file content (checked against `git show HEAD:tests/test_runtime_primitives.py`) — no shadowing.
- **Spot-grep for prior assertions on old linearized values**: searched the pre-T1 (`HEAD`) version of the test file for any `LogicalExprNode`/`op="and"|"or"|"implies"|"iff"` usage. Found exactly one: `_logical_claim()` (old line 109-117), which builds an `op="and"` claim over `PredicateExprNode` leaves (evaluator-bound, not declared) and is used exactly once, in `TestClassifyClaim`, purely to assert `expr_kind == "LogicalExpr"` classification — it never asserts a computed truth value. Repo-wide grep for `LogicalExprNode`/`op="and"` etc. across all of `tests/` shows matches only in `test_runtime_primitives.py`. All other `B`/`N`-valued assertions found in the old test file belong to `_aggregate_truth`/`fold_block`/`EvalNode`-construction tests — the separate, untouched paraconsistent-union/block-fold algebra, not the AND/OR connective evaluator. **Confirms the implementer's claim: no prior test asserted the old linearized AND/OR/IMPLIES/IFF results.**

## VERIFY 4 — Runs

Ran the specified command (`PYTHONPATH=src python -m pytest tests/test_runtime_primitives.py tests/test_property.py tests/test_conformance.py`), scoped exactly to the files named in the review brief plus conformance, per instructions (not the full suite, since T2's concurrent normalizer work is in-flight in the same tree):

```
172 passed in 5.98s
```
(41 from test_conformance.py, 12 from test_property.py, 119 from test_runtime_primitives.py — includes the 9 new connective tests.) No failures, no errors, no skips. `test_conformance_run_default_runs_full_corpus` (test_conformance.py) explicitly asserts `"16 passed" in captured.out` and passed, confirming the vendored 16/16 conformance result held.

As an additional, cheap corroborating check (not required by the brief but directly relevant to RUNTIME-001/003, which name `test_runtime_runner.py` as their enforcement mechanism): also ran `tests/test_runtime_runner.py` -> **26 passed**. `runner.py` is not in T1's diff at all, so this is a pure non-regression confirmation.

**Strong corroborating finding on FIXTURE-001**: the vendored fixture corpus (`fixtures/limnalis_fixture_corpus_v0.2.2.yaml`, case A3 "logical composition") contains claim `c6: (b AND n)` with pinned expected `truth: F` (lines 434-441), where `b` and `n` are bound to `B` and `N` respectively (per sibling claims `c4: b -> B` and `c2: n -> N` in the same fixture). This is exactly the flagship B∧N=F case, baked into the *immutable, authoritative* vendored corpus. To confirm this was a real, previously-failing conformance gap (not just a spec-purity nicety), I simulated the deleted old algebra in an isolated, throwaway Python process using the exact `_TRUTH_ORDER`/`_truth_min` definitions read from the diff's deletion lines — **no repository file was read, modified, or reverted for this check**, consistent with the reviewer's read-only mandate. The simulation shows old `_truth_min(["B","N"])` = `"N"`, which contradicts the vendored pinned expected value of `"F"`. This strongly indicates `test_a3_logical_composition` (and thus the "16 passed" vendored gate) was failing prior to this fix, and T1's change is what makes it pass now. This is a substantive, verifiable regression fix against the project's own conformance authority, not a cosmetic refactor.

## VERIFY 5 — Invariants

- No changes under `fixtures/`, `schemas/`, `spec/` attributable to T1 (or to anything else — `git status` shows zero changes anywhere in those trees).
- RUNTIME-001 (Phase Ordering): `runner.py` is not part of T1's diff; `test_runtime_runner.py` (26/26) confirms no regression. PASS/N-A.
- RUNTIME-002 (Uniform Primitive Shape): `eval_expr`'s public signature (`(claim, evaluator_id, step_ctx, machine_state, services) -> (TruthCore, MachineState, Diagnostics)`, builtins.py:1645) is unchanged; only its internal `LogicalExpr` computation was swapped. PASS.
- RUNTIME-003 (NoteExpr Bypass): `_eval_expr_inner`'s NoteExpr branch (builtins.py:1630-1635) is outside both diff hunks, untouched. PASS/N-A.
- RUNTIME-004 (PrimitiveSet Injection): `primitives.py` not touched by this diff. N/A.
- FIXTURE-001: vendored corpus byte-unchanged (no fixtures/ diff) and the "16 passed" conformance gate is green post-change, with the added evidence above that it was specifically this algebra that was previously wrong for a vendored case. PASS.
- NORM-001: not implicated — T1's own diff contains zero changes to `normalizer.py` (confirmed via the pathspec-scoped diff). The working tree's `normalizer.py` modification belongs to the concurrent T2 task and is out of scope for this review per instructions.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | PASS | `runner.py` untouched by T1; `test_runtime_runner.py` 26/26 green. |
| RUNTIME-002 | PASS | `eval_expr` signature/shape unchanged; only internal LogicalExpr computation replaced. |
| RUNTIME-003 | PASS | NoteExpr bypass branch outside both diff hunks. |
| RUNTIME-004 | N/A | `primitives.py` not touched. |
| FIXTURE-001 | PASS | Vendored corpus byte-unchanged; "16 passed" gate green; vendored case A3/c6 (B∧N) independently confirmed to require this exact fix. |
| NORM-001 | N/A | Not implicated — no normalizer changes in T1's diff (normalizer.py belongs to concurrent T2, out of scope here). |
| Scope (`restricted: cross-cutting-changes, model-changes`) | PASS | Single-file, single-concern change; no model files touched. |

## Test Results
- `tests/test_runtime_primitives.py` + `tests/test_property.py` + `tests/test_conformance.py`: **172 passed, 0 failed** (scoped run per review brief).
- `tests/test_runtime_runner.py` (bonus, RUNTIME-001/003 corroboration): **26 passed**.
- Note: full-suite run was intentionally not performed, since T2's concurrent, uncommitted `normalizer.py`/`test_operator_precedence.py` work is in-flight in the same tree and any churn there is out of this review's scope, per instructions.

## Advisories (non-blocking)
1. Nullary/empty-input identity for `_truth_and`/`_truth_or` (`"N"` for both) is inherited from the pre-existing code, not spec-derived (spec §4 defines only the binary connectives) — currently unreachable in production because `LogicalExprNode._enforce_arity` forbids empty arg lists at construction time. No action needed for T1; worth a one-line spec citation or comment if a future task (e.g., T5 extension-corpus work) ever exercises nullary folds directly.

## Verdict: PASS

## Required Changes
None.

## Rollback Recommendation: NO
The changeset is a correct, narrowly-scoped, well-tested fix that closes a real, independently-confirmed conformance gap against the vendored fixture corpus. No invariant violations, no scope-guard breaches, no out-of-scope files touched, all specified test runs green.
