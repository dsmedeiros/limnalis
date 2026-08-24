# Red Team Review: Milestone 7 (full changeset, 0994537..ae06552)

**Reviewer:** reviewer-redteam
**Date:** 2026-08-24
**Scope:** commits `73c0154` (m7/t1) through `ae06552` (m7/t7) — seven commits on
`claude/semantic-web-ontologies-3nyyy3`. PRD: `.taskmaster/docs/milestone-7-remediation-track-c.md`.
**Baseline for before/after comparison:** `0994537` (milestone open).

## Summary

The milestone's headline work is real and mostly correct: the Belnap–Dunn pair algebra
matches spec §4 exactly on the full 16-entry conjunction/disjunction tables, the EBNF
precedence rebuild produces the spec-mandated trees, `claim_subset`/`shared_state`
behave per §16.2.1/§16.6.3 under my own independent probes, the vendored artifacts are
byte-identical to their pre-M7 state, determinism holds, the 13-phase primitive contract
is intact, and 12/12 hand-computed deep mixed expressions (nested NOT over IFF, Unicode/word
spelling mixes, precedence chains) evaluate correctly end to end.

**But the T1×T2 seam is broken exactly where I suspected it, and worse than the fold-direction
hypothesis.** T2 newly makes the normalizer emit n-ary (3+ operand) `implies` and `iff`
`LogicalExprNode`s — a shape that did not exist before this milestone. T1's evaluator
indexes `sub_truths[0]` and `sub_truths[1]` and **silently discards every operand past the
second**. This is not a wrong fold direction; it is truncation. `t <=> f <=> f` evaluates to
`F` when both left- and right-associative readings give `T`. Neither the per-task tests nor
the extension corpus cover a 3-operand chain — `tests/test_operator_precedence.py` pins the
3-arg *tree* and `tests/test_runtime_primitives.py` pins the *binary* algebra; nothing joins
them.

Three further HIGH findings concern the new live-services machinery: a silent live→echo mode
fallback that makes extension pins self-fulfilling, a baseline cache that outlives its
evaluation run, and B/N results emitted with no reason code in violation of the spec's
"B and N always require reason codes" rule — with the reasonless results pinned as settled
in the new corpus.

**Verdict: FAIL.** One CRITICAL (silent wrong truth values on canonical spec syntax) blocks.

---

## Critical Findings

### CRITICAL-1 — n-ary `IMPLIES`/`IFF` silently drop all operands past the second

**Files:**
- `src/limnalis/runtime/builtins.py:1689-1697` (`_eval_logical_expr`)
- `src/limnalis/normalizer.py:1187-1198` (`_parse_expr_text`, n-ary flattening)

**What is wrong.** `_parse_expr_text` flattens repeated same-level operators into a single
n-ary `LogicalExprNode` (`a -> b -> c` → `implies(a, b, c)`; documented and tested in
`tests/test_operator_precedence.py::TestRepeatedOperatorAssociativity`). `_eval_logical_expr`
handles `and`/`or` by folding the whole `sub_truths` list, but handles `implies` and `iff` by
indexing:

```python
elif expr.op == "implies":
    not_a = _truth_flip(sub_truths[0])
    result_truth = _truth_or([not_a, sub_truths[1]])
elif expr.op == "iff":
    implies_ab = _truth_or([_truth_flip(sub_truths[0]), sub_truths[1]])
    implies_ba = _truth_or([_truth_flip(sub_truths[1]), sub_truths[0]])
    result_truth = _truth_and([implies_ab, implies_ba])
```

`sub_truths[2:]` is evaluated (leaf handlers fire, provenance is collected, diagnostics are
propagated) and then thrown away. Both the Pydantic model (`models/ast.py:253`, `args >= 2`)
and the vendored AST schema (`minItems: 2` for non-`not`) permit 3+ args, so nothing rejects
the shape.

**Shortest repro — the project's own test helper** (`tests/test_runtime_primitives.py:356`):

```python
_eval_logical('iff', 'T', 'F', 'F')          # -> 'F'   ; both associativities give 'T'
_eval_logical('implies', 'T', 'B', 'N')      # -> 'B'
_eval_logical('implies', 'T', 'B')           # -> 'B'   ; identical - the tail is discarded
```

