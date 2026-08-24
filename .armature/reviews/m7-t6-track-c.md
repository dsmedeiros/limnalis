# Review Verdict: m7-t6-track-c

Milestone 7, Wave 3, Checkpoint 2 of 3 (task T6 — Track C paradox-forensics bundles).
PRD: `.taskmaster/docs/milestone-7-remediation-track-c.md` (Wave 3, T6 section).
Prior checkpoint: `.armature/reviews/m7-t5-extension-corpus.md` (T5, Track D, PASS_WITH_ADVISORIES,
committed at f23f44f). This review covers only the checkpoint-2 delta on top of f23f44f.

## Scope Compliance

- Governing file: `src/limnalis/conformance/agents.md` (added in the T5 commit f23f44f, closing
  that checkpoint's advisory #1 about the missing governance file — confirmed via
  `git log --follow`, single commit). Frontmatter: `invariants: [FIXTURE-001, SCHEMA-001]`,
  `restricted: [cross-cutting-changes, model-changes, vendored-corpus-changes]`.
- `git status --porcelain=v1 -uall` (working tree, re-verified at the end of review after all
  worktree/probe activity): exactly the six declared path groups —
  `M fixtures/limnalis_extension_corpus_v0.1.json`, `M fixtures/limnalis_extension_corpus_v0.1.yaml`,
  `M src/limnalis/conformance/runner.py`, `M src/limnalis/plugins/fixtures.py`,
  `M tests/test_extension_corpus.py`, plus four untracked `examples/paradox_*.lmn` files. No other
  paths touched. `git diff --stat f23f44f`: runner.py +11/-4 (net +7/-4 counting only the changed
  hunk), fixtures.py +456/-29, matching the stated line counts.
- Out-of-scope modifications: **none**. `src/limnalis/models/`, `src/limnalis/runtime/`,
  `src/limnalis/normalizer.py`, `src/limnalis/plugins/__init__.py`, `grammar/`, `schemas/`, `spec/`
  all untouched (confirmed via `git diff --stat f23f44f -- <dir>` returning empty for each).
  `CRITERION_BINDING`/`TRANSPORT_HANDLER` (imported fresh into `fixtures.py`) were already defined
  in `plugins/__init__.py` at f23f44f (lines 19, 23) — not a new cross-file addition.
- No `restricted` action present: no vendored-corpus edits (verified below), no model changes, and
  the `runner.py` touch is a narrowly-scoped 7-line bugfix, not cross-cutting.

## Deep verification performed

### 1. Algebra hand-verification (spec §4 / §8.3 / §10.2 / §16.6, `spec/Limnalis-v0.2.2.md`)

