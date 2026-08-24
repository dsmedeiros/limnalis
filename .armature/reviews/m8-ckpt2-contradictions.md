# Review Verdict: m8-ckpt2-contradictions

**Reviewed:** Milestone 8, Checkpoint 2 ("Contradictions and staleness"), items 5-11 of `.taskmaster/docs/milestone-8-docs-remediation.md`, plus the checkpoint-1→2 handoff recorded in `.armature/session/state.md` ("Active Delegation") and `.armature/reviews/m8-ckpt1-executable-truth.md`.
**Changeset:** uncommitted working tree over HEAD `5571478` — 17 modified docs under `docs/` + modified `README.md` + new `docs/sarif_export.md` + modified `tests/test_doc_snippets.py` (20 files total; 19 are markdown docs, 1 is the test file). Confirmed via `git status --porcelain=v1` and unchanged across this review session.
**Method:** read every changed hunk in all 20 files against HEAD; read the normative spec sections (§8.3, §8.5, §9.2, §9.3, §10.2, §17 A12 narrative) and the vendored A12 fixture; read and executed the real runtime code (`_aggregate_adequacy_by_policy`, `aggregate_contested_adequacy`, `_aggregate_paraconsistent`, `execute_adequacy_with_basis`, `_degrade_truth`, `_execute_degrade`, `execute_transport`, `execute_transport_with_degradation_policy`, `sarif.py`, `runner.py` phase order, `cli/lint_cmd.py`); ran two independent probe scripts (adequacy aggregation divergence, CLI canary) from the scratchpad against the real installed package (no repo files added); hand-executed the rebuilt custom-degradation snippet and the property-valued transport syntax outside the pytest harness; ran `python -m limnalis lint/analyze --format sarif` for real; ran the full suite and the doc-snippet suite.

## Scope Compliance
- Declared scope: docs + tests only, per PRD hard constraint ("No changes to `src/` except NONE").
- `git diff --stat 5571478 -- spec/ schemas/ fixtures/ examples/ src/ grammar/` — empty on every path. **Zero `src/` changes confirmed** (and zero changes to any other vendored/immutable tree).
- Files modified match the task's stated changeset exactly; nothing else is dirty.

## Item-by-Item Findings

### 1. `aggregate_contested_adequacy` deviation — CONFIRMED, independently reproduced by execution

Read both functions in full:
- `_aggregate_adequacy_by_policy` — `src/limnalis/runtime/builtins.py:1029` (normative Phase-4 path, called from `evaluate_adequacy_set` at `:1088`, itself wired as `# Phase 4: adequacy evaluation` in `runtime/runner.py:361`).
- `aggregate_contested_adequacy` — `src/limnalis/runtime/builtins.py:4173`, delegating to `_aggregate_paraconsistent` (`:4258`) for `paraconsistent_union`/`adjudicated`-fallback.

Both line citations in the guide/ADR (`~1029`, `~4173`) are exact, not approximate.

**Probe 1 (`{B[method_conflict], T}`, `paraconsistent_union`)** — built `AdequacyResult` objects matching the vendored A12 fixture's own `aa1`/`aa2` values and fed them through both paths:
```
Phase-4 _aggregate_adequacy_by_policy(paraconsistent_union): truth='B' reason='adequacy_conflict'
aggregate_contested_adequacy(paraconsistent_union): adequate=False failure_kind='method_conflict'
```
`aggregate_contested_adequacy`'s `AdequacyExecutionTrace` model (`models/conformance.py:168`) has **no `truth` field at all** — only boolean `adequate`/`failure_kind` — so it structurally cannot represent "T unioned with B stays B"; `_aggregate_paraconsistent`'s own docstring even claims an outcome (`truth="B"`) its return type cannot produce, confirming the drift is real inside the source, not just in the old doc/ADR prose.

