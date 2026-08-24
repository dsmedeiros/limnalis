# Review Verdict: m7-t7-gallery-doc

Milestone 7, Wave 3, CHECKPOINT 3 (task T7 — paradox gallery doc). Reviewed against
HEAD `824142e` (m7/t6: Track C paradox-forensics cases). Documentation-accuracy
checkpoint; review centers on factual correctness against the pinned conformance
corpus, the spec, and live pipeline behavior, per the checkpoint brief.

## Scope Compliance

- Declared scope: `docs/` (no `agents.md` — docs/ is not a registry-scoped
  component) + `tests/agents.md` (scope: `tests`, authority `[read, write,
  test]`, restricted `[modify-fixtures, modify-schemas]`) for the canary test.
- Files modified (`git status` / `git diff --stat HEAD`):
  - `docs/paradox_gallery.md` — new, 304 lines
  - `README.md` — +1/−1
  - `tests/test_extension_corpus.py` — +17/−0
- Out-of-scope modifications: none. No changes to `src/`, `fixtures/`,
  `schemas/`, `spec/`, or `grammar/`. Exactly the three declared paths.
- Restricted actions from `tests/agents.md` (`modify-fixtures`,
  `modify-schemas`): not present — the new test reads
  `fixtures/limnalis_extension_corpus_v0.1.yaml` and `docs/paradox_gallery.md`
  but writes neither.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| FIXTURE-001 | PASS | New `TestParadoxGalleryDoc.test_gallery_doc_names_all_cases_and_examples` (tests/test_extension_corpus.py:407-421) is a doc-drift canary: asserts the doc mentions every C1-C4 case id and example filename. Does not modify fixtures; strengthens FIXTURE-001's spirit (corpus stays the conformance authority; doc is checked against it, not the reverse). |
| SCHEMA-001, MODEL-001, MODEL-002, NORM-001 | N/A | No `src/`, `schemas/`, or model changes in this changeset. |

## Checklist Verification (per checkpoint brief)

### 1. Verdict tables vs. pinned corpus expectations

Cross-checked every table cell in `docs/paradox_gallery.md` against
`fixtures/limnalis_extension_corpus_v0.1.yaml` case blocks `C1` (lines
917-1020), `C2` (1021-1193), `C3` (1194-1310), `C4` (1311-1458), and against
live execution (`load_corpus` + `run_case` + `compare_case`, and a direct
`run_case` probe reading `bundle_result.session_results[0].step_results[0]`).