All values re-derived independently from the spec's pair-algebra text (`T=(1,0) F=(0,1) B=(1,1)
N=(0,0)`, `spec/Limnalis-v0.2.2.md:611-613`) and cross-checked against the (unmodified, pre-existing)
runtime implementation:

- **C1 flagship `{N,B}→F`**: block(meta) folds the evaluable set `{l1=N, l3=B}` (l0 note excluded).
  Hand-derived via componentwise AND (`t=min`, `f=max`): N=(0,0)∧B=(1,1) → t=min(0,1)=0,
  f=max(0,1)=1 → (0,1)=F. Matches `_fold_block_truth` (`src/limnalis/runtime/builtins.py:502-523`,
  unmodified) rule 2 exactly. Confirmed live via `run_case`/`compare_case` on case C1: zero
  mismatches; `step.per_block_aggregates["meta#1"].truth == "F"`.
- **C3 `paraconsistent_union({T,F})→B[evaluator_conflict]/conflicted`**: componentwise OR of
  T=(1,0),F=(0,1) → (1,1)=B. `_TRUTH_JOIN` table (`builtins.py:337-354`, unmodified) agrees for all
  16 pair combinations, independently re-derived by hand (not just read). Reason rule
  (`apply_resolution_policy`, `builtins.py:440-450`): T and F both present → `evaluator_conflict`;
  support forced `conflicted` (`_aggregate_support`, `builtins.py:384-389`, aggregate=B with both T
  and F present in the evaluator truth set). C3's per-evaluator-first block fold independently
  re-derived: ev_unitary folds `{T,T}→T`, ev_collapse folds `{F,T}→F`, then aggregate
  `paraconsistent_union({T,F})→B` — never aggregate-then-fold. Live run confirms:
  `per_block_per_evaluator["local#1"] = {ev_unitary: T, ev_collapse: F}`,
  `per_block_aggregates["local#1"].truth == "B"`.
- **C4 pair-join `{T,N}→T` and `{F,N}→F`**: componentwise OR: T=(1,0)∨N=(0,0)=(1,0)=T;
  F=(0,1)∨N=(0,0)=(0,1)=F. Both re-derived directly from the spec formula (not only from the code
  table). Reason inheritance (`unique_reasons` logic, `builtins.py:446-450`): with no T/F conflict,
  the single non-None per-evaluator reason (`missing_binding`, from `ev_zf`) is inherited onto the
  aggregate. Live run: c1 → `(T, missing_binding)`, c2 → `(F, missing_binding)`, both exact matches.
- **Degrade-transport pin `T→N[transport_loss]`, support partial** (C2 `q_core`, C3 `q_amplify`):
  read `_degrade_truth` (`builtins.py:2295-2310`) directly — `T→("N","transport_loss")`,
  `F→("N","transport_loss")`, `B→("B","boundary_mix")`, `N→("N",None)`, verbatim match to spec
  §10.2's default degradation rule. Support-forcing to `partial` on truth degradation confirmed at
  `builtins.py:2366-2368`. Both C2 (`infinite_density` requires `semiclassical_validity`, bridge
  loses `semiclassical_validity` → intersection non-empty) and C3 (`interference_pattern` requires
  `phase_coherence`, bridge loses `phase_coherence`) independently re-confirmed via
  `python -m limnalis normalize` on the actual example files: `c3.semanticRequirements ==
  ["semiclassical_validity"]`, `bridge.lose == ["semiclassical_validity"]` (C2); both `degraded`,
  `dstAggregate.truth=N`, `reason=transport_loss`, `support=partial` in the live run.

No algebra-wrong pin found in any of the four cases.

### 2. Audit of the seven sketch-deltas (corpus `ast_decisions`, `fixtures/limnalis_extension_corpus_v0.1.yaml:55-88`)

Enumerated exactly seven distinct, independently-checkable factual claims across the three new/
extended `ast_decisions` entries (a count that exactly matches "seven" — not an approximation):

| # | Claim | Location | Verification method | Result |
|---|---|---|---|---|
| A | Under `paraconsistent_union` with no T/F conflict, a unique evaluator-local reason is inherited onto the aggregate (C4 c1) | `:62-64` | Read `apply_resolution_policy` reason logic + hand-traced C4 c1 | TRUE |
| B | Anchor with zero adequacy records for the resolved task licenses `N[no_adequacy_result]` (C1 l1, C4 c2) | `:68-69` | Read `compose_license` (`builtins.py:1469-1477`) + traced both claims | TRUE |
| C | Score declared `N` + non-numeric method result → `N[missing_binding]` + `adequacy_method_binding_missing` diagnostic (C2 aa_core) | `:70-72` | Read `_evaluate_single_assessment` (`builtins.py:919-952`) line by line | TRUE |
| D | Spec-sketch spelling `N[not_yet_applicable]` does not occur in the implementation | `:72-74` | `grep -rn not_yet_applicable src/ --include=*.py` → zero hits | TRUE |
| E | `AssumptionNode` exists in the AST model and schema | `:77` | `models/ast.py:362-368` (class exists); schema `AssumptionNode` referenced at `schemas/limnalis_ast_schema_v0.2.2.json:573,1929` | TRUE |
| F | Normalizer has no assumption-block surface syntax (pre-existing gap); no runtime code modified for C4's workaround | `:77-81` | `grep -in assumption grammar/limnalis.lark normalizer.py` → zero hits; `git diff --stat f23f44f -- src/limnalis/runtime src/limnalis/normalizer.py` → empty | TRUE |
| G | Normalizer accepts only `\|0:ref\|`; `\|inf:finite_time\|` is not legal surface syntax | `:84-86` | `normalizer.py:1503-1508` (rejects `kind != "0"`) + **live probe**: `normalize_surface_text` on a snippet containing `\|inf:finite_time\|` raises `NormalizationError: invalid baseline reference '\|inf:finite_time\|'` | TRUE |

All seven are (a) true statements about the implementation, verified by direct code reading and/or
live execution (not by trusting the implementer's prose), and (b) documented explicitly in the
corpus's `ast_decisions` block as implementation-vocabulary pins with citations to the specific
affected cases — none is silently substituted into an `expected:` block without disclosure. Spot
probes additionally confirmed spec §12.1's JudgedExpr rule ("if the criterion binding is missing or
unresolved, result is N[missing_binding]") and non-self-reference correctness (see §4 below), which
are consistent with but not literally among the seven corpus-documented deltas — no divergence found
there either.

### 3. The runner hunk (`src/limnalis/conformance/runner.py:826-833`, +7/-4)

Replaces an unconditional clobber (`services["adequacy_handlers"] = {...}`) with
`services.setdefault("adequacy_handlers", {}).setdefault("test://adequacy/compute_pass_v1", ...)`.
Verified three ways:

1. **Byte-identical vendored proof, reproduced independently.** Created a disposable `git worktree`
   at f23f44f, ran `python -m limnalis conformance report --format json` there and in the current
   tree, `diff`'d the two outputs: **zero bytes of difference**. (Editable-install pointer was
   correctly restored to the main tree afterward and re-verified via
   `python3 -c "import limnalis; print(limnalis.__file__)"`.) This is the strongest available proof
   that vendored-case behavior is unchanged — stronger than re-running `conformance run` alone,
   since it diffs the full structured result, not just pass/fail.
2. **Vendored 16/16 unaffected.** `python -m limnalis conformance run` (vendored corpus, the only
   corpus this CLI command touches — confirmed via `_run_conformance_report`/`_run_conformance_run`
   using `load_corpus_from_default()` with no `--corpus` override): 16 passed, 0 failed, 0 errors,
   including A6, A12, B1, B2 explicitly — and since the full JSON report is byte-identical (point 1),
   every one of the 16 cases' results, not just these four, is provably unchanged.
3. **Live-pack merge probe (both pack methods and runner-provided handler present).** Wrote a script
   that builds `build_live_fixture_services(bundle)` for case C2 (which registers
   `test://paradox/method/gw_waveforms_v1` and `test://paradox/method/qg_tbd_v1` as
   `ADEQUACY_METHOD` handlers), then applies the exact runner merge sequence. Result: all three keys
   (`gw_waveforms_v1`, `qg_tbd_v1`, and the vendored `compute_pass_v1`) coexist in
   `services["adequacy_handlers"]`; the pack handlers are unclobbered (`gw_waveforms_v1(None) ==
   0.99`) and the vendored default is present and correct (`compute_pass_v1(None) == 1.0`). Note:
   `test://adequacy/compute_pass_v1` is referenced only by the vendored A12 case
   (`grep` confirms), so no live-pack case in this corpus exercises both simultaneously in
   production — this scenario was probed synthetically as instructed, and the merge mechanism is
   sound. The comment at `runner.py:826-830` accurately states "for vendored cases services is
   empty at this point" — confirmed by reading `run_case` (`services: dict[str, Any] = {}` at
   `runner.py:806`, only mutated by `services.update(live_services)` when
   `build_live_fixture_services` returns non-`None`).

