# Review Verdict: m7-remediation-cycle1

**Reviewer:** reviewer (standard, non-adversarial)
**Scope of review:** combined IMPL-α + IMPL-β remediation changeset, full uncommitted working
tree over HEAD `fc02fe6` (17 files, +2359/-161).
**Context read first:** `.armature/reviews/m7-redteam.md` (prior FAIL verdict), current
`src/limnalis/conformance/agents.md` (updated gate/comparator rules).
**Method:** static diff review against `.armature/invariants/registry.yaml` and each touched
`agents.md`, plus independent dynamic verification — hand-computed pair-algebra discriminators
executed directly against the runtime, a separate `git worktree` at `fc02fe6` used for
before/after diffing (CLI report, deep model dump, ruff), and the full test suite run twice.

## Scope Compliance

- Declared scopes touched: `src/limnalis/agents.md` (normalizer.py, plugins/fixtures.py),
  `src/limnalis/runtime/agents.md` (builtins.py, runner.py), `src/limnalis/conformance/agents.md`
  (compare.py, runner.py, agents.md itself), plus `fixtures/limnalis_extension_corpus_v0.1.*`
  (project-authored, not vendored), `docs/paradox_gallery.md`, and 7 test files.
- Files modified: docs/paradox_gallery.md; fixtures/limnalis_extension_corpus_v0.1.{yaml,json};
  src/limnalis/conformance/{agents.md,compare.py,runner.py}; src/limnalis/normalizer.py;
  src/limnalis/plugins/fixtures.py; src/limnalis/runtime/{builtins.py,runner.py};
  tests/test_{conformance,conformance_comparison,extension_corpus,normalizer_claim_forms,
  operator_precedence,runtime_primitives,runtime_runner}.py.
- Out-of-scope modifications: none. `src/limnalis/models/`, `schemas/`, `grammar/limnalis.lark`,
  `spec/`, and the vendored `fixtures/limnalis_fixture_corpus_v0.2.2.*` are untouched (confirmed
  by `git diff --stat` and SHA-256 comparison against `fc02fe6` — see Standard Gates below). No
  `restricted` action (`cross-cutting-changes`, `model-changes`, `schema-migration`,
  `vendored-corpus-changes`) from any touched `agents.md` appears in the diff.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| NORM-001 | PASS | Full suite (incl. determinism tests) green twice; `test_shielded_scanner_forms_are_deterministic`, `test_extension_results_are_deterministic` pass. |
| NORM-002 | PASS (scope of this diff) | New associativity/shielding decisions each carry inline rationale + corpus `ast_decisions`. Pre-existing MEDIUM-4 gap (unclamped delimiter depth) is untouched, out of scope for this cycle, not worsened. |
| FIXTURE-001 | PASS | Vendored corpus files SHA-256-identical to `fc02fe6`; 16/16 vendored cases pass on the echo path with a byte-identical `conformance report --format json`. |
| SCHEMA-001 | PASS | 0 AST/result-schema errors across both corpora (independently re-run); D7's new left-nested tree shape schema-validates explicitly. |
| RUNTIME-001/002/003 | PASS | Untouched by this diff except the fixed connectives/reasons; full suite (which pins 13-phase ordering and NoteExpr bypass) is green. |
| MODEL-001/002 | N/A | `src/limnalis/models/` untouched; `EvalNode.reason` is a pre-existing field, not a new one. |

## Findings, by task priority

### 1. CRITICAL-1 closure (both halves) — VERIFIED, closed

