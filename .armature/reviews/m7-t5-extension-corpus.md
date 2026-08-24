# Review Verdict: m7-t5-extension-corpus

Milestone 7, Wave 3, Checkpoint 1 of 2 (task T5 — extension corpus Track D coverage cases).
PRD: `.taskmaster/docs/milestone-7-remediation-track-c.md` (Wave 3, T5 section).

## Scope Compliance

- Declared scope (PRD T5 line): new `fixtures/limnalis_extension_corpus_v0.1.yaml` + fixture
  bindings in `src/limnalis/plugins/fixtures.py` + tests.
- `git status --porcelain` (working tree): exactly five paths —
  `M  src/limnalis/conformance/runner.py`
  `M  src/limnalis/plugins/fixtures.py`
  `?? fixtures/limnalis_extension_corpus_v0.1.json`
  `?? fixtures/limnalis_extension_corpus_v0.1.yaml`
  `?? tests/test_extension_corpus.py`
  No other paths modified. `git diff HEAD --numstat`: `runner.py` +18/-0, `fixtures.py` +280/-0 —
  matches the checkpoint's stated line counts exactly.
- Out-of-scope modifications: **none**. Vendored `fixtures/`, `schemas/`, `spec/` byte-identity
  independently re-verified (`sha256sum` working tree vs. `git show HEAD:<path>`) for all 7
  vendored artifacts (both vendored corpus twins, all 3 schemas, both spec editions) — all `OK`,
  zero diffs.
- `src/limnalis/models/` and `src/limnalis/runtime/` untouched (confirmed via `git status`) — no
  restricted `model-changes` action from `src/limnalis/agents.md`'s `restricted` list.
- One process note (not a violation, consistent with a pre-existing gap): the PRD's T5 scope line
  names `src/limnalis/plugins/fixtures.py` but not `src/limnalis/conformance/runner.py`, unlike
  T3's line which explicitly authorized that file. There is still no dedicated
  `src/limnalis/conformance/agents.md` or `src/limnalis/plugins/agents.md` — the same gap flagged
  as advisory #2 in `.armature/reviews/m7-t3-t4-session-semantics.md`, now a second checkpoint
  touching `conformance/runner.py` without a governing file. The touch itself
  (`runner.py:808-824`) is minimal, additive, and falls within `src/limnalis/agents.md`'s scope
  (`src/limnalis/` excluding `models/`/`runtime/`) and the `limnalis-core-impl.md` persona's
  authority. Not blocking; see Advisory 1.

## Deep verification performed

### 1. Hand + machine re-derivation of every D1–D4 truth value (spec §4, `spec/Limnalis-v0.2.2.md:611-642`)

Re-derived every expectation independently by hand from the pair algebra (`T=(1,0) F=(0,1)
B=(1,1) N=(0,0)`), then re-derived a second time by calling the actual runtime functions
(`_truth_and`/`_truth_or`/`_truth_flip`, `src/limnalis/runtime/builtins.py:1623-1659`) from a
throwaway script — both methods agree with each other and with every value pinned in
`fixtures/limnalis_extension_corpus_v0.1.yaml`:

- D1 (`:122-215`): `b AND n`=F (flagship B∧N=F), `t AND b`=B, `t AND n`=N, `f OR n`=N. Block fold
  (AND across F,B,N,N) = F. All match.
- D2 (`:216-297`): `b OR n`=T, `NOT b`=B (fixed point), `NOT n`=N (fixed point). Block fold over
  T,B,N = F (the B∧N=F rule reappears transitively through 3-way AND fold; associativity checked
  both orderings by hand, same result). All match.
- D3 (`:298-366`): `b -> n` = ¬B∨N = B∨N = T; `b <=> n` = (b→n)∧(n→b) = T∧T = T. Canonical `->`/`<=>`
  spellings pinned in source (`:326-327`) and asserted as `op=implies`/`op=iff` in
  `tests/test_extension_corpus.py:170-173`. All match.