### 4. Pack surface probes (executed, not just read)

- **Unregistered criterion → `N[missing_binding]`** (spec §12.1 / vendored A13 semantics): live
  probe with a `judged_by test://not/a/registered/criterion` claim through the liar_v1 evaluator
  bundle → `truth="N", reason="missing_binding"`. Matches `JudgedCriterionEvalHandler`
  (`fixtures.py:808-838`) and spec §12.1 exactly.
- **Tarski gate: non-self-referential claim must NOT get `B[self_reference]`**: live probe with
  `p1: refers_to_itself(p2) judged_by test://paradox/criterion/tarski_gate_v1;` (p1 references a
  *different* claim, p2, not itself) → `truth="T"`, reason `None` — confirmed the gate does **not**
  fire on cross-references, only on genuine self-reference (own claim id appearing among the judged
  inner expression's symbol arguments — `tarski_self_reference_criterion`, `fixtures.py:768-806`,
  walks `SymbolTermNode.value`, confirmed via normalized-AST inspection that `refers_to_itself(l3)`
  parses `l3` as `SymbolTermNode(value="l3")`, so the walk finds it).
- **`zf_v1` deterministic `N[missing_binding]`**: `_ZF_V1_TRUTHS` (`fixtures.py:750-753`) is a static
  dict with no I/O or randomness — inherently deterministic by construction. Independently confirmed
  via two separate `python3` process invocations of the full extension-corpus run (see §6) producing
  byte-identical `model_dump()` output, including C4's `ev_zf` results.