**(a) Normalizer tree shape.** `src/limnalis/normalizer.py:140` (`_NON_ASSOCIATIVE_OPS =
frozenset({"implies", "iff"})`) and the branch at `normalizer.py:1217` build LEFT-NESTED binary
`LogicalExprNode`s for `implies`/`iff` while AND/OR (line ~1222) stay flat n-ary. The EBNF
citations in the code (`normalizer.py:126-136`, `:1199-1210`) — `ImplExpr ::= OrExpr { ImplOp
OrExpr }` line 1236, `IffExpr ::= ImplExpr { IffOp ImplExpr }` line 1235 — are byte-accurate
against `spec/Limnalis-v0.2.2-reconstructed.md:1235-1236` (checked directly). The associativity
reading (left-to-right EBNF repetition → left fold) is the standard operator-precedence-parsing
convention and is the only interpretation available since the spec prose has no explicit
associativity statement. The same decision is recorded in
`fixtures/limnalis_extension_corpus_v0.1.yaml` `ast_decisions` ("IMPLIES/IFF chains are
left-associative binary trees"). `tests/test_operator_precedence.py::TestRepeatedOperatorAssociativity`
now covers 3-operand, 4-operand, mixed-spelling (`->`/`IMPLIES` sharing a chain), and
precedence-interaction cases.

**(b) Runtime fold.** `src/limnalis/runtime/builtins.py:1823` (`implies`) and `:1829` (`iff`)
now fold `sub_truths` left-associatively pairwise instead of indexing `[0]`/`[1]`. I executed the
task's mandated discriminators directly against `eval_expr` (not just read the code):

```
iff(T,F,F)        = T   (mandated: T)
implies(T,B)      = B   (mandated: B)
implies(T,B,N)    = T   (mandated: T)
implies(F,T,F)    = F   (mandated: F, "left-only" — right-assoc and truncation both give T)
implies(T,B,N,F)  = F   (mandated: F)
```
All five match exactly (hand-derived independently from the §4 pair algebra before running, then
confirmed by direct execution — see transcript in review session). The extension corpus's new
case **D7** (`fixtures/limnalis_extension_corpus_v0.1.yaml`, `id: D7`) pins the red team's exact
repro (`t <=> f <=> f`, `f -> t -> f`) plus a third chain (`t -> b -> n`); `tests/test_extension_corpus.py::test_d7_nonassociative_chains`
checks both the tree shape and the truth values end-to-end through the live path.
`tests/test_runtime_primitives.py::TestEvalLogicalConnectives` adds direct-execution tests for
all of the above plus a flat-vs-explicitly-nested equivalence sweep (defense-in-depth for
hand-built ASTs, since the Pydantic model and vendored schema still permit `args > 2`).

### 2. HIGH-3 (B/N reason derivation) — VERIFIED, closed with an honestly-documented residual limitation

`_derive_composition_reason` (`builtins.py:1724`) implements §16.6.6: unique determining child
reason inherited, else `logical_composition` + info diagnostic. I verified both branches by
direct execution, including a case the test suite does not: `or(missing_binding-leaf,
declared_as_N-leaf)` → `('N', 'logical_composition', [...])` with both contributing reasons
named in the diagnostic message. `_eval_logical_expr` wires this at claim level (`builtins.py`
after line 1836); `fold_block` wires the same derivation at block level (`builtins.py:594`,
`fold_block` docstring at `:526`). The block-level docstring states plainly that `fold_block` has
no diagnostics-list parameter in its signature, so the `logical_composition` case there carries
only the reason code, not the contributing-reasons diagnostic — I confirmed this against the
actual function signature (`-> tuple[dict[str, EvalNode], EvalNode]`, no `Diagnostics` in or
out): the limitation is real and honestly stated, not a silent gap.

**22-field deep-diff claim, independently reproduced.** Using a separate `git worktree` at
`fc02fe6`, I ran the vendored corpus through both `conformance report --format json` (byte-`diff`
clean) and a full `BundleResult.model_dump(mode="json")` dump for all 16 cases before/after. The
diff has exactly 38 changed lines: 16 are the new `eval_path` field (`null`→`"echo"`, an artifact
of the field not existing pre-fix) and **22 are `"reason": null` → `"reason": "<value>"`**, all at
`block_results[].per_evaluator[...].reason` / `block_results[].aggregate.reason` paths, all for
`truth: "N"` block folds. No other field differs anywhere in ~11,300 lines of dumped JSON. This
matches the claim exactly.

### 3. HIGH-1 fail-closed gate — VERIFIED, closed

`build_live_fixture_services` (`plugins/fixtures.py:1156`) now raises
`LiveFixturePackCoverageError` on partial coverage (`:1184`) and returns `None` only on zero
coverage. The new corpus-manifest guard in `run_case` (`conformance/runner.py:866-868`) closes
the zero-coverage gap: it computes `declared_bindings = set(corpus.bindings_by_id)` (the
corpus's own `fixtures:` manifest ids) and, only when that set intersects
`live_fixture_evaluator_uris()` (i.e., only for a corpus that self-identifies as "live" by
declaring live-pack URIs), flags any bundle evaluator binding not in `declared_bindings` as a
loud error. I traced this by hand against both corpora's actual binding-id namespaces
(`test://eval/atoms_v2...` for the extension corpus's `fixtures:` section vs. wholly disjoint
`test://eval/atoms_v1...` for the vendored corpus) and confirmed the guard is **provably inert**
for the vendored corpus (empty intersection, by construction of disjoint URI namespaces) while
active for the extension corpus. `tests/test_extension_corpus.py::TestLiveGateFailClosed`
reproduces both of the red team's exact repros (typo'd URI, with and without a tampered pin) and
a new partial-coverage case, all now failing loudly. Both safety nets pass:
`test_every_extension_case_activates_live_path` (11/11 `eval_path == "live"`) and
`tests/test_conformance.py::TestVendoredEvalPath::test_all_vendored_cases_run_on_echo_path`
(16/16 `eval_path == "echo"`) — both independently re-confirmed by me via direct script
execution, not just by reading the tests.

### 4. HIGH-2 baseline cache scoping — VERIFIED, closed

`run_bundle` (`runtime/runner.py:899-900`) installs a fresh `services["__baseline_value_cache__"]`
on every call unless the caller opts in via `services["__shared_baseline_cache__"]`. I confirmed
only `run_bundle` does this (`run_session`/`run_step` untouched, matching the documented
"callers own the lifecycle" scoping). `tests/test_runtime_runner.py::TestSharedStateBaselineCaching::
test_fixed_cache_does_not_survive_across_run_bundle_calls` and
`::test_shared_baseline_cache_opt_in_survives_runs` both pass, and the extension corpus's
`TestBaselineCacheRunScoping::test_reused_services_dict_does_not_leak_fixed_cache` reproduces the
red team's exact D5 repro as a passing regression test. The pre-existing `shared_state=True/False`
tests in the same test class (which drive `run_session` directly) are untouched in the diff and
still pass — D5/T4 semantics unchanged.

### 5. Comparator vs §18.2 — VERIFIED, closed

`claimIds` are now compared order-sensitively against `BlockResult.claims`
(`conformance/compare.py:391-408`). Step-level reverse checks exist for claims (`:713-733`),
blocks (`:750-768`), and transports (`:786-798`) with exactly the two documented exemptions:
non-evaluable note claims (via `ClaimClassification.evaluable`) and per-bridge transport
scaffolding (via `bridge_ids` computed from `bundle.bridges`). I confirmed via the test suite
that a genuinely extra evaluated claim fails
(`test_claim_subset_leak_is_detected_step_level`) while a note claim
(`test_note_claims_stay_exempt_from_reverse_check`) and a per-bridge transport entry
(`test_unpinned_executed_transport_query_is_flagged`, which also asserts `b_to_core` is NOT
flagged) do not. The warnings channel (`CaseComparison.warnings`) never touches `passed`
(`passed=len(mismatches) == 0` at `compare.py`, warnings is a fully separate list) — confirmed
both by the dedicated unit tests and by independently re-running comparison over all 16 vendored
cases myself: **0 warnings, 0 mismatches** (the extension corpus's own
`test_committed_corpus_produces_zero_warnings` covers the extension side at 0/11). No vendored
expectation newly fails (16/16 pass, byte-identical report, confirmed above).

### 6. score=N vocabulary — VERIFIED, closed, and correctly bounded

`_evaluate_single_assessment` (`builtins.py:980`) now branches to `N[not_yet_applicable]` +
warning only when `method_handler is not None` (i.e., the method IS resolved) and the score is
declared or computed as the `"N"` sentinel; an unresolved method still falls through to
`N[missing_binding]` + error. I checked this boundary against the spec directly:
`spec/Limnalis-v0.2.2.md:2043-2044` states, as a **settled AST decision**, "Unresolved method
always yields N[missing_binding] regardless of score presence" — this is exactly the priority
order the fix implements (`§9.2` also lists "method unresolved →N[missing_binding]" before the
score=N rule). `tests/test_runtime_primitives.py` adds direct tests for all four quadrants
(resolved+declared-N, resolved+computed-N, unresolved+declared-N, resolved+numeric-recompute
[pre-existing behavior preserved]). Joint adequacy reuses the same fixed function
(`evaluate_adequacy_set` calls `_evaluate_single_assessment` at both `builtins.py:1154` and
`:1263`), so the fix isn't partial. C2's corpus pins, `docs/paradox_gallery.md`, and the
`ast_decisions`/precision-note text are updated coherently and consistently, and — matching the
task's expected framing exactly — the gallery explicitly states `no_adequacy_result` (the
license-time "no record at all" case, C1 `l1`/C4 `c2`) **remains** a documented, un-fixed
divergence from the spec sketch, correctly scoped as out of this cycle.