**How to trigger from surface syntax.** Any expression chaining three or more
`->`/`<=>`/`IMPLIES`/`IFF` at one precedence level. `->` and `<=>` are the spec's *canonical*
ImplOp/IffOp spellings (reconstructed EBNF lines 1236, 1243-1244), not legacy forms.

```
bundle NARY {
  frame { system Test; namespace Logic; scale unit; task check; regime nominal; }
  evaluator ev0 { kind model; binding test://eval/atoms_v2; }
  resolution_policy rp0 { kind single; members [ev0]; }
  local {
    c1: f -> t -> f;
    c4: t <=> f <=> f;
  }
}
```
Run through `run_bundle` with `build_live_fixture_services` (atoms_v2: t=T, f=F):

| claim | args | actual | left-assoc | right-assoc |
|---|---|---|---|---|
| `c1: f -> t -> f` | 3 | **T** | F | T |
| `c4: t <=> f <=> f` | 3 | **F** | **T** | **T** |

`c4` is the discriminator: `F` is wrong under *every* associativity convention. The actual
result is simply `t <=> f`. Direct proof that the tail is ignored:

```python
_eval_logical_expr(implies, args=[f, t])          -> T
_eval_logical_expr(implies, args=[f, t, f])       -> T
_eval_logical_expr(implies, args=[f, t, f, f])    -> T
_eval_logical_expr(implies, args=[f, t, zzz])     -> T   # unknown atom, still T
```

**What happens when triggered.** A silently wrong four-valued truth for the claim, which
propagates into per-evaluator results, resolution-policy aggregation, block folding, block
aggregates, transport source aggregates, and the summary. No diagnostic, no exception.

**Why the per-task reviews missed it.** Pre-M7 (`0994537`), `a IMPLIES b IMPLIES c`
normalized to a single atomic `PredicateExpr` named `"a IMPLIES b IMPLIES c"` — the n-ary
shape was unreachable, so T1's binary-only evaluator was adequate at the time it was written.
T2 made the shape reachable and pinned the tree; T1's review predates T2. `AND`/`OR` are
associative so their n-ary fold is sound, which is why the flattening looked safe.

Most tellingly, T1 *did* add an n-ary test —
`tests/test_runtime_primitives.py::test_nary_connectives_fold_pairwise`, docstring
*"spec §4 pair algebra generalizes n-ary"* — but it asserts only `and(T,B,N)` and `or(F,N,B)`,
i.e. exactly the two operators whose implementation folds the full list. The author reasoned
about n-ary generalization and tested the half that works.

**Severity: CRITICAL** (wrong output produced silently). **Blocks.**

---

## High Findings

### HIGH-1 — A typo'd evaluator binding URI silently converts an extension case to claim-id echo, making its pins self-fulfilling

**File:** `src/limnalis/conformance/runner.py:819-824`; gate in
`src/limnalis/plugins/fixtures.py:1130-1161` (`build_live_fixture_services`).

`build_live_fixture_services` returns `None` unless **every** evaluator binding URI is in
the live pack. On `None`, `run_case` keeps `primitives = PrimitiveSet(eval_expr=fixture_eval_expr, ...)`
— the claim-id-keyed handler built *from the case's own `expected.per_evaluator` map*. So a
case that falls off the live path echoes its own expectations and passes unconditionally.
Nothing in the corpus, the comparator, or the test suite asserts that a given extension case
actually took the live path.

**Repro:**
```python
case = copy.deepcopy(corpus.get_case('D1'))
case.source = case.source.replace('test://eval/atoms_v2', 'test://eval/atoms_v2x')  # one char
run_case(case, corpus); compare_case(...)          # -> passed = True

case2 = copy.deepcopy(corpus.get_case('D1'))
case2.source = (case2.source
    .replace('test://eval/atoms_v2', 'test://eval/atoms_v2x')
    .replace('c1: (b AND n);', 'c1: (t OR t);'))   # expression now computes T, pin still says F
run_case(case2, corpus); compare_case(...)          # -> passed = True, c1 truth = F
```
The second case is a corpus that pins `F` for an expression that evaluates to `T` and still
reports green. The existing canary `test_conformance_path_computes_rather_than_echoes` only
mutates the *expression*, not the URI, so it does not detect this; `test_live_pack_ignores_vendored_bindings`
asserts the opposite direction.