- **Via-URIs never invoked**: `grep -n "TRANSPORT_HANDLER\|transport_handler" src/limnalis/runtime/*.py`
  → **zero matches**. Confirmed structurally: `execute_transport` (`builtins.py:1975`) dispatches
  `degrade` mode to `_execute_degrade(bridge, src_aggregate, semantic_requirements, metadata,
  claim_id, diags)` (`builtins.py:2170-2173`) — note the signature does not even receive `services`,
  so it is structurally incapable of looking up a services-registered handler. `bridge.via` is used
  only as a provenance string (`builtins.py:2336, 2343, 2374, 2381`). The `_bridge_via_marker`
  registration (`fixtures.py:885-902`) is therefore correctly characterized in its own docstring as
  a documentation-only marker. (Minor architecture observation, non-blocking: `CRITERION_BINDING`
  registry entries, similarly, are registered for pattern-consistency but not actually consulted at
  dispatch time — `JudgedCriterionEvalHandler` bakes `_LIVE_CRITERION_BINDINGS` directly into the
  handler instance at construction rather than querying the registry. No behavioral risk today since
  both derive from the same module-level dict, but worth knowing if a future case tries to register
  a *runtime-added* criterion binding expecting the registry alone to be authoritative.)

### 5. Examples

Independently re-verified outside of pytest: a standalone script compared each `examples/paradox_*.lmn`
file's exact bytes against `case.source + "\n"` for all four corpus cases — all four **MATCH**.
`python -m limnalis normalize` invoked directly (not via the test's `main()` call) on all four files
— all four exit 0 with no stderr output. `python -m limnalis parse` also independently exercised on
`paradox_liar.lmn` and its normalized JSON manually inspected: confirms `false(liar_sentence)` parses
as `PredicateExpr(name="false", ...)` (not misparsed as the `false` boolean literal — the boolean
keyword handling only applies to bare-identifier *arguments*, not predicate names) and
`refers_to_itself(l3)` correctly nests as `JudgedExpr(expr=PredicateExpr(...,
args=[SymbolTerm(value="l3")]), criterionRef=...)`.

### 6. Standard gates (all independently reproduced, not read from the implementer's report)

- Extension corpus schema validation: 0 errors both twins (pytest `TestExtensionCorpusSchema`, 3/3
  pass) + YAML/JSON twin parity (`yaml_data == json_data` exact equality, `TestExtensionCorpusTwinParity`,
  2/2 pass).
- 10/10 cases PASS, zero mismatches: independently re-verified with a standalone script (bypassing
  pytest) calling `load_corpus`+`run_case`+`compare_case` directly on all ten case ids (D1-D6,
  C1-C4) — all ten report `error=None, passed=True, mismatches=0`.
- Cross-process determinism: the same script run as two **separate** `python3` process invocations,
  outputs (including full `bundle_result.model_dump()` for every case) diffed — **zero bytes of
  difference**.
- Vendored 16/16: `python -m limnalis conformance run` → "Results: 16 passed, 0 failed, 0 errors out
  of 16 cases".
- Vendored byte-unchanged: `sha256sum` of both `fixtures/limnalis_fixture_corpus_v0.2.2.{yaml,json}`
  matches `git show HEAD:<path> | sha256sum` exactly for both files; `git status`/`git diff --stat`
  confirm zero changes to `schemas/` or `spec/`.
- Full suite: `python -m pytest tests/ -q` → exit code 0, exactly **1021** dots (verified by counting
  `.` characters directly since this environment's pytest run does not print its usual terminal
  summary line — an environment quirk unrelated to the changeset; exit code 0 and dot-count give
  equivalent assurance), matching the acceptance criterion's expected count exactly. No `F`/`E`
  markers anywhere in the output.
- Scope: confirmed exactly the six declared path groups (see Scope Compliance above), re-verified
  after all worktree/probe cleanup.

### 7. Content sanity (read the four case sources as documents)

- **C1**: `a_liar_truth` anchor is `subtype placeholder`, `status active`, with **no** `adequacy`
  block at all (confirmed in both the corpus source and the normalized AST: `"adequacy": []`) —
  correctly encodes "placeholder anchor carrying no assessments." `l0` note text literally quotes
  the liar sentence and is marked non-evaluable/excluded. `l3`'s criterion correctly targets its own
  id (`refers_to_itself(l3) judged_by ...`) inside claim `l3` itself — genuine self-reference, not a
  forward/back reference to a different claim.
- **C2**: `c3` declares `requires [semiclassical_validity]` and the bridge declares
  `lose [semiclassical_validity]` — confirmed identical string, non-empty intersection, via direct
  normalized-AST inspection (not just reading the YAML).
- **C4**: `a_choice` anchor (`subtype placeholder`, `status active`, `adequacy: []`) plus meta note
  `m1` whose text explicitly states "ASSUMPTION (active): axiom_of_choice ... recorded as the active
  placeholder anchor a_choice because the surface grammar has no assumption-block form" — accurately
  self-documenting the workaround in-bundle, not just in the corpus's `ast_decisions`.
- Focus tags and titles cross-checked against actual case mechanics for all four cases (self_reference,
  N_and_B_equals_F for C1; adequacy_assessment, score_not_computable, degrade_transport for C2;
  multi_evaluator, paraconsistent_union, evaluator_conflict, block_fold_order for C3;
  assumption_disclosure, choice_dependence, missing_binding, proxy_anchor_license, note_only_block
  for C4) — all accurate, none overstated or missing an obviously-warranted tag.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| FIXTURE-001 (Fixture Conformance Authority) | PASS | All four Track C expectations independently hand-derived from spec §4/§8.3/§10.2/§12.1 pair-algebra formulas (not merely read from code) and cross-checked against live execution; zero mismatches, cross-process deterministic. |
| SCHEMA-001 / SCHEMA-004 (schema validation) | PASS | Both corpus twins validate with 0 errors against the vendored schema, independently reproduced; AST schema untouched (no `models/` changes). |
| FIXTURE-003 (JSON-YAML Equivalence) | PASS | `yaml_data == json_data` exact equality, reproduced. |
| NORM-001 (Normalizer Determinism)-adjacent | PASS | `normalizer.py` untouched; exercised (not modified) through 4 new bundles, cross-process-deterministic. |
| Vendored-corpus immutability (`restricted: vendored-corpus-changes`) | PASS | `fixtures/limnalis_fixture_corpus_v0.2.2.{yaml,json}` byte-identical to `git show HEAD:` (sha256 match); `schemas/`, `spec/` untouched. |
| Vendored-behavior stability (conformance/agents.md directive) | PASS | Byte-identical `conformance report --format json` diff against a disposable worktree at f23f44f; 16/16 vendored PASS. |
| Cross-cutting-changes / model-changes (restricted) | PASS | `runner.py` touch is a narrowly-scoped 7-line fix; `src/limnalis/models/`, `src/limnalis/runtime/` untouched. |

## Verdict: PASS_WITH_ADVISORIES

No FAIL findings. Every algebra-determined expectation in C1-C4 was independently re-derived from
the spec's pair-algebra and transport-degradation formulas (not merely read from the implementer's
docstrings or trusted from passing tests), and matches. All seven identified sketch-deltas are true
statements about the implementation, verified by direct execution/grep, and are documented in the
corpus as implementation-vocabulary pins rather than silently substituted — this includes the
`not_yet_applicable` vocabulary gap, confirmed genuinely absent from `src/` by exhaustive grep. The
runner hunk was proven behavior-preserving for vendored cases by the strongest available method (a
byte-identical structured-report diff against the actual pre-checkpoint commit) and the merge
mechanism was proven sound for the "both pack and runner handlers present" case via a synthetic
probe. Criterion dispatch, self-reference detection (including the negative case — a
non-self-referential judged claim correctly does *not* trigger `B[self_reference]`), and the
via-URI-never-invoked claim were all confirmed by direct execution and by grepping the runtime for
the complete absence of a `TRANSPORT_HANDLER` lookup path, not merely by reading fixtures.py's
docstrings. All example files are byte-identical to their corpus sources and independently
normalize cleanly via the CLI. All standard gates (schema, parity, 10/10, cross-process determinism,
vendored 16/16 + byte-immutability, full suite at exactly 1021, exact scope) were independently
reproduced rather than read from the implementer's report.

