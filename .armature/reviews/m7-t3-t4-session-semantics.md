# Review Verdict: m7-t3-t4-session-semantics

## Scope Compliance
- Declared scope (PRD `.taskmaster/docs/milestone-7-remediation-track-c.md`, Wave 2):
  - T3 `EvaluationStep.claim_subset` — scope `runtime/models.py`, `runtime/runner.py`, `conformance/runner.py`
  - T4 `EvaluationSession.shared_state` — scope `runtime/` (est. 80-150 LOC each)
- Files modified (`git diff HEAD --numstat`, working tree): exactly
  `src/limnalis/runtime/models.py` (+38/-2), `src/limnalis/runtime/runner.py` (+51/-3),
  `src/limnalis/runtime/builtins.py` (+183/-0), `src/limnalis/conformance/runner.py` (+9/-0),
  `tests/test_runtime_runner.py` (+415/-0), `tests/test_conformance.py` (+72/-0).
- `git status --porcelain`: these six files plus `src/limnalis/normalizer.py` and
  `tests/test_normalizer_claim_forms.py` (the parallel task, out of scope per instructions, not
  reviewed here).
- `fixtures/`, `schemas/`, `spec/`: `git diff HEAD` empty; `sha256sum` of both vendored corpus
  files unchanged. No out-of-scope modifications.
- `restricted` actions: `runtime/agents.md` lists `[cross-cutting-changes, model-changes]`;
  `.claude/agents/limnalis-runtime-impl.md`'s own scope note explicitly names `models.py` as an
  in-scope writable file within `src/limnalis/runtime/` and explicitly distinguishes it from the
  read-only `src/limnalis/models/` (the actual AST package) — so "model-changes" restricts edits to
  `src/limnalis/models/`, not `runtime/models.py`. No file under `src/limnalis/models/` was touched.
  No restricted action present.
- One process note (not a violation): `src/limnalis/conformance/runner.py` has no dedicated
  `agents.md`, and the generic `limnalis-runtime-impl.md` persona's own scope bullet lists only
  `src/limnalis/runtime/`. The PRD's own T3 line explicitly authorizes touching
  `conformance/runner.py`, and the change there is a minimal, narrowly-scoped 9-line addition
  consistent with that authorization, so this is not treated as scope creep — flagged only because
  no `conformance/agents.md` yet exists to formalize the authority (advisory below).

## 1. claim_subset semantics (spec §16.2 / §16.2.1)

`StepConfig.claim_subset: list[str] | None` (`runtime/models.py:46-64`, docstring cites §16.2/§16.2.1,
documents all three states — `None`, non-empty list, `[]` — and the unknown-id/laziness rules).

`run_step` (`runtime/runner.py:231-262`) computes `subset_ids` once and builds `all_claims` by
filtering `block.claims` against it; every later phase (2 refs, 5 license, 6 evidence view, 7
classify, 8 eval_expr, 9 support synthesis, 10 assemble, 11 resolution policy) iterates only
`all_claims` (or dicts derived from it) — confirmed by reading the full file (`runner.py:264-778`).
Excluded claims therefore never receive a classification, license, evidence view, truth core,
support, per-evaluator eval, or aggregate — they simply never enter any of those dicts.