**Probe 2 (`priority_order`, order with an early F)** — order `[aaF(F, not adequate), aaT(T, adequate)]`:
```
Phase-4 priority_order: truth='F' reason='threshold_not_met'   (early F is decisive, per spec)
aggregate_contested_adequacy priority_order: winner=aaT (adequate=True)   (skips the F, picks the later T)
```
This is an exact inversion, matching the docstring's own literal claim at `builtins.py:4184` ("use first adequate, or first if all inadequate") — the loop at `:4226-4229` walks `for trace in traces: if trace.adequate: return trace`, which cannot stop at a decisive F. `_aggregate_adequacy_by_policy`'s `priority_order` branch (`:1066-1072`) also accepts an explicit `policy_order` parameter (from `policy.order`); `aggregate_contested_adequacy` has no such parameter at all — a second, structural divergence beyond the aggregation-rule difference.

**Spec verification (§8.3, `spec/Limnalis-v0.2.2.md:812-824`):** "paraconsistent_union. ... Aggregate by componentwise OR across evaluators. One evaluator T, one evaluator F →aggregate B[evaluator_conflict]. ... priority_order. Use the first listed evaluator whose truth is not N. If all are N, aggregate is N." Matches the guide's and amendment's paraphrase exactly, including "including an F or B result" as an accurate restatement of "first ... not N."

**A12 verification (vendored corpus, `fixtures/limnalis_fixture_corpus_v0.2.2.json:1444-1460`, and spec §17 narrative at `spec/Limnalis-v0.2.2.md:1922-1931`):** `adequacy_expectations.aa1 = {truth: B, reason: method_conflict}`, `aa2 = {truth: T}`, `a_model:prediction (aggregate) = {truth: B, reason: adequacy_conflict}` — byte-for-byte the numbers the ADR amendment and guide cite. The spec's own A12 prose is even more explicit: "aa1: ... Expected: B[method_conflict]. aa2: ... Expected: T. With adequacy_policy: paraconsistent_union, aggregate = B." **The docs' claim is not just plausible, it is a verbatim restatement of the spec's own worked example.**

**Verdict on item 1: sound and independently reproduced.** The docs' finding is correct in every particular checked (both function identities, both line numbers, both aggregation-rule mismatches, and the A12 illustration).

**Bonus discovery (not part of the claimed deviation, logged for future ledger use, not a docs defect):** the mechanism by which `aa1` becomes `B[method_conflict]` differs between the two code paths too. The Phase-4 path (`builtins.py:1161-1207`) triggers method_conflict when same-task assessments use *different method URIs*, regardless of score agreement. `execute_adequacy_with_basis` (`:4144-4152`, used by `aggregate_contested_adequacy`) triggers it when *computed vs. declared score diverges beyond `adequacy_divergence_tolerance`* — which is the literal §9.2 rule ("If computed and declared scores materially disagree ... assessment result is B[method_conflict]", `spec/Limnalis-v0.2.2.md:924-926`). Neither the guide nor the ADR amendment makes any claim about this deeper mechanism (both are scoped to the aggregation step only, and are accurate there), so this is not a gap in the reviewed prose — but it is worth folding into the checkpoint-3 deviation-ledger entry alongside the aggregation-rule finding, since it means the divergence between the two functions is broader than the aggregation-strategy semantics alone.

### 2. ADR-008 amendment — appended only, dated, technically accurate