- **C1** (docs/paradox_gallery.md:73-92): claim truth/support/license for
  `l1` (`N[undefined_term]`, license `N[no_adequacy_result]` on
  `a_liar_truth:truth_assignment`) and `l3` (`B[self_reference]`) match the
  pin exactly. Block `meta` fold to `F` via `N AND B = F` matches
  `expected.blocks.meta.aggregate: F` and is the exact mechanism spec §4
  documents ("Why B∧N=F: ... Truth-support vanishes; falsity-support
  remains" — spec/Limnalis-v0.2.2.md:640-641), which is also exactly what
  `_fold_block_truth` (src/limnalis/runtime/builtins.py:502-523) implements.
  `l0` non-evaluable/excluded framing matches the corpus's own
  `normalized_ast_expectations` bullet. Diagnostics: none — matches
  `diagnostics: []`.
- **C2** (docs/paradox_gallery.md:115-141): `c1` (T, license T via
  `a_smooth_manifold:prediction`), `c3` (T, license `N[missing_binding]` via
  `a_smooth_manifold:description`), adequacy rows (`aa_pred` T,
  `aa_core` N[missing_binding] + `adequacy_method_binding_missing` error),
  and transport `q_core` (degraded, T → N[transport_loss], support partial)
  all match `expected` and `adequacy_expectations` exactly. One exception —
  see Finding 1 below (the `c2` License cell).
- **C3** (docs/paradox_gallery.md:160-176): per-evaluator/aggregate for
  `c_super` (`B[evaluator_conflict]`, support conflicted) and `c_coherent`
  (T, support absent), block `local` per-evaluator/aggregate, and transport
  `q_amplify` (degraded, T → N[transport_loss], support partial) all match
  the pin exactly. The "per evaluator first" block-fold-order claim matches
  spec §8.6 verbatim ("Blocks are folded per evaluator first, then
  aggregated... It does not: aggregate claim truth across evaluators first,
  then fold" — spec/Limnalis-v0.2.2.md:851-857).
- **C4** (docs/paradox_gallery.md:204-224): `c1` (T, reason
  `missing_binding`), `c2` (F, reason `missing_binding`, license
  `N[no_adequacy_result]`), blocks `local` (F) and `meta` (N/`empty_block`),
  and the adequacy store (`aa_vol` T) all match the pin exactly. One
  exception — see Finding 1 below (the `c1` License cell). The
  paraconsistent_union reason-inheritance claim for `c1` ("aggregate truth
  stands, with the dissent's ground attached as disclosure") was traced to
  `apply_resolution_policy`'s general (not Track-C-specific)
  `paraconsistent_union` branch (src/limnalis/runtime/builtins.py:423-451,
  "Preserve unique inherited reason") and matches spec §8.3's reason rule
  ("...otherwise use resolution_policy or the unique inherited reason" —
  spec/Limnalis-v0.2.2.md:817-820).

Block-level reason annotations (`B[evaluator_conflict]` for C3's block,
`N[empty_block]` for C4's `meta` block) are accurate — I confirmed
`fold_block` (src/limnalis/runtime/builtins.py:526-589) computes its
aggregate via the same `apply_resolution_policy` used for claims, so these
reasons are genuinely produced at runtime — but they are not part of the
corpus's machine-checked `expected.blocks.*.aggregate` pin, which per spec
§8.6's `BlockResult` schema is a bare `T|F|B|N` enum with no reason field.
The doc's bracket annotations mirror the corpus's own descriptive
`normalized_ast_expectations` prose (which uses identical notation, e.g.
"-> B[evaluator_conflict]" at corpus line 1257, "-> N[empty_block] fold" at
line 1396), not an invented gloss. Not a finding, but worth a one-line
provenance note if the doc is revised (see Observation, below).

### 2. Four precision statements

- **Reason-vocabulary divergence** (docs/paradox_gallery.md:263-272): §8.5
  reason taxonomy confirmed to list `not_yet_applicable` among N reasons
  (spec/Limnalis-v0.2.2.md:828-845, specifically line 843). §9.2 confirmed:
  "If score = N, result is N[not_yet_applicable]" (line 923). §16.6.4
  confirmed: "score=N or no record →N[not_yet_applicable]" (line 1664) —
  this is the line that actually supports the compound "score declared N,
  or no adequacy record" claim; §9.2 alone only covers the score=N half.
  Both cited sections do contain the claimed content. Grepped `src/` for
  `not_yet_applicable`: zero occurrences — confirms "the implementation
  does not emit `not_yet_applicable` anywhere." `no_adequacy_result` occurs
  exactly once (builtins.py:1473), in `compose_license`, consistent with
  "the implementation's reason codes." `ast_decisions` block exists at
  fixtures/limnalis_extension_corpus_v0.1.yaml:45 and documents this exact
  divergence (see topic "License reason vocabulary under live
  compose_license," lines 65-70).
- **AC-as-anchor workaround** (docs/paradox_gallery.md:273-277): grepped
  `AssumptionNode` repo-wide — present in `src/limnalis/models/ast.py` and
  `schemas/limnalis_ast_schema_v0.2.2.json` (AST model + schema, as
  claimed), and absent from `src/limnalis/normalizer.py` (zero references —
  confirms "no surface-grammar support yet").
- **`|inf:|` rejection** (docs/paradox_gallery.md:278-283): empirically
  probed `normalize_surface_text` with a claim containing
  `|inf:finite_time|` — raised `NormalizationError: invalid baseline
  reference '|inf:finite_time|'`; the same claim with `|0:finite_time|`
  normalized successfully. Traced to
  `_parse_arg_text` (src/limnalis/normalizer.py:1503-1514):
  `kind, ref_id = inner.split(":", 1)`, then
  `if kind != "0" or not ref_id: raise NormalizationError(...)` —
  unconditionally rejects any `kind` other than the literal string `"0"`,
  which includes `inf` and `∞`. This matches the doc's claim precisely.
  (Minor: the doc's bullet does not carry an explicit `§`/line citation to
  the EBNF the way item 1 cites `§8.5`/`§9.2`/`§16.6.4` — it says "The spec
  grammar defines..." with no locator. Not inaccurate, just less precisely
  sourced than the sibling bullets; see Observation.)
- **Via-URIs never invoked** (docs/paradox_gallery.md:284-290): grepped
  every use of `bridge.via` in `src/limnalis/runtime/builtins.py`'s
  `execute_transport` and helpers — all 14 occurrences are inside
  `provenance=[bridge.id, bridge.via, ...]` list construction; none are
  used as a lookup/dispatch key. `PARADOX_BRIDGE_NAIVE_EXTRAPOLATION_V1_URI`
  and `PARADOX_BRIDGE_AMPLIFICATION_V1_URI` in
  `src/limnalis/plugins/fixtures.py:679,683` are plain string constants,
  and the corpus's own `test://.../bridges` registry entries
  (fixtures/limnalis_extension_corpus_v0.1.yaml:213-222, 245-252)
  independently describe them as "registered in the live pack as a marker
  only" — confirms the claim word-for-word.

### 3. Layer taxonomy and overclaim check

Spec §0 ("Architectural Layers," spec/Limnalis-v0.2.2.md:406-420) defines
exactly the four layers the doc uses (World, Knowledge, Fiction, Notation)
with matching descriptions — Knowledge layer is explicitly "who or what is
evaluating... Expressed through Evaluator, Evidence... Eval" (fits C3's
two-evaluator conflict); Fiction layer is explicitly "Assumptions,
idealizations, placeholders, proxies... adequacy judgments... Anchor" (fits
C2/C4's anchor-licensing stories). The doc's C1→notation, C2/C4→fiction
overreach, C3→knowledge conflict mapping is grounded in the spec's own
taxonomy, not invented. Grepped the doc for overclaiming language
(`solve`, `prove`, `settle`, `eliminat`): none found. The doc explicitly
disclaims resolution of the underlying questions ("The gallery does not
answer the underlying questions... does not say what is at r = 0... does
not tell you whether to accept the Axiom of Choice," docs/paradox_gallery.md:294-296)
and frames results as disclosure, not dissolution-by-fiat ("nothing
explodes... only disclosed" contradictions, line 16).

### 4. Runnable pointers

All three documented commands executed successfully from the repo root:

```
python -m limnalis normalize examples/paradox_liar.lmn                 -> exit 0
python -m limnalis normalize examples/paradox_schwarzschild.lmn        -> exit 0
python -m limnalis normalize examples/paradox_decoherence_cat.lmn      -> exit 0
python -m limnalis normalize examples/paradox_banach_tarski.lmn        -> exit 0
python -m limnalis validate-fixtures fixtures/limnalis_extension_corpus_v0.1.yaml
                                                                        -> {"status": "ok", "version": "v0.1"}
python -m pytest tests/test_extension_corpus.py -k Paradox             -> 7 passed, 17 deselected
```

The 7 passing tests include the new `TestParadoxGalleryDoc` canary.
`TestParadoxExamples.test_example_files_match_corpus_sources`
(tests/test_extension_corpus.py:389-397) confirms the "byte-identical...
test-enforced" claim (docs/paradox_gallery.md:36) with a literal
`path.read_text(...) == case.source + "\n"` comparison.

### 5. House style / README

- `docs/paradox_gallery.md` structure (Purpose → summary table → per-case
  sections with `**Corpus case:**`/`**Bundle:**` bold labels → reading
  guide → limits) is consistent with the closest existing analog,
  `docs/m6b_stress_bundles.md` (Purpose → per-bundle sections with
  `**File:**` bold labels → corpus-integration pointer). Markdown tables
  scanned programmatically for column-count consistency: no malformed
  tables. No trailing whitespace, no tabs, file ends with a trailing
  newline.
- The doc introduces `§8.5`/`§9.2`/`§16.6.4`-style citations, which do not
  appear elsewhere in `docs/*.md` (grep confirms zero other hits) but are
  the established convention in `.armature/reviews/*.md` (5 files). This is
  a reasonable, deliberate escalation of an existing internal convention
  into user-facing docs given this doc's precision mandate, not a
  style violation.
- README.md diff is genuinely a single inserted clause inside one existing
  paragraph/line (`+1/-1`): `For classic paradoxes encoded as claim
  bundles, see the [Track C Paradox Gallery](docs/paradox_gallery.md).`
  inserted between the Architecture Overview and spec/ sentences; nothing
  else on the line changed. The relative link `docs/paradox_gallery.md`
  resolves correctly from README.md's location (repo root) to the new file.

### 6. Suite + scope

- `git status --porcelain=v1`: exactly `M README.md`, `M
  tests/test_extension_corpus.py`, `?? docs/paradox_gallery.md`. No
  `src/`, `fixtures/`, `schemas/`, or `spec/` changes.
- Full suite: `python -m pytest tests/ -q` — exit 0, 1022 passing dots
  (verified by exact character count of the progress-dot output; no `F`,
  `E`, or `s` characters present), matching the expected 1022 exactly.

## Findings

### Finding 1 (moderate — precision/internal consistency; not a pinned-value violation)

`docs/paradox_gallery.md:118` (C2 table, `c2` row) and
`docs/paradox_gallery.md:206` (C4 table, `c1` row) both show License = `—`
(dash), which a reader will naturally take to mean "no license was
computed / not applicable." Both `c2` (C2) and `c1` (C4) are claims with no
`uses [...]` clause — the identical situation as `l3` in the C1 table,
which the doc correctly and explicitly annotates as License = `T (no
anchors used)` (docs/paradox_gallery.md:77).

I verified live, via `run_case` against the actual corpus cases, that
`compose_license` takes the same "claim uses no anchors" branch
(src/limnalis/runtime/builtins.py:1328-1334,
`return LicenseResult(claim_id=claim_id, overall=LicenseOverall(truth="T"))`)
for all three claims, and confirmed the concrete runtime output:

```
C2 c2: {'claim_id': 'c2', 'overall': {'truth': 'T', 'reason': None}, 'individual': [], 'joint': [], 'diagnostics': []}
C4 c1: {'claim_id': 'c1', 'overall': {'truth': 'T', 'reason': None}, 'individual': [], 'joint': [], 'diagnostics': []}
```

So the dash in these two cells is not merely "unpinned" (true — the
corpus's `expected` block omits `license` for these claims too, and
`compare.py`'s `_compare_license` skips comparison entirely when
`license_exp` is `None`, so nothing machine-checked is violated) — it
actively understates what the live pipeline computes, and does so
inconsistently with the doc's own precedent two sections earlier for the
structurally identical `l3` case. This is exactly the kind of
doc-states-something-checkably-false-about-conformance-material drift this
checkpoint exists to catch, even though it doesn't touch a field
`compare_case` enforces.

**Required change:** correct the License cells for `c2` (C2 table) and
`c1` (C4 table) to reflect the actual computed value (a vacuous `T`, no
reason — as already modeled correctly for `l3` in the C1 table), or
otherwise make the "no `uses` clause → no license row shown" convention
uniform across all three tables so a dash and an explicit `T` are not used
to mean the same thing in different places.

## Observations (non-blocking, optional polish)

- The block-level reason brackets (`B[evaluator_conflict]`, `N[empty_block]`)
  in the C1/C3/C4 tables are true (verified against `fold_block`'s
  implementation) but are not part of the corpus's machine-checked
  `expected.blocks.*.aggregate` pin (a bare truth-value enum per spec
  §8.6). A one-clause note distinguishing "pinned truth value" from
  "runtime-computed, corpus-annotated reason" would remove all ambiguity
  for a future reader auditing the doc against the YAML `expected:` block
  directly.
- The `|inf:|` rejection bullet (item 3 of "Implementation Vocabulary and
  Encoding Notes") is the only one of the four precision statements that
  doesn't carry an explicit section/line locator into the spec grammar,
  unlike its siblings (which cite `§8.5`, `§9.2`, `§16.6.4`). The claim
  checks out (verified empirically and against
  `spec/Limnalis-v0.2.2-reconstructed.md:1279-1280`), but a citation would
  match the rigor of the rest of the section.

## Verdict: PASS_WITH_ADVISORIES

The document is exceptionally well fact-checked: every pinned truth,
support, reason, license, adequacy, transport, and diagnostic value across
all four C1-C4 corpus cases was cross-checked against
`fixtures/limnalis_extension_corpus_v0.1.yaml` and matches exactly; all
four "implementation vocabulary" precision claims were independently
verified true against source code and, where testable, live execution
(including one direct empirical probe of the `|inf:|` rejection); the
layer taxonomy is grounded in spec §0 rather than invented, and the doc
explicitly disclaims solving the paradoxes; all three documented runnable
commands succeed; the README edit is a genuine single-clause insertion
with a resolving link; and the full suite is green at exactly 1022 passing
with no scope creep beyond the three declared paths. The one substantive
issue (Finding 1) is narrow, self-contained, does not affect any
machine-checked pin, and does not touch either case's headline verdict —
but should be corrected for consistency with the doc's own standard before
this becomes load-bearing reference material for the Wave 3 red team.

## Required Changes (before/alongside commit; non-blocking for the checkpoint's core accuracy claim)

- Fix the two License cells identified in Finding 1
  (docs/paradox_gallery.md:118, docs/paradox_gallery.md:206) so a dash and
  an explicit computed value do not describe the same underlying
  situation inconsistently.

## Rollback Recommendation: NO

Finding 1 is a two-cell precision fix, not a structural or conformance
defect. Remediating in place (or in a fast-follow edit) is safer and
cheaper than rolling back a 304-line, otherwise-verified-accurate
checkpoint.