- D4 (`:367-451`), the precedence-discrimination cases — computed both trees for each claim using
  the real `_truth_and`/`_truth_or`:
  - `t AND f OR t` (c1): correct `OR(AND(t,f),t)`=T, inverted `AND(t,OR(f,t))`=T — both trees agree,
    so c1 exercises only the AST tree-shape pin (`tests/test_extension_corpus.py:188-192`), not a
    truth-level discriminator, exactly as the corpus's own `normalized_ast_expectations` note
    states (`:404-406`).
  - `f AND t OR t` (c2): correct `OR(AND(f,t),t)`=**T**, inverted `AND(f,OR(t,t))`=**F**. Corpus
    expects T (`:426-433`) — the *correct* value. Matches the checkpoint's explicit claim exactly.
  - `n OR t AND b` (c3): correct `OR(n,AND(t,b))`=**T**, inverted `AND(OR(n,t),b)`=**B**. Corpus
    expects T (`:434-441`) — the *correct* value, and a second discriminator that also exercises
    B/N in the pair algebra. Matches the checkpoint's explicit claim exactly.
  Block fold (AND across T,T,T) = T, matches.
  No wrong expected value found anywhere in D1–D4.

### 2. D5 vs. the consolidated spec's A11 narrative (`spec/Limnalis-v0.2.2.md:1900-1921`, §16.2.1 at `:1444-1463`)

Quoted the spec narrative verbatim and compared field-by-field against
`fixtures/limnalis_extension_corpus_v0.1.yaml:452-652`:

- Fixture semantics: `test://baseline/by_context_v1` returns 10 at (t1, regime=nominal) and 20 at
  (t2, regime=stress); `sensor_A` fixed at 10 — reproduced exactly in the corpus's fixture
  `behavior.contexts` (`:99-105`) and in the handler's `_BY_CONTEXT_V1_VALUES` table
  (`src/limnalis/plugins/fixtures.py:510-513`).
  Session/step shapes: `s_shared`/`s_isolated`, each with steps `s1`(t1,regime=nominal) /
  `s2`(t2,regime=stress) — matches `:500-538` exactly.
- All eight expected claim values checked against the spec's stated expectations
  (`spec:1917,1920`) one by one — **all eight match exactly**:
  s_shared s1: c_fixed=T, c_step=T (`:560-575`) ✓; s_shared s2: c_fixed=T (cached), c_step=F
  (re-resolved) (`:583-598`) ✓; s_isolated s1: c_fixed=T, c_step=T (`:607-623`) ✓; s_isolated s2:
  c_fixed=F (reinitialized), c_step=F (`:631-646`) ✓. Block folds (AND of the two claims per
  step) also independently re-derived and match (`T∧T=T`, `T∧F=F`, `F∧F=F`).
- Baseline-frame/regime subtlety: read `materialize_referenced_baselines`
  (`src/limnalis/runtime/builtins.py:724-857`) directly. The baseline-local overlay is
  `_merge_frame_facets(step_ctx.effective_frame, baseline_node.frame)` (`:797-800`), and
  `_merge_frame_facets` is "later values override earlier ones, only when non-None" (`:104-114`).
  `b_fixed`/`b_step`'s declared frame is `@{system=Test, namespace=Baseline}` (no `regime`
  facet) — so the overlay leaves `regime` exactly as it was in `step_ctx.effective_frame`, which
  is itself `merge(bundle.frame, session.base_frame, step.frame_override)`
  (`build_step_context`, `:138-153`) — i.e. the step's `frame_override` regime survives untouched
  into the resolver call. This is a byte-for-byte match to spec §16.2.1's stated overlay rule
  ("A baseline's own frame field overlays the effective step frame for that baseline's resolution
  only… does not mutate the effective step frame used by other baselines or claims",
  `spec:1456-1458`) and confirms the implementer's documented rationale
  (`fixtures/limnalis_extension_corpus_v0.1.yaml:541-543`) is sound, not just asserted. This
  machinery is pre-existing (already reviewed/PASSed in `.armature/reviews/m7-t3-t4-session-semantics.md`)
  — T5 only makes it reachable through new, real bindings; it does not reimplement it.
- `expected.baseline_states` (`:552-554`) is genuinely enforced, not decorative —
  `src/limnalis/conformance/compare.py:536-540` calls `_compare_baseline_states` whenever the key
  is present.