`git diff 5571478 -- docs/adr/008-contested-adequacy-aggregation.md` shows **only `+` lines** — the original body (lines 1-40, including the "All must agree" / "first adequate one wins" table cells) is byte-unchanged; the amendment is a pure append starting at the `---` separator. Dated "2026-08-24" (today). Content cross-checked against spec §8.3/§9.3 and the A12 corpus data above — accurate on every claim, including the nuanced "not because the producers disagree" framing (A12's `aa2` result is independently `T`; the aggregate becomes `B` because of the union/join operation, not a boolean "did they disagree" check).

### 3. Degrade alignment — three docs match spec §10.2 and the real implementation; runnable example executes as documented

- **Spec §10.2** (`spec/Limnalis-v0.2.2.md:1002-1005`): "T →N[transport_loss], F →N[transport_loss], B →B[boundary_mix], N →N. ... support becomes partial unless truth_policy overrides it." **`_degrade_truth`** (`builtins.py:2446-2461`) implements this table exactly, cell for cell. `transport_semantics.md` and `cookbook/transport_chains.md`'s new mode tables reproduce it verbatim.
- **`writing_a_transport_handler.md`**'s rebuilt example: ran the full snippet (`<!-- doc-snippet: runnable -->`, now in `COVERED_DOCS`) verbatim outside pytest. Output matched the doc's inline comments exactly: `degraded` / `dp_conf` / `T` / `0.72...` (0.9 × 0.8 scale factor from 2 risks, `max(0.5, 1.0-0.1*2)=0.8`). All cited hook names verified to exist and match signatures: `DegradationPolicyNode` (`models/ast.py:676`, `id/kind: Literal["default","custom"]/binding/preserve_fields/max_loss`), `execute_transport_with_degradation_policy(bridge, step_ctx, machine_state, services, degradation_policy=None)` (`builtins.py:3010`), `services["__degradation_handlers__"]` (read at `builtins.py:3058-3061`), all re-exported through `limnalis.api.transport`/`api.context`/`api.models`/`api.results` exactly as imported in the snippet. The section heading ("a custom degradation policy that **overrides** the default"), the inline docstring ("Overrides the spec 10.2 default degradation rule"), and the closing sentence ("With `kind="default"` (or no policy at all), the same call reduces to the normative `execute_transport` behavior") together label this unambiguously as an override illustration, not a default-behavior description.
- **Minor observation (not a defect):** the guide's sentence "spec §10.2 allows a truth policy to override that" slightly widens the literal spec sentence, which ties "unless truth_policy overrides it" grammatically to the *support* rule, not explicitly to the truth-weakening table. Non-blocking: the doc immediately clarifies that "in this implementation the override hook is the M6B degradation-policy extension" (a different, working mechanism), so it never claims the spec's literal `truth_policy: BindingRef?` field (present in the AST — `models/ast.py:501`, parsed by `normalizer.py:713,724`) is what's active. **Separately discovered, out of scope for this milestone (`src/` frozen):** that literal `TransportNode.truthPolicy` field is structurally validated but never read anywhere under `src/limnalis/runtime/` — it is dead at runtime, independent of and in addition to the `aggregate_contested_adequacy` finding above. Worth a future ledger line; not a doc-accuracy defect since the doc never claims it's wired up.

### 4. `transport_chains.md` rewrite — property-valued syntax normalizes; honest note is accurate

Built a full bundle using the doc's exact bridge/claim syntax (`preserve [sensor_fidelity, calibration_traceability]`, `gain [model_grounding]`, and `c_temp: ... refs [e_sensor] semantic_requirements [sensor_fidelity];`) and ran it through the real CLI: `limnalis normalize` exit 0, `limnalis validate-ast` exit 0, `semanticRequirements: ["sensor_fidelity"]` present on the claim exactly as documented.

The "honest note" (`docs/cookbook/transport_chains.md:53`) claims `examples/cwt_transport_bundle.lmn` still uses evidence ids in `preserve`/`lose`/`gain` and still normalizes — confirmed: the real file uses `preserve [e_sensor, e_calibration]` etc. (`examples/cwt_transport_bundle.lmn:83-84,96-98`), and `limnalis normalize`/`validate-ast` both exit 0 on it. `requires [e_sensor]` on `c_model` (`examples/cwt_transport_bundle.lmn:118`) does map to `semanticRequirements` — `normalizer.py:72-73` lists `"requires"` and `"semantic_requirements"` as synonymous clause keywords, both writing into `ClaimNode.semanticRequirements` (`:884-891`). The note's claim about `pattern_only` status on a plain `evaluate` run is confirmed by running `limnalis evaluate examples/cwt_transport_bundle.lmn` (both bridges report `"status": "pattern_only"`); `transport_queries` is a real fixture-environment key (`conformance/runner.py:607-632`) and case **B1** genuinely uses it (`fixtures/limnalis_fixture_corpus_v0.2.2.json:1620-1631`, the only `transport_queries` occurrence inside the B1 case block).

### 5. Resolution-policy and staleness fixes — grep-clean, phase table correct, banners present

Repo-wide grep across `docs/` + `README.md`:
- `unanimous`, `cli.py`, `currently stubbed`, `degraded_transport`: **zero hits**, anywhere.
- `All must agree` (exact case): **one hit**, `docs/adr/008-contested-adequacy-aggregation.md:27` — inside the untouched original ADR body (confirmed append-only above). Correctly preserved.
- `First adequate wins` (exact case, the old Title-Case table-cell phrasing): **zero hits** — the row that contained it was replaced.
- Lowercase/paraphrased occurrences of "all must agree" / "first adequate (one/wins)" appear only inside the ADR's own preserved body (`:27-28`) and the two corrective quotes (`adequacy_execution_guide.md:70`, `adr/008:48,51`) that explicitly frame them as the superseded/divergent phrasing — exactly the permitted exception class.
- `how_evaluation_works.md:70` now reads "spec §8.3 ... `single` ... `paraconsistent_union` ... `priority_order` ... `adjudicated`", matching spec text verbatim in substance.
- **Phase-table fix, verified against `runtime/runner.py`'s real comments:** `plugin_sdk_overview.md:41` now reads `2 | resolve_ref`, matching `runner.py:294` (`# Phase 2: resolve refs/policies`) exactly; `runner.py:269` confirms phase 1 is "build step context" (no primitive, correctly absent from the extensibility table). All other rows in the table (3,4,5,6,8,9,11,13) cross-checked against `runner.py:333,361,390,422,476,534,629,696` — all correct, unchanged by this diff.
- **PrimitiveSet canonical-home claim** (`plugin_sdk_overview.md:26`): both `limnalis.api.evaluator` (`api/evaluator.py:13-16`) and `limnalis.api.plugins` (`api/plugins.py:26`) import `PrimitiveSet` directly from `..runtime.runner` — there is no real import-chain hierarchy between the two, so "canonical home" is an editorial/curatorial framing, not a false claim about source topology; it does not misstate anything checkable.
- **Five historical banners:** present, worded consistently, and dated `2026-08-24` on `release_candidate_status.md:3`, `milestone_3b_notes.md:3`, `milestone_3c_status.md:3`, `m6b_stress_bundles.md:3`, `implementation_notes.md:3`. All cross-referenced paths in the banners resolve (`docs/architecture.md`, `docs/how_evaluation_works.md`, `docs/cookbook/conformance_testing.md`, `docs/transport_semantics.md`, `docs/cookbook/transport_chains.md`, `docs/adr/` all exist).
- Checkpoint-1 handoff item verified fixed as part of this checkpoint: all 5 bare `format=` sites (`downstream_artifact_consumption.md:52`, `export_formats.md:192,193,222`, `exchange_package_format.md:216`) now use `input_format=`/`output_format=`; grep for stray `format="..."` outside `output_format`/`input_format`/CLI `--format` returns zero hits. Hand-executed the fixed `create_package(..., output_format="directory")` call against the real signature (`interop/package.py:73`) — succeeds.

### 6. SARIF doc — every documented field/flag/choice verified against `sarif.py` and real CLI output

Read `src/limnalis/sarif.py` in full and compared field-by-field against `docs/sarif_export.md`'s mapping table: `$schema`/`version`, `ruleId`↔`diag.code` + first-message `shortDescription`, `level` mapping (`error→error`, `warning→warning`, else→`note`, including the doc's "(and anything else)" nuance matching `.get(severity, "note")`), `message.text`, conditional `locations`/`region` (only when `source_file`/`span` present), conditional `properties.phase`/`subject`, and the `(ruleId, message)`/`id` sort keys — **all exact matches**, no discrepancies found.