Block folding exclusion is **not** implemented via synthetic AST nodes. `fold_block`
(`runtime/builtins.py:526-589`, unmodified by this diff — confirmed by `git diff` hunk list, no
hunk touches this function) computes `evaluable_claim_ids = [c.id for c in block.claims if c.id in
claim_classifications and claim_classifications[c.id].evaluable]` (`builtins.py:547-551`). Because
`claim_classifications` only contains entries for claims that were classified (i.e. `all_claims`),
an excluded claim id is simply absent from that dict and is excluded by the *existing* presence
check — the same mechanism already used for out-of-band classification failures — not by
constructing a filtered `ClaimBlockNode`. I grepped the diff and both `runtime/` and `conformance/`
source for `ClaimBlockNode(` construction: none exists outside test files. `ClaimBlockNode` still
carries its pre-existing `_min_claims` validator (`models/ast.py:585-590`, "must contain at least
one claim") — the exact validator the abandoned PR c964192 tripped by fabricating filtered block
copies — and this implementation never calls that constructor, so the validator is never at risk.
Empty evaluable set → `EvalNode(truth="N", reason="empty_block", ...)` (`builtins.py:554-560`,
pre-existing, unmodified), matching §16.6.9 "Empty evaluable set → N."

Live verification (`PYTHONPATH=src python3`, 4-scenario probe script in scratchpad):
- `claim_subset=None`: both `c1`/`c2` evaluated, block claims `['c1','c2']`, no `empty_block` reason.
- `claim_subset=[]`: `claim_results == []`, `block_results[0].claims == []`,
  `per_block_aggregates['blk1'] == N/empty_block`, `per_claim_classifications == {}` — confirms `[]`
  is distinct from `None` and literally zero-claims, not "no restriction."
- `claim_subset=["c1","ghost1","ghost2"]`: only `c1` in results; two deterministic warnings,
  `code=claim_subset_unknown_id`, `phase=claim`, `subject in {ghost1, ghost2}`, sorted.
- Two-block bundle, `claim_subset=["a1"]` (block `blk_b`'s only claim `b1` excluded): `blk_b` folds
  to `N/empty_block`; `blk_a` (not excluded) does not.
All four match the PRD's stated behavior exactly. The 8 `TestClaimSubset` tests
(`tests/test_runtime_runner.py:608-773`) assert the same surfaces (classification keys, aggregate
keys, license keys, block claim lists, diagnostic contents) plus the block-folding-influence case
(`test_excluded_claims_are_excluded_from_block_folding`, `:648-665`, a T-vs-F stub `eval_expr` that
proves the excluded claim's truth cannot leak into the block aggregate — a strong, non-trivial
assertion, not just presence/absence).

**Result: PASS.**

## 2. shared_state semantics (spec §16.6.3)

`SessionConfig.shared_state: bool = True` (`runtime/models.py:71-87`, docstring cites §16.6.3, states
both cache keys and that `on_reference`/`tracked` are unaffected).

`materialize_referenced_baselines` (`runtime/builtins.py:724-857`) is called once per (claim,
evaluator) pair inside phase 8's loop, immediately before `primitives.eval_expr`
(`runner.py:488-498`, comment cites §16.6.3/§16.2.1 explicitly). For `mode == "fixed"`: cache key is
`(session_id, baseline_id)` when `shared_state` else `(session_id, step_id, baseline_id)`
(`builtins.py:795-800`) — exact match to spec text. `mode == "tracked"`: `continue`s immediately,
never touches the cache or `machine_state.baseline_store` (`builtins.py:783-787`). Anything else
(only `on_reference` remains, per `BaselineMode = Literal["fixed","on_reference","tracked"]`,
`models/ast.py:17`) resolves unconditionally on every call, no cache (`builtins.py:833-848`).

Resolver-failure localization: both the `fixed` and `on_reference` branches wrap the resolver call in
`try/except Exception`, on failure append `{"severity":"warning","code":"baseline_resolution_error",
"phase":"baseline","subject":baseline_id,"message":str(exc)}` and set
`BaselineState(status="unresolved")`, then `continue` — no exception can escape
`materialize_referenced_baselines` (`builtins.py:816-826`, `:838-848`).

The cache lives in `services["__baseline_value_cache__"]` (`builtins.py:791-793`), not in
`MachineState` (which is rebuilt fresh every `run_step` call, `runner.py:227`) — this is the
mechanism by which the cache "survives" per-step `MachineState` resets while remaining scoped by the
session-qualified key, not by object identity.

Live verification (scratchpad probe, `PYTHONPATH=src python3`):
- `shared_state=True`, 2 steps, distinct step times: resolver called **1** time; both steps' stored
  baseline values are identical (`bl1@2026-03-06T09:00:00Z#1`), i.e. the cached-at-t0 value survives
  into the t1 step's separate `MachineState`.
- `shared_state=False`, same session shape: resolver called **2** times; step0/step1 values differ
  and match each step's own time.
- **Cross-session leakage probe**: `run_bundle` with two sessions (`session_alpha`, `session_beta`),
  both `shared_state=True`, both using the *same* `services` dict (as `run_bundle`/`run_session` do
  internally — confirmed by reading `runner.py:833`, `runner.py:896`) and the *same* step id and
  time: resolver called **2** times (once per session, not deduped), and
  `services["__baseline_value_cache__"].keys()` shows `[('session_alpha','bl1'),
  ('session_beta','bl1')]` — no cross-session value reuse, confirmed by direct key inspection, not
  just call counts.
- Resolver-failure probe: `run_step` with a resolver that raises `RuntimeError("boom")` returns a
  normal `StepResult` (no exception propagated to the caller); `baseline_store["bl1"].status ==
  "unresolved"`, `value is None`; diagnostics contain exactly one `baseline_resolution_error` with
  `phase="baseline"`, `subject="bl1"`, `message="boom"`.
- Also confirmed: `conformance/runner.py:806` builds a **fresh** `services = {}` per `run_case`
  invocation, so even generic/repeated session ids (e.g. `"default"`, `"s1"`) across different
  fixture cases cannot leak through a shared cache — the isolation holds at both the session-id-key
  level (within one bundle run) and the per-case-fresh-dict level (across fixture cases).

The 9 `TestSharedStateBaselineCaching` test functions (10 parametrized runs,
`tests/test_runtime_runner.py:776-934`) assert the same surfaces I probed independently: default
value, cache reuse/non-reuse, `on_reference` behavior under both flag values, `tracked`
non-materialization, per-session cache scoping, resolver-error localization, and the no-resolver
no-op. Assertions check concrete values (`step0_state.value ==
"bl1@2026-03-06T09:00:00Z"`), call counts, and diagnostic field contents — not merely absence of
exception.

**Result: PASS.**

## 3. RUNTIME-001 / RUNTIME-004 (phase ordering, 13 primitives, no 14th primitive)

`git diff HEAD -- src/limnalis/runtime/runner.py` hunk list: `@@-35,6+35,7@@` (one new import line
only), `@@-227,10+228,38@@`, `@@-456,6+485,17@@`, `@@-618,6+658,9@@`, `@@-722,11+765,16@@`. None of
these hunks touch the `PrimitiveSet` dataclass (`runner.py:70-90`, which sits between the untouched
import block and the first touched line 227) — its 13 fields
(`resolve_ref` ... `execute_transport`) are byte-identical to HEAD. `materialize_referenced_baselines`
is called directly as `_materialize_referenced_baselines(...)` (a plain function import, not a
`PrimitiveSet` field) and is not injectable/overridable through `PrimitiveSet` — confirmed it is not
one of the 13 fields.

Trace-event count: grepped every `trace.append(_trace(` call site in the current file (20 call
sites total, spread across mutually-exclusive try/except/else branches — phases 1/3/4 have 3
branches each, phase 2 has 2, phases 5-13 have 1 unconditional each = 20 sites but exactly 13 events
per execution). No new `_trace(` call was added for the new helper. Re-ran
`TestPhaseTraceOrder::test_trace_contains_all_13_phases` (`tests/test_runtime_runner.py:116-120`,
pre-existing, unmodified) directly: still asserts and still passes `len(result.trace) == 13`.

§16.2.1 laziness clause ("claim_subset does not itself force eager baseline materialization"):
`materialize_referenced_baselines` is called only inside the phase-8 per-claim loop over `all_claims`
(post-subset-filter, post-NoteExpr-bypass `continue`), so a baseline referenced solely by an excluded
claim is never passed to the resolver. Re-ran
`test_subset_does_not_force_eager_baseline_materialization`
(`tests/test_runtime_runner.py:739-773`) directly — passes — and independently reproduced it via my
own probe (Section 1 above / probe2 experiment): excluding the only referencing claim → 0 resolver
calls; the same bundle with no restriction → 1 resolver call at first evaluation. This is the
counting-resolver proof the task asked me to re-run; confirmed.

No-op when the resolver service is absent: `resolver = services.get("baseline_criterion_resolver");
if resolver is None: return diags` (`builtins.py:764-765`) is the first substantive line of the
function — an early return before touching `machine_state.baseline_store` or the cache. Grepped
`baseline_criterion_resolver` across `src/`: it appears **only** in the new helper's own
definition/docstring and in test-local service dicts — `conformance/runner.py` and
`plugins/fixtures.py` never set it, so every vendored conformance case takes this no-op path.
Reconfirmed by independently running `python -m limnalis conformance run` → 16/16 PASS (below).

**Result: PASS.**

## 4. Conformance threading

`_build_sessions_from_case` (`conformance/runner.py:533-575`) now passes
`claim_subset=step_env.get("claim_subset")` (`:552`) straight through from the fixture dict — this
correctly preserves all three states (missing key → `None`; explicit `null` → `None`; explicit
`[]` → `[]`) since `dict.get` returns exactly what's present. Verified directly with a synthetic
`SimpleNamespace` case with `claim_subset: ["c1","c3"]`, an omitted key, and `claim_subset: []` on
three different steps — `test_build_sessions_from_environment_preserves_step_claim_subset`
(`tests/test_conformance.py:386-411`) asserts all three states land correctly typed on `StepConfig`.

`shared_state = sess_env.get("shared_state"); if shared_state is None: shared_state = True`
(`conformance/runner.py:564-566`) reads the fixture value instead of ignoring it, defaulting to
`True` per spec when absent. `grep -n "shared_state" fixtures/limnalis_fixture_corpus_v0.2.2.yaml`
shows exactly one occurrence: A11's `shared_state: true` (line 852) — matching the PRD's specific
claim. Since `true` is also the implementation default, reading it is behaviorally a no-op, which
`test_vendored_a11_session_shared_state_is_read` (`tests/test_conformance.py:445-456`) asserts
directly (`sessions[0].shared_state is True`) and cross-references
`TestRegressions3A::test_a11_session_baseline_timing` (verified that test exists,
`tests/test_conformance.py:78-79`, and passes — see Section 7).

Vendored corpus byte-identity: `git diff HEAD -- fixtures/ schemas/ spec/` empty;
`sha256sum` of `limnalis_fixture_corpus_v0.2.2.{yaml,json}` computed and no modification detected
(git reports zero changes to those paths at all).

4 tests added to `TestConformanceSessionBuilding`
(`test_build_sessions_from_environment_preserves_step_claim_subset`,
`test_build_sessions_from_environment_reads_shared_state_false`,
`test_build_sessions_shared_state_defaults_true_when_absent`,
`test_vendored_a11_session_shared_state_is_read`) — matches the PRD's claimed count exactly.

**Result: PASS.**

## 5. MODEL invariants

`runtime/models.py`'s own `agents.md` (`runtime/agents.md:21`) states explicitly: "Runtime models use
standard Pydantic BaseModel (not LimnalisModel — these are not AST nodes)." `StepConfig` and
`SessionConfig` are plain `BaseModel` subclasses with no `model_config` override, consistent with
every other class in the file (none of the ~20 classes in `runtime/models.py` sets
`extra="forbid"`) — this is the pre-existing, deliberate convention for this file, not something T3/T4
changed. MODEL-001 ("AST node types must inherit LimnalisModel") and MODEL-002 ("AST models must use
extra='forbid'") are scoped to the AST package (`src/limnalis/models/`, whose `LimnalisModel` base
sets `extra="forbid"` — `src/limnalis/models/base.py:9-14`), which this diff does not touch at all
(confirmed via `git status`/`git diff`). Marking **N/A** rather than PASS, per the reviewer
persona's "be honest" principle — these invariants do not bind these two classes, and the PRD's
review-request framing conflated them with the unrelated AST-model invariants.

Field docstrings: `claim_subset` cites "(spec §16.2 / §16.2.1)" and documents `None`
vs. non-empty-list vs. `[]` semantics explicitly, including the deliberate rationale for treating
`[]` as zero-claims (`runtime/models.py:47-64`). `shared_state` cites "(spec §16.6.3)" and documents
both cache keys plus the on_reference/tracked carve-out (`runtime/models.py:72-87`). Both satisfy the
"field docstrings cite the spec sections" / "`[]` semantics documented" requirement.

**Result: N/A (not PASS) for MODEL-001/002** — out of these classes' governance scope by explicit,
pre-existing project convention; no violation because no such claim is made. Docstring/citation
requirement: **PASS**.

## 6. Tests

Counted directly via `grep -n "def test_"`:
- `TestClaimSubset` (`tests/test_runtime_runner.py:608-773`): **8** test functions — matches "8
  claim_subset" claim exactly.
- `TestSharedStateBaselineCaching` (`:776-934`): **9** test functions, one parametrized
  `@pytest.mark.parametrize("shared_state", [True, False])` (`:834`) → **10** actual pytest runs —
  matches "10 shared_state runs" claim exactly (the wording distinguishes "runs" from function
  defs, and it is accurate).
- `TestConformanceSessionBuilding` additions (`tests/test_conformance.py:386-456`): **4** test
  functions — matches "4 conformance threading" claim exactly.
- Total: 22 test functions / 23 pytest runs (22 + 1 extra parametrize run), consistent with the "22
  claimed" framing (function-def count).

Fixture-plugin-pack scope: `git diff HEAD -- src/limnalis/plugins/` is empty — no stub or fixture
binding was added there; all new resolvers (`_counting_context_resolver`, `failing_resolver`) and
helpers (`_baseline`, `_baseline_claim`, `_multi_block_bundle`, `_two_step_session`) are defined
locally in `tests/test_runtime_runner.py`, reusing the file's own pre-existing `_frame`/`_bundle`/
`_session`/`_env`/`_step` helpers rather than introducing new ones with overlapping purpose.

Assertion substance (spot-checked, not just "no exception"): call counts
(`assert counter["calls"] == 1`), exact string values
(`assert step0_state.value == "bl1@2026-03-06T09:00:00Z"`), diagnostic field contents
(`assert warnings[0]["subject"] == "ghost"`), and cross-run comparisons
(`assert step0_state.value != step1_state.value`). Every new test method/class carries a docstring
citing the specific spec subsection it verifies (§16.2, §16.2.1, §16.6.3, §16.6.9 all appear).

**Result: PASS.**

## 7. Live suite runs

- `python3 -m pytest tests/test_runtime_runner.py tests/test_runtime_primitives.py
  tests/test_conformance.py -v`: **208 passed**, 0 failed.
- `python3 -m pytest tests/ -v`: **988 passed**, 0 failed, 0 errors — matches the orchestrator's
  reported combined-tree count exactly, independently reproduced.
- `python3 -m limnalis conformance run`: **16 passed, 0 failed, 0 errors out of 16 cases**,
  independently reproduced.
- (Housekeeping, not requested but low-cost: ran `ruff check` on all six files and compared against
  the same six files at `HEAD` under the project's real `pyproject.toml` config — every one of the
  59 current findings has an identical (file, rule, message) match at `HEAD`; zero new findings.
  Three pre-existing `F401` unused-import warnings in `tests/test_runtime_runner.py` — `pytest`,
  `TimeCtxNode`, `MachineState` — are newly *resolved* because the added tests now legitimately use
  them. No lint regression; CI does not gate on lint/mypy in this repo (`.github/workflows/ci.yml`
  runs only `pytest`), so this is informational only.)

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 (Phase Ordering) | PASS | `PrimitiveSet` untouched (0 diff hunks in that region); 20 mutually-exclusive `_trace(` call sites still yield exactly 13 events/run; `test_trace_contains_all_13_phases` re-run, passes. New helper is invoked inside phase 8's existing scope, not a new phase. |
| RUNTIME-002 (Uniform Primitive Shape) | PASS / N/A for the new helper | All 13 existing primitives' signatures untouched. `materialize_referenced_baselines` is deliberately not a primitive (not in `PrimitiveSet`, not injectable) so the uniform `(output, machine_state, diagnostics)` shape does not apply to it by design — this is the correct choice, not a gap. |
| RUNTIME-003 (NoteExpr Bypass) | PASS | Phase-8/9 `continue` for non-evaluable claims happens before the new `materialize_referenced_baselines` call and before `eval_expr`/`synthesize_support`, unchanged control flow (`runner.py:481-485`). |
| RUNTIME-004 (PrimitiveSet Injection) | PASS | Still exactly 13 injectable fields; no 14th primitive registered. |
| FIXTURE-001 (Fixture Conformance Authority) | PASS | 16/16 vendored cases, independently reproduced; vendored corpus files byte-unchanged. |
| MODEL-001 / MODEL-002 | N/A | `runtime/models.py` classes are explicitly non-AST, non-`LimnalisModel` runtime models by pre-existing project convention (`runtime/agents.md:21`); `src/limnalis/models/` untouched. See Section 5. |
| SCHEMA-001 | N/A | No AST/schema surface touched by this diff. |

## Verdict: PASS_WITH_ADVISORIES

Every specific behavior claimed for T3 and T4 was independently reproduced by direct execution
(not just by reading the new tests), including the two hardest-to-get-right properties: (a)
claim_subset achieves block-folding exclusion purely through the pre-existing
presence-in-classifications contract with zero synthetic AST node construction anywhere in the
diff (the specific abandoned-PR pitfall named in the task), and (b) the shared_state cache is
provably scoped by session id under a shared `services` dict (not by dict-object separation), with
a live cross-session probe showing distinct cache entries and independent resolver invocations.
Resolver failures are fully localized (no exception escape, `unresolved` status,
`baseline_resolution_error` diagnostic) and the whole materialization path is a true no-op absent
the injected resolver service, which is why the fixture-backed conformance path (16/16, verified)
is unaffected. Phase count, primitive registry, and trace shape are all provably unchanged. Test
counts (8 / 10-runs / 4) match the claimed figures exactly, assertions are substantive, and every
new test cites its governing spec subsection. Full suite (988) and vendored conformance (16/16)
reproduced independently.

Advisories (not blocking):
1. **Baseline-local frame overlay is implemented but not directly asserted.**
   `materialize_referenced_baselines` builds `resolve_ctx` via
   `_merge_frame_facets(step_ctx.effective_frame, baseline_node.frame)` (`runtime/builtins.py:807-812`)
   per the §16.2.1 baseline-local frame rule, but no test captures/asserts the frame actually passed
   to the resolver (the counting resolver only inspects `effective_time`). Low risk — the merge
   helper itself is exercised elsewhere (`build_step_context` tests) — but a follow-up test that
   asserts on `resolve_ctx.effective_frame` (e.g. a baseline with a facet not present in the step's
   effective frame) would close this specific gap for T4.
2. **No `src/limnalis/conformance/agents.md`.** The cross-directory touch to
   `conformance/runner.py` is explicitly authorized by the PRD's T3 scope line, and is a minimal,
   correctly-scoped 9-line change, but there is no standing governance file establishing
   `conformance/`'s scope/authority/invariants the way `runtime/agents.md` and `tests/agents.md` do.
   Worth adding in a future governance-hygiene pass, not blocking for this changeset.
3. **`Diagnostic.phase` mixes int (existing generic `phase_error`/`stubbed_primitive` diagnostics)
   and spec-named string values** (existing `"baseline"`/`"license"`/`"transport"`, now joined by the
   new `"claim"` for `claim_subset_unknown_id`). This is a pre-existing inconsistency (not introduced
   by this diff — `sort_diagnostics`'s `_phase_key` already handled mixed types before this change,
   `runtime/models.py:377-382`, unmodified) and the new diagnostics correctly follow the
   spec-named-string convention already used for baseline/license/transport; flagged only as a
   reminder that the numeric-phase generic diagnostics remain spec-inconsistent (spec's `Diagnostic.
   phase` enum is `resolve | frame | baseline | license | evidence | claim | block | transport`, no
   integers) — out of scope for T3/T4 to fix.

## Rollback Recommendation: NO
No invariant violation, no regression, no scope violation. All claimed behaviors reproduced
independently via direct execution, not merely by reading the diff or trusting the new tests. The
three advisories are narrowly-scoped, non-blocking follow-ups (one test-coverage gap, one
governance-documentation gap, one pre-existing stylistic inconsistency noted for awareness).