### 7. Pipe shielding — VERIFIED, closed

All four scanners (`_scan_top_level_matches`, `_split_top_level`, `_split_words`,
`_is_wrapped_expression`) now share `_pipe_span_opens` (`normalizer.py:1399-1416`). I ran the red
team's exact MEDIUM-3 repro table directly against `_parse_expr_text`/`_split_args` (not just via
tests): `p(|0:a,b|, c)` → 2 args (`BaselineRefTerm("a,b")`, `SymbolTerm("c")`); `(a AND |0:x'y|)`
→ `and(a, |0:x'y|)`; `(a AND |0:x(y|)` → `and(a, |0:x(y|)`; `declare |0:x'y| as fiction` → a
proper `DeclarationExpr` (previously `NormalizationError`). All four match the fix's claimed
output exactly. I additionally ran 5 adversarial variants of my own (nested pipes, two spans in
one expression, `NOT` over a span containing the word `AND`, a bare wrapped span) — all
deterministic, no crashes, span content correctly kept opaque. Note: `tests/test_normalizer_claim_forms.py`
correctly routes the `declare`+quote repro through a **parenthesized** form
(`(declare |0:x'y| as fiction)`), because the surface grammar's `ATOM` terminal
(`grammar/limnalis.lark:33`, `/[^{}\s;"']+/`) excludes bare `'` outside of the separate `GROUP`
regex terminal (`\([^()]*\)`, which has no such exclusion) — an unrelated, pre-existing,
out-of-scope grammar characteristic, not a gap in this fix (I confirmed this by hitting the raw
Lark tokenizer error myself on the unparenthesized form, then finding the test file already
anticipates and documents exactly this).