`--format` choices (`plain`, `json`, `grouped` default, `sarif`) and their availability on both `lint` and `analyze` confirmed against `cli/lint_cmd.py:201-206,222-227`. The "structured formats always print, even empty" and "exit code independent of format" claims confirmed against `cli/lint_cmd.py:88` (`if typed or fmt in ("json","sarif")`) and `:104-105` (`has_errors` computed before/independent of format branch).

Ran `limnalis lint examples/minimal_bundle.lmn --format sarif` and `limnalis analyze ... --format sarif` for real: output is a **byte-for-byte match** to the doc's "abridged" example (same `ruleId`, `level`, region `1,1`–`12,2`, `properties.phase=normalize`/`subject=minimal_bundle`, `version: "0.2.2rc1"`). Ran twice and diffed — byte-identical, confirming the determinism claim.

Links: `docs/getting_started.md` (new paragraph) and `docs/architecture.md` (transport-handlers section) both link to `sarif_export.md`; `sarif_export.md`'s "Further reading" links back to both — all four resolve (files exist at the referenced relative paths). Not yet linked from `docs/README.md` — expected and out of scope for checkpoint 2 (explicitly deferred to checkpoint 3 per the task's closing note).

### 7. CLI canary — walks subparsers correctly, fails on fabricated commands, all 12 README rows resolve