This checkpoint also correctly actioned both advisories from the prior checkpoint's review
(`m7-t5-extension-corpus.md`): advisory #1 (missing `conformance/agents.md`) was resolved in the T5
commit itself and is now the governing file for this review; advisory #2 (forward note that T6 would
need `TRANSPORT_HANDLER`/`CRITERION_BINDING` registration blocks and a broader
`build_live_fixture_services` activation gate) was implemented essentially as anticipated.

### Advisories (not blocking)

1. **Minor mypy delta, non-CI-gated.** `python -m mypy src/limnalis/plugins/fixtures.py
   src/limnalis/conformance/runner.py` reports 23 errors post-checkpoint vs. 22 at f23f44f (verified
   via the same disposable-worktree technique). The one new occurrence
   (`fixtures.py:762`, inside the new `DynamicTruthEvalHandler.__call__`) is the exact same
   pre-existing class of error (`str` assigned where a `Literal['T','F','B','N']` is expected) that
   already appears 9 times in the unmodified baseline — the new handler faithfully mirrors
   `AtomTruthEvalHandler`'s existing (accepted) idiom rather than introducing a new pattern. `mypy`
   is not part of `.github/workflows/ci.yml` (which runs only `pytest`) and `[tool.mypy]` is
   `strict = false`, so this is not a gate violation — flagged for hygiene awareness only.