### 8. Standard gates — ALL PASS

- Full suite: **1094 passed**, run twice back-to-back — deterministic, matches the expected count exactly.
- Extension corpus: 11/11 cases, all `eval_path == "live"` (verified independently).
- Vendored corpus: 16/16 cases, all `eval_path == "echo"`; `conformance report --format json`
  byte-`diff`-identical against a `git worktree` at `fc02fe6`; vendored fixture/spec/grammar/schema
  files SHA-256-identical to `fc02fe6` (`fixtures/limnalis_fixture_corpus_v0.2.2.{yaml,json}`,
  both spec files, `grammar/limnalis.lark`, and a full `diff -rq` over `schemas/`).
- Extension corpus: 0 AST-schema and 0 conformance-result-schema errors across all 11 cases
  (independently re-run, not just read from tests); YAML/JSON twins parse-identical
  (`yaml.safe_load(...) == json.load(...)`).
- All 9 `examples/*.lmn` normalize cleanly.
- Gallery canary (`tests/test_extension_corpus.py`, doc-drift check) passes.
- Ruff: I ran `ruff check` on every one of the 13 changed Python files against both `fc02fe6` and
  the current tree. Raw counts are identical ("Found 79 errors" both times); after normalizing
  away line-number shifts (files grew), the `(file, rule-code)` violation multiset is **exactly
  identical** — zero new violations introduced, zero fixed, full parity.