Read `tests/test_doc_snippets.py:181-227`. `_iter_subparser_actions`/`_cli_command_exists` correctly walk the argparse subparser tree token-by-token, supporting multi-token commands (`"conformance run".split()`).

Scratch-probed the real helper against the real `build_parser()` (no repo files touched): all 12 README CLI-table rows (`parse`, `normalize`, `validate-source`, `validate-ast`, `validate-fixtures`, `evaluate`, `print-schema`, `conformance list`, `conformance show`, `conformance run`, `conformance report`, `version`) resolve True; three fabricated probes (`frobnicate`, `conformance frobnicate`, `lint sarif`) all correctly resolve False, including the multi-token case where the fabrication only appears at the second token (proving the walk, not just top-level membership, is exercised). `python -m pytest tests/test_doc_snippets.py -v` — **25/25 passed**, including `test_readme_cli_table_lists_only_real_commands`.

### 8. README.md scope check — edits are exactly the item-5/item-9 fixes, nothing else drifted

Full diff is two hunks, matching `git diff --stat` (`README.md | 7 +-`, i.e. 2 deletions / 5 insertions): (1) the resolution-policy list line (item 5: `unanimous, majority, adjudicated` → `` `single`, `paraconsistent_union`, `priority_order`, `adjudicated` ``); (2) the repo-layout block (item 9: `cli.py` line replaced by `cli/`, `interop/`, `plugins/` package lines). No other prose in README.md was touched.

### 9. Gates