### 3. Conformance runner wiring (`src/limnalis/conformance/runner.py:808-824`, the +18-line hunk)

Read closely: `build_live_fixture_services(bundle)` (`src/limnalis/plugins/fixtures.py:718-749`)
returns `None` unless the bundle declares ≥1 evaluator **and every** evaluator's binding URI is
in `_LIVE_EVALUATOR_HANDLER_FACTORIES` (`:647-650`, currently `{ATOMS_V2_URI,
BASELINE_MATCH_V1_URI}`); only then does `runner.py:822-824` swap in a bare `PrimitiveSet()`
(all-real-builtins default, `src/limnalis/runtime/runner.py:71-90`) and merge `live_services` into
the per-call-local `services` dict. Adversarial probes (`PYTHONPATH=src python3`, scratch scripts):

- **Mixed bundle** (one evaluator bound to `test://eval/atoms_v2`, a second to
  `test://eval/atoms_v1`, both normalized through the real Lark/normalizer pipeline, not
  synthetic): `build_live_fixture_services` returns `None`, confirmed live. Ran the same mixed
  bundle end-to-end through `run_case` with a synthetic expectation: it fell back cleanly to the
  claim-id-keyed fixture-echo path with no crash and no partial live activation for either
  evaluator — exactly the pre-existing vendored behavior shape.
- **Vendored case** (A3, which exercises logical composition): `build_live_fixture_services`
  returns `None` (its sole evaluator binds `test://eval/atoms_v1`). Grepped every `binding:` URI
  in the vendored corpus (`fixtures/limnalis_fixture_corpus_v0.2.2.yaml`) — none collides with
  either live-pack URI, so all 16 vendored cases are guaranteed `None` by construction, not
  merely by accident.