2. **Registry/dispatch redundancy for `CRITERION_BINDING`.** `register_extension_fixture_plugins`
   registers judged-criterion callables under the registry's `CRITERION_BINDING` kind
   (`fixtures.py:1075-1084`), but `JudgedCriterionEvalHandler` never queries that registry kind at
   evaluation time — it is constructed with `_LIVE_CRITERION_BINDINGS` baked in directly
   (`fixtures.py:346-354` factory wiring). No behavioral risk today (same source dict, no drift
   possible), but the registry registration is currently decorative rather than load-bearing for
   dispatch; worth knowing before a future case assumes registering under `CRITERION_BINDING` alone
   is sufficient to wire a new criterion.
3. **Guidance for T7 (gallery doc) — please read before drafting `docs/paradox_gallery.md`:**
   - State plainly that the license/adequacy reason vocabulary shown in the gallery
     (`N[no_adequacy_result]`, `N[missing_binding]` for a declared-`N`-score assessment with a
     non-numeric method result) is the **reference implementation's** reason taxonomy, and that it
     diverges from the consolidated spec §9.2 prose's literal `N[not_yet_applicable]` spelling for a
     declared score of `N`. Do not present the gallery's C1/C2/C4 license outcomes as if they were
     the spec's literal reason-code spelling — cite this as a known, documented vocabulary pin (per
     `ast_decisions`), not silently.
   - Describe C4's axiom-of-choice disclosure as what it actually is: an **active placeholder anchor
     plus a meta note**, not a first-class `Assumption` declaration — the surface grammar has no
     assumption-block form (confirmed: zero occurrences of "assumption" in `grammar/limnalis.lark`
     or `normalizer.py`). If the doc discusses "assumption disclosure" as a Limnalis language
     feature, it must be precise that this is a workaround, not native syntax.
   - Describe C2's "declared unboundedness" via the DynamicExpr encoding actually used
     (`curvature --> divergence_within_finite_time`, `op=approaches`), not via a symbolic-infinity
     baseline reference — `|inf:finite_time|` is not legal surface syntax (baseline refs are fixed
     at offset 0; verified by a live `NormalizationError` probe).
   - When narrating C4's "choice-dependence disclosure" (aggregate T carrying the ZF evaluator's
     `missing_binding` reason), be precise that this happens because `paraconsistent_union`'s reason
     rule inherits a *unique* per-evaluator reason when there is no T/F conflict — a general
     resolution-policy mechanism, not a Track-C-specific feature — to avoid implying bespoke paradox
     handling that doesn't exist.
   - Do not describe the bridge `via` URIs (`test://paradox/bridge/naive_extrapolation_v1`,
     `.../amplification_v1`) as "executed" or "invoked" — `execute_transport` implements
     `degrade`/`preserve`/`metadata_only` entirely internally and never calls a transport handler for
     those modes (confirmed: zero references to a transport-handler services lookup anywhere in
     `src/limnalis/runtime/*.py`); the `via` URI is carried only as provenance metadata.

## Rollback Recommendation: NO

No invariant violation, no incorrect algebra pin, no undisclosed spec divergence, no scope
violation, no regression against the actual pre-checkpoint commit (byte-identical vendored
conformance report, byte-identical vendored corpus files). Proceed to commit and to checkpoint 3
(T7, gallery documentation). The three advisories above are non-blocking; the third is guidance for
the *next* checkpoint's content, not a required change to this one.