- **Full suite:** `python -m pytest tests/ -q` — exit code 0, **exactly 1119 passing dots**, zero `F`/`E`/`s`/`x` markers.
- **Snippet tests:** `tests/test_doc_snippets.py` — 25/25 passed (up from 16 in checkpoint 1; the 9 new tests come from the 3 newly covered docs' extracted `runnable` blocks plus the CLI canary).
- **Fences balanced:** counted `` ``` `` occurrences in all 19 touched markdown files (18 modified docs incl. `README.md` + new `sarif_export.md`) — every file has an even count. (The task's "20 touched docs" phrasing appears to count the full 20-file changeset including `tests/test_doc_snippets.py`, which is Python, not markdown — no fence check applies to it and none is missing.)
- **Byte-untouched:** `git diff --stat 5571478 -- spec/ schemas/ fixtures/ examples/ src/ grammar/` empty on every path.

## Advisories (non-blocking; none require changes to this checkpoint)

1. `docs/writing_a_transport_handler.md`'s "spec §10.2 allows a truth policy to override that" slightly widens the literal spec sentence (see item 3 above); does not misstate runtime behavior and is immediately followed by an accurate description of the actual (different) override mechanism. Consider tightening on a future pass.
2. Newly discovered, out of scope for `src/` changes this milestone: `TransportNode.truthPolicy` (`models/ast.py:501`) is parsed/normalized/validated but never read by `src/limnalis/runtime/` — the spec's literal §10.2 override field is inert; the M6B `DegradationPolicyNode` mechanism the docs now describe is a separate, working path. Candidate for the checkpoint-3 deviation ledger or a later milestone.
3. Newly discovered, out of scope: the two code paths' `B[method_conflict]` *trigger* mechanisms differ (Phase-4: different method URIs on same-task assessments; `execute_adequacy_with_basis`: computed-vs-declared score divergence beyond tolerance, which is the literal §9.2 rule). Neither reviewed doc makes a claim about this, so it is not a prose defect, but it broadens what "the `aggregate_contested_adequacy` deviation" should probably cover when filed in `compatibility_and_deviations.md` at checkpoint 3 — recommend folding it into the same ledger entry rather than treating the aggregation-rule mismatch as the whole story.
4. Pre-existing, not touched by this checkpoint (already flagged as non-blocking in the checkpoint-1 review): `docs/downstream_artifact_consumption.md:62` still has a non-`v`-prefixed `"spec_version": "0.2.2"` inside an elided (non-runnable, `...`-truncated) dict-literal example. Untouched by checkpoint 2's declared scope and not part of the checkpoint-1→2 handoff list; still open for a future pass.

## Verdict: PASS_WITH_ADVISORIES

All nine verification items hold up under independent, execution-based re-checking — most notably item 1, the load-bearing deviation finding, which was reproduced from scratch with two targeted probes against the live code (not just re-derived from reading) and cross-confirmed against the spec's own worked A12 example and the vendored corpus's `adequacy_expectations` pins, which match the ADR amendment's numbers exactly. The ADR-008 amendment is a clean append (verified via diff, no `-` lines) with accurate technical content. The three degrade-semantics docs align with spec §10.2 and the real `_degrade_truth` table; the rebuilt custom-degradation example executes exactly as documented and is unambiguously labeled as an override. The transport_chains.md rewrite's property-valued syntax normalizes and validates by direct CLI execution, and its honest note about the untouched cwt example is accurate on every sub-claim. The contradiction-sweep grep is clean outside the explicitly-permitted preserved ADR body and corrective quotes. The phase table now matches `runner.py`'s real numbering. The SARIF doc matches `sarif.py` and real CLI output field-for-field, including byte-identical determinism across repeated runs. The CLI canary genuinely walks the subparser tree and genuinely fails on fabricated commands. README's diff is exactly the two mandated fixes. All gates are green: 1119/1119 tests, 25/25 snippet tests, balanced fences on all touched markdown, and zero bytes changed outside docs/tests. Four non-blocking advisories are logged above (two are new discoveries about pre-existing `src/`-side gaps, correctly left unpatched per the milestone's hard constraint; two are pre-existing/minor prose nits).

## Required Changes: none

## Note for Checkpoint 3

- The confirmed `aggregate_contested_adequacy` deviation (item 1 above) must be filed in `docs/compatibility_and_deviations.md`. Recommend the filed entry cover both the aggregation-rule mismatch (paraconsistent_union "all-must-agree" boolean vs. spec's pairwise truth union; priority_order "first-adequate" vs. spec's "first-not-N") **and** advisory 3 above (the differing per-assessment method_conflict trigger mechanisms), since both are real, currently-undocumented-outside-this-checkpoint divergences in the same function pair, with exact spec citations (§8.3, §9.2, §9.3) and file:line evidence now on record in this review and in the amended ADR-008 / `adequacy_execution_guide.md`.
- `docs/sarif_export.md` is confirmed complete, accurate, and ready to join the docs index (`docs/README.md`) — no corrections needed before linking it in.
- Advisories 1, 2, and 4 above are optional cleanup, not blockers, for checkpoint 3 or a later pass.

## Rollback Recommendation: NO

No invariant violation, no scope violation, no regression, no inaccurate documentation claim found anywhere in the 20-file changeset after execution-based re-verification of all nine requested items. Safe to commit checkpoint 2 as-is.