- **Byte-identical proof against the actual pre-checkpoint commit**: created a detached
  `git worktree` at `HEAD` (commit `19a5077`, before this checkpoint's changes), ran
  `limnalis conformance report --format json` there and in the current working tree, and `diff`'d
  the two JSON reports — **byte-identical**, zero differences. This is strictly stronger than an
  in-process before/after comparison: it proves the wiring change has zero observable effect on
  the vendored corpus relative to the actual prior commit, not just relative to itself.
- **Extension case** (D1): `build_live_fixture_services` returns a dict with `evaluator_bindings`
  (D1 has no baselines, so no `baseline_criterion_resolver` key — correctly conditional,
  `fixtures.py:745-748`), confirmed live activation.
- **State pollution**: interleaved `run_case` calls (A3 → A4 → A11 → D1 → D5 → D6 → A3 → A4 → A11
  again, all in one Python process) and compared `model_dump()` of the vendored cases before vs.
  after the extension cases ran between them — **identical**. Re-ran the full 16-case vendored
  corpus a second time in the same process, immediately after the extension cases — **16/16
  PASS**. `services`/`primitives` are function-local to each `run_case` call
  (`runner.py:806,794-797`); the only module-level state in `fixtures.py` (`_ATOMS_V2_TRUTHS`,
  `_BY_CONTEXT_V1_VALUES`, `_LIVE_EVALUATOR_HANDLER_FACTORIES`, `_LIVE_BASELINE_RESOLVERS`) is
  read-only, never mutated. No leakage found by construction or by direct probing.
- `BASELINE_HANDLER` usage (`fixtures.py:709-715,741-748`) correctly follows the pre-existing
  "registry-only, not auto-wired" contract documented at
  `src/limnalis/plugins/__init__.py:214-220` — no duplication or conflict with
  `build_services_from_registry`'s auto-wired kinds.

### 4. Canary quality (`tests/test_extension_corpus.py:291-361`, `TestAtomLevelCanary`, 3 tests)

Ran all three; all pass. Independently re-ran the tamper canary manually outside pytest with full
mismatch detail: swapping D1's `c1: (b AND n);` for `c1: (t OR t);` while keeping the stated
expectation F makes the runner compute **T** (`per_claim_aggregates["c1"].truth == "T"`), and
`compare_case` genuinely fails with two concrete mismatches
(`sessions[0].steps[0].claims.c1.per_evaluator.ev0.truth: expected='F', actual='T'` and the
matching `.aggregate.truth` line) — this is real content divergence, not a vacuous pass. Read
`AtomTruthEvalHandler.__call__` (`fixtures.py:529-549`): it dispatches on `getattr(expr, "name",
None)` — the leaf `PredicateExprNode.name` — confirming atoms_v2 keys on predicate **names**,
never on claim ids, exactly as claimed.

### 5. Schema + parity

Ran `collect_validation_errors` against both twins directly: **0 errors** for the YAML and **0
errors** for the JSON, against `schemas/limnalis_fixture_corpus_schema_v0.2.2.json`. `yaml_data ==
json_data` (direct Python comparison): **True**. Read the schema's `ConformanceCase.track`
definition directly: `{"type": "string", "enum": ["A", "B"]}` — genuinely forbids any value other
than `"A"`/`"B"`; `id` has no pattern constraint (`{"type": "string"}`), so the `D1..D6` prefix is
legal. The track-A decision is documented in both `meta.purpose` (`:17-29`) and a dedicated
`ast_decisions` entry (`:42-50`), as claimed.

### 6. Immutability + suite

- Hashed all 7 vendored artifacts (both corpus twins, 3 schemas, 2 spec editions) against
  `git show HEAD:<path>` — all `OK`, zero diffs.
- Full suite: `python3 -m pytest tests/ -q` — this environment's pytest does not print a final
  textual summary line (verified this is an environment-wide quirk, not specific to this run: the
  same truncation occurs on `--collect-only` too, and exit code is consistently 0), so verification
  was done by counting status characters directly from the raw log: **1015 `.` characters, 0
  `F`/`E`/`s`, exit code 0** — matches the checkpoint's stated "expect 1015 passed" exactly
  (998 prior + 17 new). `tests/test_extension_corpus.py -v` run in isolation: **17 passed**
  (matches the stated test count exactly).
- `python3 -m limnalis conformance run`: **16 passed, 0 failed, 0 errors out of 16** (all A1–A14,
  B1–B2 individually listed PASS).
- Determinism: ran the extension corpus's own `test_extension_results_are_deterministic`
  (passes), plus an independent 10-iterations-per-case script (not reusing the implementer's test
  code) comparing `model_dump()` across runs for all six D1–D6 cases — **1 distinct result per
  case across 10 runs**, for all six.

### 7. Scope

`git status --porcelain` shows exactly the five stated paths (see Scope Compliance above).

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| FIXTURE-001 (Fixture Conformance Authority) | PASS | Every D1–D6 expected value independently re-derived by hand and via the real runtime pair-algebra functions; all match spec §4/§16.2.1/§17.2 exactly. Tamper canary proves the corpus computes rather than echoes. This corpus exists specifically to close FIXTURE-001's documented blind spots (`.armature/journal.md`, 2026-08-23 entries) and does so correctly. |
| SCHEMA-004 (Fixture Corpus Schema Validation) | PASS | Both YAML and JSON twins validate with 0 errors against the vendored schema, independently reproduced. |
| FIXTURE-003 (JSON-YAML Equivalence) | PASS | `yaml_data == json_data` confirmed by direct parse comparison; also confirmed by `TestExtensionCorpusTwinParity` (2 tests). |
| FIXTURE-002 (Fixture Version Alignment) | N/A | The corpus is explicitly and legitimately independently versioned (`version: v0.1`, "PROJECT-AUTHORED (not a vendored artifact)", `fixtures/limnalis_extension_corpus_v0.1.yaml:1-14`) — it validates against the v0.2.2 schema but does not claim to *be* the v0.2.2 vendored corpus. `tests/test_packaging_resources.py` (FIXTURE-002's `enforced-by`) contains zero version-alignment assertions of any kind (grepped for "version": no matches), so no enforcement mechanism is at risk either way. |
| NORM-001 (Normalizer Determinism) | PASS | `src/limnalis/normalizer.py` untouched by this diff; exercised (not modified) via 6 new surface sources routed through `normalize_surface_text`, confirmed deterministic across 10 independent runs per case. |
| SCHEMA-001 (AST Schema Validation) | N/A | No AST/schema surface touched; `src/limnalis/models/` untouched. |
| RUNTIME-004 (PrimitiveSet Injection) | PASS | The new code's only runtime touch is instantiating a bare `PrimitiveSet()` (`runner.py:823`) — still exactly the 13 real-builtin-default fields, no 14th primitive, no shape change. `src/limnalis/runtime/` itself is untouched by this diff. |
| MODEL-001 / MODEL-002 | N/A | `src/limnalis/models/` untouched. |

## Verdict: PASS_WITH_ADVISORIES

No FAIL findings. Every expected truth value in D1–D6 was independently re-derived twice (by hand
and via the live runtime algebra functions) and matches the spec exactly, including both
precedence-discriminating cases (`f AND t OR t` = T correct / F inverted; `n OR t AND b` = T
correct / B inverted) called out explicitly in the checkpoint request. D5's eight expected claim
values match the consolidated spec's A11 narrative exactly, and the baseline-frame/regime overlay
subtlety was verified sound by reading the actual merge implementation, not just trusting the
implementer's docstring. The conformance runner wiring — the highest-risk hunk — was proven safe
by the strongest available method: a byte-identical JSON conformance report diff against the
actual pre-checkpoint commit (via a disposable `git worktree`), plus adversarial mixed-binding and
state-pollution probes that all behaved correctly. All three canaries pass and the tamper canary
produces genuine, specific mismatches. Schema validation, JSON/YAML parity, vendored-artifact
byte-immutability, the full suite (1015), vendored conformance (16/16), and determinism were all
independently reproduced, not merely read from the diff or trusted from the implementer's own
tests.

### Advisories (not blocking)

1. **Governance-hygiene gap, now spanning two checkpoints.** No `src/limnalis/conformance/agents.md`
   or `src/limnalis/plugins/agents.md` exists. T3/T4 touched `conformance/runner.py` under this
   same gap (flagged as advisory #2 in `.armature/reviews/m7-t3-t4-session-semantics.md`); this
   checkpoint touches it again, and the PRD's own T5 scope line does not name it explicitly (unlike
   T3's line, which did). The touch here is small, additive, and well-isolated, so not blocking —
   but a third touch is likely: T6 (Track C paradox bundles) will almost certainly need to extend
   `conformance/runner.py` and/or `plugins/fixtures.py` further for bridge/transport and
   criterion-binding live wiring (see Advisory 2). Authoring `conformance/agents.md` before T6
   starts would be cheaper than doing it after a third ungoverned touch.
2. **Forward architecture note for T6 (Track C paradox bundles).** The live-pack registration
   surface added here — `register_extension_fixture_plugins` and `build_live_fixture_services`
   (`src/limnalis/plugins/fixtures.py:677-749`) — only wires `EVALUATOR_BINDING` and
   `BASELINE_HANDLER` kinds, and the activation gate (`build_live_fixture_services:730-735`) only
   inspects `bundle.evaluators`. Per the PRD, T6's C2/C3 need degrade/remap bridge transport, C1
   needs a self-reference criterion binding (`CriterionBindingContract`/`JudgedExpr` dispatch), and
   C4 needs joint adequacy — none of which the current registration surface or activation gate
   accounts for. This is not a defect in this checkpoint (T5's PRD scope is D1–D6 only, and it
   correctly does not attempt bridge/criterion wiring), but flagging it now lets the T6 implementer
   decide deliberately whether to broaden `build_live_fixture_services`'s gate and add
   `TRANSPORT_HANDLER`/`CRITERION_BINDING` registration blocks to
   `register_extension_fixture_plugins` following the same pattern, rather than discovering the gap
   mid-checkpoint and retrofitting it.

## Rollback Recommendation: NO

No invariant violation, no incorrect expected value, no scope violation, no regression against the
actual pre-checkpoint commit (byte-identical vendored conformance report). Proceed to commit and to
checkpoint 2 (T6). The two advisories are non-blocking, forward-looking notes for the next
checkpoint's design, not required changes to this one.