**Blast radius.** Any future edit that adds an evaluator with a non-pack URI, renames a pack
URI, or typos one, silently downgrades that case from "computed live" to "echoes itself" while
the suite stays green. This directly undermines the corpus's stated authority ("its cases are
evaluated LIVE", corpus header) and PRD acceptance criterion 2/3.

**Severity: HIGH** (false green; regression of the corpus's discriminating power).

### HIGH-2 — `__baseline_value_cache__` survives across `run_bundle` invocations and silently returns stale baseline values

**File:** `src/limnalis/runtime/builtins.py:760, 778-780` (`materialize_referenced_baselines`).

The fixed-baseline cache is stored in the caller-owned `services` dict under
`__baseline_value_cache__`, keyed `(session_id, baseline_id)` — no bundle id, no run id, and
no lifecycle. The docstring states the intent ("survives across the per-step MachineState
instances **within a** `run_session`/`run_bundle` invocation") but nothing enforces it.
`conformance.runner.run_case` happens to build a fresh services dict per case, which is why
the corpus never sees this; any caller that reuses a services dict (the natural pattern for a
plugin registry / long-lived host) gets stale values.

**Repro** (D5 bundle, `test://baseline/by_context_v1`):
```python
services = build_live_fixture_services(bundle)
# Run A: session "s_shared", one step at t1/nominal
run_bundle(bundle, [SessionConfig(id='s_shared', steps=[StepConfig(id='s1', time=t1, frame_override=nominal)])],
           env, services=services)
#   -> b_fixed = 10, c_fixed = T          (correct)
# Run B: SAME services dict, same session id, one step at t2/stress
run_bundle(bundle, [SessionConfig(id='s_shared', steps=[StepConfig(id='s1', time=t2, frame_override=stress)])],
           env, services=services)
#   -> b_fixed = 10, c_fixed = T          (WRONG — stale)
# Control: fresh services, same Run B config
#   -> b_fixed = 20, c_fixed = F          (correct)
```
A claim's truth value flips from `F` to `T` purely because a services dict was reused. Spec
§16.6.3 scopes the fixed-baseline cache to a *session*; nothing licenses survival across
evaluation runs.

**Severity: HIGH** (silently wrong output under a plausible, undocumented-as-forbidden caller
pattern; borderline CRITICAL — it is only not CRITICAL because the in-repo callers happen to
avoid it).

### HIGH-3 — Live logical composition emits `B`/`N` with no reason code, violating spec §8.5 and §16.6.6 — and the new corpus pins the omission as settled

**Files:** `src/limnalis/runtime/builtins.py:1701-1705` (`_eval_logical_expr` return),
`src/limnalis/runtime/builtins.py:566-575` (per-evaluator block fold `EvalNode`),
`fixtures/limnalis_extension_corpus_v0.1.yaml:56-64` (ast_decision "Composed-claim reasons
under live sub-expression evaluation").

Spec §8.5: *"B and N always require reason codes."* Spec §16.6.6: *"If logical composition
yields B or N: if one child reason uniquely determines the outcome, inherit it; otherwise use
`logical_composition` and record contributing child reasons in diagnostics."*

`_eval_logical_expr` returns `TruthCore(truth=result_truth, provenance=sorted(provenance))` —
`reason` is never set, and no `logical_composition` diagnostic is ever emitted anywhere in the
runtime (the only occurrences of that code are the comparator's *injection* shim,
`conformance/runner.py:641-658`). The same omission exists in `fold_block`'s per-evaluator
`EvalNode` construction.

**Observed (live extension corpus, `run_case` output):**
| case | claim | expr | truth | reason | §16.6.6 expected reason |
|---|---|---|---|---|---|
| D1 | c2 | `t AND b` | B | `None` | `source_conflict` (unique child reason) |
| D1 | c3 | `t AND n` | N | `None` | `undefined_term` |
| D1 | c4 | `f OR n` | N | `None` | `undefined_term` |
| D2 | c2 | `NOT b` | B | `None` | `source_conflict` |
| D2 | c3 | `NOT n` | N | `None` | `undefined_term` |
| C4 | block `local#1` / `ev_zf` | fold {N,N} | N | `None` | a reason is mandatory |

Pre-M7 this was unobservable (no case computed composition live). M7 built the live path
specifically to compute composition for real, then wrote the extension corpus to match the
incomplete output and recorded it as a *settled* `ast_decision` — framing a normative-MUST
violation as a stylistic difference from the vendored corpus. That framing is what a standard
review would accept and what a red team must not.

**Severity: HIGH** (spec-normative violation newly enshrined as conformance authority; the
milestone's own new machinery is the thing that surfaces it).

---

## Medium Findings

### MEDIUM-1 — C2 pins `score = N` → `N[missing_binding]` + an **error** diagnostic; spec mandates `N[not_yet_applicable]`, and the cited justification does not apply

**Files:** `fixtures/limnalis_extension_corpus_v0.1.yaml:66-74, 1104-1110, 1173-1181`;
implementation at `src/limnalis/runtime/builtins.py:920-950`.

Spec §9.2: *"If score = N, result is `N[not_yet_applicable]`."* Spec §16.6.4: *"Score=N →
`N[not_yet_applicable]`"* and *"score=N or no record → `N[not_yet_applicable]`"*.
`not_yet_applicable` is in the §8.5 N-reason taxonomy; `no_adequacy_result` is not.

The implementation collapses "score explicitly declared N" into the same branch as "no method
binding available" (`effective_score = None` at line 923-924 → `reason = "missing_binding"` at
945 → `severity: error, code: adequacy_method_binding_missing` at 946-948). The corpus pins
this and justifies it with *"per the vendored ast_decision `unresolved_method -> N[missing_binding]`"*.
That decision (vendored corpus line 116) is about an **unresolved method**. C2's `aa_core`
method `test://paradox/method/qg_tbd_v1` **is** registered and resolves — the fixture returns
the sentinel string `'N'` on purpose. So the cited authority does not cover the pinned case.

The knock-on: an author declaring "we have not computed this yet" gets a severity-`error`
diagnostic that says a binding is missing. The gallery doc (`docs/paradox_gallery.md:124`)
repeats it. The underlying code defect is pre-existing (commit `0d81033`), but M7 is the
commit that turns it into a pinned conformance expectation in a project-authored corpus and
documents it in a published gallery.

The same class applies to `no_adequacy_result` (C1 `l1`, C4 `c2`): spec says "no record →
`N[not_yet_applicable]`"; the implementation invents a reason code outside the §8.5 taxonomy.

**Severity: MEDIUM.**

### MEDIUM-2 — `claimIds` corpus pins are never compared, and step claim comparison has no reverse check

**File:** `src/limnalis/conformance/compare.py:276-336` (`_compare_block`), `557-612`
(`_compare_session`).

`_compare_block` reads only `per_evaluator` and `aggregate` from the block expectation. Every
`claimIds:` pin in the extension corpus (D1, D2, D4, D6, C1, C3, C4) is decorative — the
comparator never looks at `BlockResult.claims`. This matters most for D6, whose whole point is
that `claim_subset` changes the block claim listing.

Separately, `_compare_session` iterates only over *expected* claims. There is no
"extra actual claim not in expectation" check at the step level (there is one at the
per-evaluator level inside a block, `compare.py:315-321`). The §16.2.1 requirement that
excluded claims are *absent from results* is therefore not verified by the corpus at all.

Mitigation that keeps this at MEDIUM: `tests/test_extension_corpus.py:255-263` asserts
`block1.claims == ["c_keep","c_drop"]` / `block2.claims == ["c_keep"]` and
`set(step2.per_claim_aggregates) == {"c_keep"}` directly, and D6's block *aggregate* (F vs T)
does discriminate. But the corpus mechanism itself is blind, and
`src/limnalis/conformance/agents.md:34-35` explicitly claims "Comparison functions must check
both directions … one-directional blindness is a previously remediated defect class" — which
is not true of the step-level claim map or of `claimIds`.

**Severity: MEDIUM** (false-green surface in the conformance mechanism; contradicts a scoped
agents.md directive added by this same milestone).

### MEDIUM-3 — T2b's pipe-span shielding is applied to only one of four scanners

**File:** `src/limnalis/normalizer.py` — shielded: `_scan_top_level_matches:1399-1411`;
**unshielded:** `_split_top_level:2002-2052` (used by `_split_args`), `_split_words:1438-1489`,
`_is_wrapped_expression:2060-2084`.

The T2b remediation justified pipe-span shielding on the grounds that *"this normalizer imposes
no charset restriction on the reference id"* (docstring at `normalizer.py:1361-1376`). That
argument applies identically to the other three scanners, which still interpret delimiters and
quotes inside `|0:…|` spans. Reproducible structure loss:

| input | result | expected |
|---|---|---|
| `p(\|0:a,b\|, c)` | 3 args: `SymbolTerm("\|0:a")`, `SymbolTerm("b\|")`, `SymbolTerm("c")` | 2 args: `BaselineRefTerm("a,b")`, `SymbolTerm("c")` |
| `(a AND \|0:x'y\|)` | atomic `PredicateExpr(name="(a AND \|0:x'y\|)")` | `and(a, \|0:x'y\|)` |
| `(a AND \|0:x(y\|)` | atomic `PredicateExpr` of the whole text | `and(a, \|0:x(y\|)` |
| `declare \|0:x'y\| as fiction` | `NormalizationError: must contain an 'as' clause` | a DeclarationExpr |

Compare `p(|0:a AND b|, c)`, which *does* produce a correct `BaselineRefTerm("a AND b")` —
the shielding is inconsistent between the operator scan and the argument scan for the same
span. Deterministic and non-crashing, so not HIGH, but the remediation is half-done and the
docstring overstates the coverage ("`|0:...|` spans are additionally shielded from **every**
top-level scan", `normalizer.py:1230-1232` — they are not).

**Severity: MEDIUM.**

### MEDIUM-4 — Unbalanced-delimiter operator swallowing is silent; delimiter depth is never clamped at zero

**File:** `src/limnalis/normalizer.py:1415-1428` (`_scan_top_level_matches` depth counters),
`912-984` (`_warn_boundary_operator_predicates`).

`paren_depth`/`bracket_depth`/`brace_depth` can go negative and are never clamped, so a single
stray closer permanently shields the rest of the text from every top-level scan. T2b's new
`expr_malformed_operator` warning only fires for a word operator at a *boundary* of a predicate
name, so operators swallowed mid-name by a delimiter imbalance are silent:

| claim expression | normalized | diagnostics |
|---|---|---|
| `a AND b) OR c` | `and(a, PredicateExpr("b) OR c"))` — the `OR` is swallowed | **none** |
| `(a AND b OR c` | `PredicateExpr("(a AND b OR c")` — both operators swallowed | **none** |
| `a) AND b` | `PredicateExpr("a) AND b")` | **none** |
| `AND b` / `a AND` | `PredicateExpr` | `expr_malformed_operator` ✓ |

NORM-002 requires a structured diagnostic for every non-trivial normalization decision;
discarding operator structure because of a delimiter imbalance qualifies. No crashes and fully
deterministic degradation, which is why this is MEDIUM not HIGH. (I fuzzed ~100 pathological
inputs — nested quotes in pipes in parens, adjacent operators, operators at both boundaries,
30-deep nesting, unbalanced everything — with zero crashes and zero recursion errors.)

### MEDIUM-5 — `run_case` injects the vendored `compute_pass_v1` adequacy handler into live-pack services

**File:** `src/limnalis/conformance/runner.py:831-833`.

```python
services.setdefault("adequacy_handlers", {}).setdefault(
    "test://adequacy/compute_pass_v1", lambda assessment: 1.0
)
```
When the live path is active, `services["adequacy_handlers"]` is the pack's table; the
`setdefault` adds a vendored scaffolding handler that always returns 1.0. Verified for C2:
final table is `['test://adequacy/compute_pass_v1', 'test://paradox/method/gw_waveforms_v1',
'test://paradox/method/qg_tbd_v1']`. No current extension case references that URI, so no
wrong result today — but it breaks the stated "live pack only" contract: an extension case
could resolve a method it never declared and get an automatic pass. (The outer dict is freshly
built per call by `build_services_from_registry`, so there is no cross-case mutation leak —
I verified that separately, see "Verified Clean" below.)

### MEDIUM-6 — Baseline materialization is an untraced side effect inside phase 8

**File:** `src/limnalis/runtime/runner.py:487-498`.

`_materialize_referenced_baselines` mutates `machine_state.baseline_store` and the services
cache from inside the phase-8 evaluator loop, but appends no `PrimitiveTraceEvent`. Trace
consumers see 13 events per step (RUNTIME-001 verified intact across all 26 corpus cases) and
cannot see when or whether a baseline was resolved. It is also invoked once per
*(claim, evaluator)* pair, so a stateful or call-counting resolver observes a call count that
scales with panel size — defensible for `on_reference` per §16.6.3, but undocumented.

### MEDIUM-7 (advisory, pre-existing code) — JudgedExpr two-stage contract is not implemented; C1's flagship verdict is produced without stage 1

**File:** `src/limnalis/runtime/builtins.py:1736-1750` (`_eval_judged_expr`).

Spec §12.1: *"Default judgment evaluation is two-stage: (1) evaluate the wrapped inner
expression under the active evaluator; (2) pass the inner truth result, the expression, the
criterion reference, and the current context to the criterion binding"*, with
`CriterionBindingContract: evalJudged(innerTruth, expr, criterionRef, ctx, history, services)`.

When a `JudgedExpr` handler exists, `_eval_judged_expr` calls
`handler(expr, claim, step_ctx, machine_state)` and returns immediately — the inner expression
is **never evaluated** and no `innerTruth` is passed. (The spec permits a criterion to *ignore*
`innerTruth`, but not for stage 1 to be skipped or for the contract to omit the parameter.)
The code is byte-identical to `0994537`, so this is pre-existing; I raise it because M7 T6 is
the first case to exercise it live: C1's `l3` → `B[self_reference]` is presented in the corpus
and in `docs/paradox_gallery.md:77` as a computed forensic verdict, and
`tarski_self_reference_criterion` (`plugins/fixtures.py:768-806`) decides it purely by walking
the un-evaluated expression for the claim's own id.

---

## Low Findings

- **LOW-1** — `resolve_baseline` (`builtins.py:607-670`) marks fixed baselines
  `status="ready"` with `value=None` in phase 3, before any materialization. D5's
  `expected.baseline_states: {b_fixed: ready, b_step: ready}` is therefore satisfied trivially
  by phase 3 and pins nothing. Observed directly: with `claim_subset=['c_step']` in step 1,
  `baseline_store['b_fixed'] == ('ready', None)`.
- **LOW-2** — Test gap that is the seam itself:
  `tests/test_operator_precedence.py:419-424` pins the 3-arg `implies` *tree*, and
  `tests/test_runtime_primitives.py::test_nary_connectives_fold_pairwise` pins n-ary `and`/`or`
  evaluation — but nothing evaluates a 3-arg `implies`/`iff`. Two tests bracket the hole
  CRITICAL-1 lives in without covering it.
- **LOW-3** — Non-evaluable note claims still receive a `LicenseResult` (`C1 l0 → T`,
  `C4 m1 → T`). Harmless today; §16.6.7 excludes notes from support synthesis and the same
  spirit arguably applies to licensing.

---

## Verified Clean (things I attacked and could not break)

Recorded so the next reviewer does not repeat the work:

1. **Spec §4 pair algebra.** Full 16-entry `∧` table, `∨` table, `¬` fixpoints verified
   against `spec/Limnalis-v0.2.2.md:611-634` by hand. `_fold_block_truth`
   (`builtins.py:502-521`) is provably equivalent to `_truth_and` over the same multiset for
   all four values, so expression-level and block-level conjunction agree.
2. **Deep mixed binary expressions.** 12 hand-computed cases (nested `NOT` over `IFF`,
   Unicode/word spelling mixes `t ∧ b ∨ n ∧ f`, `b → n ↔ t`, `NOT b AND t OR n`, double
   negation, cross-level precedence) — **0 mismatches** end to end through
   `eval_expr` + `atoms_v2`.
3. **D1/D4 corpus pins re-derived independently from spec §4** (not from the reviews):
   `B∧N=F`, `T∧B=B`, `T∧N=N`, `F∨N=N`, `B∨N=T`, `¬B=B`, `¬N=N`, `B→N=T`, `B↔N=T`;
   `t AND f OR t = T`, `f AND t OR t = T` (inverted tree gives F — real discriminator),
   `n OR t AND b = T` (inverted tree gives B — real discriminator). All correct.
4. **Support pins.** `absent` for evidence-free claims (§16.6.7 "E(claim)=∅ → absent"),
   `conflicted` for C3's `B[evaluator_conflict]` aggregate (§16.6.8), `partial` for degrade
   transport (§10.2 "if truth degrades due to loss, support becomes partial"). C4's
   `T`-with-inherited-`missing_binding` aggregate matches §16.6.8's "inherited unique reason
   where possible". All correct.
5. **C1–C4 block folds and licenses** re-derived: C1 `{N,B}→F`; C3 per-evaluator-first
   `{T,T}→T` / `{F,T}→F` then join `→B[evaluator_conflict]`; C4 `{T,F}→F` / `{N,N}→N` then
   join `→F`, note-only meta `→N[empty_block]`. All correct and matching §8.6.
6. **D5 vs spec §17.2 A11.** The corpus pins match the spec narrative verbatim
   (s_shared s2: b_fixed=10 cached, b_step=20; s_isolated s2: both 20). Verified live.
7. **`claim_subset` interaction probes** (all behaved sanely and per §16.2.1):
   subset excluding a transport target → `status=unresolved` + error
   `transport_source_missing`, no crash; empty subset `[]` → `N[empty_block]`,
   `claims=[]`, followed by an unrestricted step that evaluates normally;
   duplicate ids deduped; unknown ids → `claim_subset_unknown_id` warnings only;
   subset + `shared_state=false`; subset deferring a fixed baseline's first use to step 2 →
   baseline fixes against the step-2 context, which is exactly §16.6.3's
   "the first step that triggers it determines the context".
8. **Corpus-run ordering independence.** Ran extension-then-vendored and vendored-then-extension
   in one process; both result sets byte-identical to the isolated runs. No
   `PluginRegistry` reuse (fresh per `build_live_fixture_services` call), no shared services
   dict, no `__baseline_value_cache__` leakage between cases (each `run_case` builds a fresh
   dict). Gate under adversarial shapes: zero evaluators → `None`; mixed live/non-live
   bindings → `None`; missing binding attribute → `None`.
9. **FIXTURE-001.** `fixtures/limnalis_fixture_corpus_v0.2.2.{yaml,json}`, all of `schemas/`,
   `spec/Limnalis-v0.2.2.md`, `spec/Limnalis-v0.2.2-reconstructed.md`, `grammar/limnalis.lark`
   — SHA-256 identical to `0994537`. Vendored conformance 16/16; extension 10/10.
10. **NORM-001 / no normalizer regression.** I dumped the full normalized AST + diagnostics
    for all 16 vendored corpus sources and all 9 examples under pre-M7 code and current code:
    **the only differing key is `example:paradox_schwarzschild.lmn`**, a file that did not
    exist pre-M7. Zero new diagnostics on valid inputs (`expr_malformed_operator` fires on
    none of them — T2b's "zero false positives" claim holds). `normalize` run 3× on every
    example: byte-identical every time. Full suite run twice plus once in reversed file order:
    green each time.
11. **RUNTIME-001 / 002 / 003.** All 26 cases across both corpora emit exactly 13 trace
    events per step in strictly ascending phase order. `PrimitiveSet` still has exactly 13
    fields; `materialize_referenced_baselines` was correctly kept out of it. Notes bypass
    `eval_expr` and support synthesis.
12. **MODEL-001 / 002 / SCHEMA-001.** `src/limnalis/models/`, `src/limnalis/interop/`,
    `grammar/`, `schemas/` untouched by the milestone. Every normalized bundle from both
    corpora and all examples validates against the vendored AST schema, except the vendored
    A4 `b_invalid` baseline, which is a deliberate pre-existing negative case. Extension
    corpus YAML and JSON both validate 0-errors against the vendored fixture-corpus schema and
    are `==`-identical after parse.
13. **Fixture adjudicator is inert for C3/C4.** `_build_fixture_adjudicator` *is* constructed
    for C3 (its expectations contain `reason: evaluator_conflict`), but
    `apply_resolution_policy` only consults an adjudicator for `kind == "adjudicated"`; C3/C4
    are `paraconsistent_union`, so their B/T aggregates come from the real `_aggregate_truth`.
    Not an echo.
14. **`docs/paradox_gallery.md` verdict tables.** Spot-checked every license and block cell
    against live `run_case` output, including the four cells the corpus does *not* pin
    (`C1 l3`, `C2 c1`/`c2`, `C4 c1` licenses = T). All accurate. The doc's precision notes
    about `not_yet_applicable` being absent and transport via-URIs being declarative-only are
    factually correct.

---

## PRD Acceptance Criteria

| # | Criterion | Verdict |
|---|---|---|
| 1 | Full suite green; vendored 16/16; vendored files byte-unchanged | **MET** — 1022 passed (×3 runs incl. reversed order); 16/16; SHA-256 identical |
| 2 | Extension corpus validates against vendored schema and passes the conformance runner with all pinned expectations met | **MET with caveats** — 10/10 and 0 schema errors, but `claimIds` pins are uncompared (MEDIUM-2) and "passes" is not proof of live evaluation (HIGH-1) |
| 3 | `(a AND b OR c)` and friends normalize to EBNF trees; `B∧N=F` computed by the live algebra in ≥1 extension case | **MET** — D4 trees verified; D1 c1 = F computed live |
| 4 | `claim_subset` and `shared_state` observable behavior matches §16.2.1/§16.6.3, exercised by extension cases | **MET** — independently re-derived and probed beyond the corpus cases |

Criterion 3's "and friends" is where CRITICAL-1 sits: the trees are right, the *evaluation* of
3+-operand `implies`/`iff` trees is not.

---

## Verdict: FAIL

## Blocking Issues

1. **CRITICAL-1** — `_eval_logical_expr` (`src/limnalis/runtime/builtins.py:1689-1697`)
   silently discards `args[2:]` for `implies` and `iff`, producing wrong truth values for any
   3+-operand chain that `_parse_expr_text` (`src/limnalis/normalizer.py:1187-1198`) now
   flattens. Discriminating probe: `t <=> f <=> f` evaluates to `F`; both associativities give
   `T`. Whatever the fix, it must also settle and *document* the associativity reading of the
   EBNF's `{ ImplOp OrExpr }` / `{ IffOp ImplExpr }` repetitions, since `→` and `↔` are not
   associative — and it must be pinned by a truth-level test and an extension corpus case, not
   only by a tree-shape test.

## Issues That Should Be Fixed Or Explicitly Accepted Before Merge

2. **HIGH-1** — nothing asserts that an extension case took the live path; a one-character URI
   typo turns any case into a self-fulfilling echo that passes with a demonstrably wrong pin.
3. **HIGH-2** — `__baseline_value_cache__` has no run/bundle scoping and silently flips claim
   truths across `run_bundle` calls that share a services dict.
4. **HIGH-3** — live composition emits `B`/`N` without reason codes (spec §8.5 "always
   require"), never emits `logical_composition` (§16.6.6), and the extension corpus records the
   omission as a settled decision rather than a known divergence.

## Advisories (non-blocking, should be tracked)

- **MEDIUM-1** — C2's `score=N → N[missing_binding]` + severity-`error` pin contradicts spec
  §9.2/§16.6.4 (`N[not_yet_applicable]`); the vendored `unresolved_method` decision cited as
  justification does not cover a case whose method *is* resolved. Same class for the invented
  `no_adequacy_result` reason code (C1 `l1`, C4 `c2`), which is outside the §8.5 taxonomy.
- **MEDIUM-2** — `_compare_block` ignores `claimIds`; `_compare_session` has no extra-claim
  reverse check. Contradicts the both-directions directive in the new
  `src/limnalis/conformance/agents.md`.
- **MEDIUM-3** — pipe-span shielding covers only `_scan_top_level_matches`; `_split_top_level`,
  `_split_words`, `_is_wrapped_expression` still mis-parse spans (`p(|0:a,b|, c)` → two bogus
  SymbolTerms). The `_parse_core_expr_text` docstring's "every top-level scan" claim is wrong.
- **MEDIUM-4** — delimiter depth is never clamped at zero and operator swallowing from
  unbalanced delimiters produces no diagnostic (NORM-002 gap).
- **MEDIUM-5** — `run_case` injects `test://adequacy/compute_pass_v1` into live-pack adequacy
  handlers.
- **MEDIUM-6** — baseline materialization is untraced and runs once per (claim, evaluator).
- **MEDIUM-7** — JudgedExpr two-stage contract (§12.1) unimplemented; C1's flagship verdict is
  produced without evaluating the inner expression. Pre-existing code, newly load-bearing.
- **LOW-1/2/3** as listed above.