### 9. Cross-fix interactions — no seam defects found

α's newly-populated B/N reasons (claim- and block-level) flow correctly into β's new comparator
checks: the corpus pins were updated in lockstep (D1/D2/C4 reasons, C2's `not_yet_applicable`),
and both corpora independently verified at 0 warnings / 0 mismatches — if the two fixes
disagreed, the new under-pin warning would have fired. D7 is included in the corpus iterated by
`test_every_extension_case_activates_live_path`, so it is exercised by the fail-closed gate (live
path confirmed). `EvalNode.reason` is a pre-existing model field (`runtime/models.py:132`), so
none of this required a model change. I found no seam defect between the two implementers' work.

## Advisories (non-blocking)

1. **No standing regression test pins "vendored corpus produces zero comparator warnings."**
   `tests/test_extension_corpus.py::test_committed_corpus_produces_zero_warnings` covers the
   extension side; the equivalent vendored-side property (which I verified holds today, 0/16, by
   direct script execution) has no test of its own in `tests/test_conformance.py`. Low risk since
   the vendored corpus is immutable (FIXTURE-001) — this could only regress via a future
   comparator-logic change, which would receive its own review.
2. **`run_case(case, corpus=None)` bypasses the HIGH-1 corpus-manifest guard entirely** (the
   `elif corpus is not None:` branch at `conformance/runner.py:865` is simply skipped). Both real
   call sites (`src/limnalis/cli/_existing.py:919,995`) always pass a corpus; the only
   `run_case(case, None)` callers are pre-existing synthetic/mocked tests unrelated to live-pack
   coverage (`tests/test_conformance.py:208,254`). Worth a docstring note if a future caller might
   omit the corpus in a live-pack-relevant context, but not a live gap today.
3. **MEDIUM-4/5/6/7 and LOW-1/2/3 from `.armature/reviews/m7-redteam.md` remain open**, exactly as
   documented by the original review (unclamped delimiter depth silently swallowing operators;
   `compute_pass_v1` injected into live-pack adequacy handlers; untraced baseline materialization;
   the pre-existing `JudgedExpr` two-stage-contract gap; the three LOWs). These were explicitly
   outside this remediation cycle's stated scope (CRITICAL-1, HIGH-1/2/3, and the
   score-N/comparator/pipe-shielding MEDIUMs) and I confirmed none of them were silently worsened
   — they are candidates for a future cycle, not a defect in this one.

## Verdict: PASS_WITH_ADVISORIES

Every finding this cycle targeted — CRITICAL-1 (both halves), HIGH-1, HIGH-2, HIGH-3, and the
three named MEDIUMs (score=N vocabulary, comparator blindness, pipe shielding) — is closed, and I
independently reproduced the closure by direct execution rather than relying on the diff's own
tests: hand-verified pair-algebra discriminators run against the live evaluator, a from-scratch
`git worktree` diff proving vendored byte-identity and the exact 22-field reason-only deep-diff,
an independent zero-warnings sweep over both corpora, the red team's own exact repro strings run
through the fixed code, and a ruff parity check. The full suite is green twice (1094/1094,
deterministic). All vendored artifacts are untouched (SHA-identical). No invariant is violated,
no restricted action occurred, and no cross-fix seam defect was found. The three advisories above
are minor, forward-looking, and none of them represents a false-green surface or a wrong
computed value.

## Rollback Recommendation: NO

Remediation is sound; proceed to red team re-verdict.
