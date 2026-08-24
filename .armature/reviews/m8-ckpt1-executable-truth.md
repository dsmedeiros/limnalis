# Review Verdict: m8-ckpt1-executable-truth

**Reviewed:** Milestone 8, Checkpoint 1 ("Executable truth"), items 1-4 of `.taskmaster/docs/milestone-8-docs-remediation.md`
**Changeset:** uncommitted working tree over HEAD `b70580d` (docs + tests only)
**Method:** read every real signature under review, ran the new suite, hand-executed 5 extracted snippets outside the pytest harness, probed the extraction mechanism with a scratch harness (no repo files added), ran a real `export-ast`, checked PyPI live, diffed every one of the 9 docs against HEAD in full.

## Scope Compliance

- Declared scope: no `docs/agents.md` exists, so this changeset is governed by root `agents.md` (scope `/`, `restricted: [write-application-code]`) and `tests/agents.md` (scope `tests`, `restricted: [modify-fixtures, modify-schemas]`).
- Files modified (`git status --porcelain=v1`): exactly `docs/cookbook/custom_plugin.md`, `docs/downstream_artifact_consumption.md`, `docs/downstream_usage_examples.md`, `docs/exchange_package_format.md`, `docs/export_formats.md`, `docs/getting_started.md`, `docs/interop_overview.md`, `docs/jsonld_rdf_note.md`, `docs/plugin_sdk_overview.md` (all `M`), plus new `tests/test_doc_snippets.py` (`??`). Matches the task's stated changeset exactly; nothing else is dirty.
- `git diff --stat b70580d -- src/ grammar/ .armature/ spec/ schemas/ fixtures/` — all empty. Vendored/source trees untouched.
- Out-of-scope modifications: none.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| FIXTURE-001 | PASS | `fixtures/` byte-unchanged (empty diff). New test doesn't touch fixture semantics; it documents API usage. Hand-executed the fixture-conformance snippet myself: all 16 corpus cases still PASS through unmodified `run_case`/`compare_case` (see Item 1 below). |
| FIXTURE-002/003 | N/A | No fixture files touched. |
| SCHEMA-00x, MODEL-00x, NORM-00x, PARSER-00x | N/A | No `src/`, `schemas/`, or `grammar/` changes (all empty diffs). |
| root `agents.md` restricted: write-application-code | PASS | Zero `src/` changes. |
| `tests/agents.md` restricted: modify-fixtures, modify-schemas | PASS | Zero `fixtures/`/`schemas/` changes; new test file only reads them. |

## Checkpoint: 1 of 3

---

## Item 1 — Every fixed snippet vs. the real API

Read the real signatures first, then checked every rewritten call site against them:

- `run_bundle(bundle, sessions, env, primitives=None, services=None, adjudicator=None)` — `src/limnalis/runtime/runner.py:871-878`.
- `run_case(case, corpus=None)` — `src/limnalis/conformance/runner.py:721` (no `services` kwarg at all).
- `NormalizationResult` — `dataclass(slots=True)` with fields `canonical_ast`, `diagnostics` only — `src/limnalis/normalizer.py:55-58`.
- `CaseComparison` — fields `case_id, passed, mismatches, skipped, skip_reason, error, warnings` (no `differences`) — `src/limnalis/conformance/compare.py:30-46`.
- `FixtureCorpus` — plain dataclass, no `__iter__`; iterate `.cases` — `src/limnalis/conformance/fixtures.py:59-80`.
- `load_corpus(path)` / `load_corpus_from_default()` — `src/limnalis/conformance/fixtures.py:90-99`.

Every rewritten call site in the 9 docs matches these signatures (`.bundle`→`.canonical_ast`, `bundle.claims`→`bundle.claimBlocks[i].claims`, `comparison.differences`→`.mismatches`, `run_case(case, corpus)` positional not `services=`, `for case in corpus.cases:` not `for case in corpus:`, `run_bundle(bundle, sessions, env, ...)` with real `SessionConfig`/`StepConfig`/`EvaluationEnvironment` objects).

**Ran `tests/test_doc_snippets.py`: 16 passed** (`downstream_usage_examples.md` ×11, `plugin_sdk_overview.md` ×1, `cookbook/custom_plugin.md` ×2, plus the canary and the negative control).

**Hand-executed 5 snippets outside the pytest harness** (copied verbatim into scratch scripts, run from repo root with the installed editable package — i.e. exactly what a reader who copy-pastes would get):
1. `downstream_usage_examples.md:18-29` (minimal parse+normalize) → `Bundle ID: minimal_bundle`, `Claim blocks: 1`, `Claims: 1`. Exact.
2. `downstream_usage_examples.md:118-165` (custom `ev0::predicate` handler wiring) → confirmed via an injected sentinel that the registered handler **was actually invoked** (`CALLED["predicate"] = True`), aggregate truth `T` — substantiates the doc's claim "the handler below is actually consulted when that bundle is evaluated." `examples/minimal_bundle.lmn` does declare `evaluator ev0`, confirmed by reading the file.
3. `downstream_usage_examples.md:171-208` (B1 grid pack via fixture corpus) → 5 claims, real `ev_grid` truth/support values printed, no errors.
4. `downstream_usage_examples.md:269-288` (fixture-pack conformance loop) → all **16/16 corpus cases print PASS** through the real `run_case`/`compare_case` path — this exercises FIXTURE-001 live and it holds.
5. `cookbook/custom_plugin.md:22-68` (setup+setup+runnable concatenated exactly as a reader following the tutorial top-to-bottom would paste them) → executes cleanly.

All five ran clean against the real installed package (no mocks). This directly confirms the extraction mechanism reproduces exactly what a reader would experience, not merely what the harness's namespace-chaining happens to paper over.

**Verdict on Item 1: sound.** Signatures verified by reading and by execution; no remaining mismatch found in any snippet inside the checkpoint's declared scope.

## Item 2 — Extraction mechanism

Read `tests/test_doc_snippets.py:1-169` in full. To avoid modifying the repo, I built an isolated scratch harness (`/tmp/.../scratchpad/probe_extraction.py`) that imports the real `_extract_snippets` function from the real test module and points its `REPO_ROOT` at throwaway probe docs in the scratchpad only — no repo file was added or edited for this.

- **Unknown marker fails collection:** `<!-- doc-snippet: executable -->` → `ValueError: probe_unknown_marker.md:3: unknown doc-snippet kind 'executable' (expected one of ['illustrative', 'runnable', 'setup'])`. Since `_SNIPPETS_BY_DOC = _all_snippets()` runs at **module import time** (`tests/test_doc_snippets.py:118`), this exception fires during pytest collection, not inside a test body — a real repo doc with a typo'd marker would fail the whole collection run, not silently skip.
- Marker not immediately followed by a `` ```python `` fence → same class of `ValueError` (verified with a second probe doc).
- A doc with `setup` → `runnable` → `illustrative` → an unmarked block extracts exactly the 3 marked ones in order (unmarked excluded); the "illustrative" block contained deliberately invalid Python (`(((`) and was never executed, confirming illustrative content is inert.
- **Negative control genuinely discriminates:** `test_negative_control_old_broken_attribute_raises` (`tests/test_doc_snippets.py:158-169`) is a hardcoded (non-extracted) test asserting `result.bundle` raises `AttributeError` against the real `normalize_surface_file` result. Since `NormalizationResult` is `@dataclass(slots=True)` with only `canonical_ast`/`diagnostics` as slots, this is a real, structural guarantee, not a stub — confirmed passing in the full run.
- **Gate-armed canary:** `test_every_covered_doc_has_runnable_snippets` (`tests/test_doc_snippets.py:150-155`) asserts each of the 3 `COVERED_DOCS` has ≥1 runnable block, so stripping all markers from a covered doc fails the suite rather than silently exempting it.

**Verdict on Item 2: sound**, confirmed by direct execution of the real extraction code against hostile scratch input, not just by reading.

## Item 3 — No overcorrection

Read the full `git diff b70580d` for all 9 files (not just excerpts) plus the complete current text of `downstream_usage_examples.md` and `getting_started.md` end-to-end.

- Every hunk in every file ties directly to one of: broken-snippet fixes (item 1), install instructions (item 2), or the node/version field contract (item 3 of the PRD). No incidental prose drift found.
- `docs/downstream_usage_examples.md` reads coherently top-to-bottom as a document: section headers that changed (e.g. "Using the fixture plugin pack for conformance testing" → "Running conformance cases with the fixture plugin pack") are justified by the content actually changing underneath them (manual `register_fixture_plugins` wiring replaced by "you don't wire it up yourself, `run_case` does it"), not cosmetic churn.
- `docs/getting_started.md`'s embedded `.lmn` example (lines 24-37) is **byte-identical** to `examples/minimal_bundle.lmn` (verified by direct string comparison) — the surface-syntax fix (checkpoint item 1's "brace-less/semicolon-less block") is not just plausible-looking, it matches the real fixture file exactly.
- `cookbook/custom_plugin.md:80`'s corrected pointer does both things the PRD offered as alternatives: it correctly recharacterizes `examples/consumer_grid_b1.py` as using `run_case`/`compare_case` (verified: `grep` on that file shows `run_case`/`compare_case`, zero `run_bundle`) **and** links to the real `run_bundle` example in `downstream_usage_examples.md`'s "Running B1 with the grid plugin pack" section — the anchor (`#running-b1-with-the-grid-plugin-pack`) matches that section's actual header text under standard GFM anchor-slugging.

**Verdict on Item 3: sound.** Fixes are surgical; no scope creep into unrelated prose found in any of the 9 files.

## Item 4 — Install instructions

- PyPI: confirmed 404. The JSON API (`https://pypi.org/pypi/limnalis/json`) returns a clean `HTTP/2 404` with body `{"message": "Not Found"}` served directly by PyPI's `gunicorn` backend — sanity-checked against a known-real package (`requests`) via the identical path/proxy, which correctly returns `200` with full metadata, proving the request path itself works. (The `/project/limnalis/` HTML page returns a `200` "Client Challenge" bot-mitigation stub through the sandboxed network path — not authoritative; the JSON API is.)
- All 5 install-instruction docs (`getting_started.md:5-18`, `downstream_usage_examples.md:9-11`, `plugin_sdk_overview.md:6`, `downstream_artifact_consumption.md:9-15`, `interop_overview.md:98-105`) now say "not yet published to PyPI," show `pip install -e .` / `pip install -e ".[dev]"`, and show `PYTHONPATH=src python -m limnalis ...`.
- Runtime deps cited (`pydantic`, `lark`, `jsonschema`, `PyYAML`) match `pyproject.toml:24-29` exactly (`pydantic>=2.12,<3`, `lark>=1.2.2,<2`, `jsonschema>=4.25,<5`, `PyYAML>=6.0,<7`) — no extra, no missing, no wrong name.
- Repo-wide grep confirms zero remaining `pip install limnalis` occurrences anywhere in `docs/`.

**Verdict on Item 4: sound.**

## Item 5 — Field contract, verified by execution

Ran `python -m limnalis export-ast examples/minimal_bundle.lmn` for real and inspected the output:
- Every AST node carries `"node": "<PascalCase>"` — observed `"Bundle"`, `"ClaimBlock"`, `"Claim"`, `"PredicateExpr"`, `"Evaluator"` in the real export. Matches `BundleNode.node: Literal["Bundle"]` (`src/limnalis/models/ast.py:594`) and the doc's corrected `ast["node"]` (was `ast["node_type"]`).
- `spec_version`/`schema_version` = `"v0.2.2"`, `package_version` = `"0.2.2rc1"` in the real envelope — matches `src/limnalis/version.py:5-7` (`SPEC_VERSION = "v0.2.2"`, `SCHEMA_VERSION = "v0.2.2"`, `PACKAGE_VERSION = "0.2.2rc1"`) and `pyproject.toml:7` (`version = "0.2.2rc1"`) exactly. Repo-wide grep: zero remaining `"0.1.0"` or `node_type` anywhere in `docs/`.
- **`limnalis version`** (not `--version`) really does print `{"package": "0.2.2rc1", "spec": "v0.2.2", "schema": "v0.2.2", "corpus": "v0.2.2"}` — ran it, byte-for-byte match to `export_formats.md:135-140`. Separately confirmed `limnalis --version` really does print just `limnalis 0.2.2rc1` — the doc's added parenthetical claim ("prints just the package version line", `export_formats.md:126`) is accurate.
- **`output_format` kwarg at "the one fixed site":** `export_ast_from_dict(ast_data, output_format="json")` (`export_formats.md:211`) — ran it against the real function (`src/limnalis/interop/export.py:45-59`, param is `output_format`) and got the correct envelope back. Counted exactly **6** new `"0.2.2rc1"` occurrences across the diff, matching the PRD's "(6 places)" precisely.

**Verdict on Item 5: sound, all claims execution-verified.**

## Item 6 — Scope + gates

- `git status --porcelain=v1` matches the stated changeset exactly (9 `M` docs + 1 `??` test file); nothing else dirty.
- `git diff --stat b70580d -- spec/ schemas/ fixtures/` — empty. Byte-untouched, confirmed.
- **Full suite: `python -m pytest tests/ -q` → exit code 0, exactly 1110 dot markers, zero `F`/`E`/`s`/`x` characters in the output.** Matches "expect 1110" exactly.
- Markdown fences: counted `` ``` `` markers in all 9 changed docs — all even (balanced): `downstream_usage_examples.md` 22, `plugin_sdk_overview.md` 10, `cookbook/custom_plugin.md` 8, `getting_started.md` 14, `downstream_artifact_consumption.md` 30, `interop_overview.md` 12, `export_formats.md` 22, `exchange_package_format.md` 20, `jsonld_rdf_note.md` 2.

**Verdict on Item 6: sound.**

## Item 7 — Checkpoint-2 handoff list: verified real, and more precisely scoped than stated

All three handoff items are real. I did not find a written record of this handoff list anywhere in the repo (not in `.armature/journal.md`, not in `.armature/session/state.md`'s "Active Delegation" line) — it appears to exist only as the implementer's/orchestrator's own notes relayed in the task prompt. **Process note (not a changeset defect):** before this checkpoint is marked complete, the orchestrator should land this handoff list in `.armature/session/state.md` or the journal so checkpoint 2 doesn't have to be re-derived from memory.

1. **`format=` kwargs in remaining sites — REAL, and broader than "the one fixed site" phrasing might suggest.** I swept all 9 changed docs for bare `format=` calls (excluding `output_format=`/`input_format=`/CLI `--format`) and confirmed **5 sites, 3 files, 4 different functions**, every one raising a real `TypeError` when executed against the current API:
   - `docs/downstream_artifact_consumption.md:52` — `import_ast_envelope(json_text, format="json")` → real param is `input_format` (`src/limnalis/interop/import_.py:16-19`). `TypeError: import_ast_envelope() got an unexpected keyword argument 'format'` (confirmed by execution). Bonus: the prose immediately below it ("the `format` parameter is required", line 55) is directionally correct (an explicit format really is required for raw-string input, per `src/limnalis/interop/import_.py:72-76`) but names the wrong parameter.
   - `docs/export_formats.md:192,193` — `export_ast(..., format="json"/"yaml")` → real param is `output_format` (`src/limnalis/interop/export.py:19-22`). Confirmed by execution.
   - `docs/export_formats.md:222` — `export_result(result_data, format="json")` → same, `src/limnalis/interop/export.py:62-65`. Confirmed by execution.
   - `docs/exchange_package_format.md:216` — `create_package(..., format="directory")` → real param is `output_format` (`src/limnalis/interop/package.py:64-73`). Confirmed by execution.
   - By contrast, the CLI-level `--format` bash flags (e.g. `export_formats.md:152`) are correct as-is — I ran `limnalis export-ast examples/minimal_bundle.lmn --format yaml` and it worked; the CLI flag name is legitimately distinct from the Python kwarg name, so these should not be touched.
   - None of these 5 sites are in `COVERED_DOCS` (only the 3 wiring docs are gated), so they don't regress the item-1 acceptance bar and are correctly out of checkpoint 1's declared scope (checkpoint 1 item 1 never lists `export_formats.md` or `exchange_package_format.md`'s programmatic-API snippets).
2. **PrimitiveSet module location — real, but weaker than a "bug."** `PrimitiveSet` is defined once at `src/limnalis/runtime/runner.py:71` and is listed as an export of **both** `limnalis.api.plugins` (`plugin_sdk_overview.md:15`) and `limnalis.api.evaluator` (`plugin_sdk_overview.md:22`, also `architecture.md:103`, `release_candidate_status.md:57`, `adr/004-public-api-freeze.md:19`). I confirmed both import paths actually work and resolve to the identical class object (`from limnalis.api.evaluator import PrimitiveSet` and `from limnalis.api.plugins import PrimitiveSet` both print `<class 'limnalis.runtime.runner.PrimitiveSet'>`) — so this is not a broken import, just an undocumented dual public re-export with no doc stating the canonical defining module. Worth a one-line clarification when `plugin_sdk_overview.md`'s API-module table is expanded per PRD checkpoint-2 item 9 — not a functional defect.
3. **The stale src comment — real.** `src/limnalis/interop/envelopes.py:19-21`: `spec_version: str  # e.g. "0.2.2"`, `schema_version: str  # e.g. "0.2.2"`, `package_version: str  # implementation version e.g. "0.1.0"` — these three comments are now stale against the corrected doc values (`v0.2.2` / `0.2.2rc1`) confirmed live via `export-ast` above. Correctly left untouched: the milestone's hard constraint is "No changes to `src/` except NONE," and the PRD explicitly says "if a doc fix reveals a code bug, report it; do not patch."

**Verdict on Item 7: all three confirmed real; item 1 (`format=`) is more extensive than a single-site parenthetical implies — 5 concrete sites identified for checkpoint 2 planning.**

---

## Additional advisory (minor, non-blocking, pre-existing, not in this diff)

`docs/downstream_artifact_consumption.md:51,62` still show non-`v`-prefixed `"spec_version": "0.2.2"` inside two elided example literals (`'{"spec_version": "0.2.2", ...}'` and `{"spec_version": "0.2.2", "schema_version": "0.2.2", ...}`). These are explicitly truncated with `...` (not valid JSON/runnable on their own), untouched by this diff, and distinct from the specific "6 places" `package_version: "0.1.0"` fix list the PRD named — so not a checkpoint-1 gap, just a loose end worth a follow-up pass whenever that file is next touched.

## Verdict: PASS_WITH_ADVISORIES

Checkpoint 1's four declared items are correctly, precisely, and verifiably implemented — every fixed snippet checked against the real current signatures by reading the source and then confirmed by actually running 16/16 gated tests plus 5 hand-copied snippets outside the harness; the marker-extraction mechanism was probed adversarially (scratch-only, no repo files added) and behaves exactly as documented; the diffs are surgical with no overcorrection found in any of the 9 files; install instructions and the field-contract corrections are accurate and independently verified against a real `export-ast` run, `version.py`, and `pyproject.toml`; scope is exactly the stated 9 docs + 1 test file with `spec/`/`schemas`/`fixtures/` byte-untouched and the full suite green at exactly 1110. All three checkpoint-2 handoff items are confirmed real (not fabricated), with the `format=` item found to be somewhat broader in extent (5 concrete sites across 3 files) than "the one fixed site" phrasing alone would suggest — useful precision for checkpoint 2 scoping, not a defect in this checkpoint.

## Required Changes: none (advisories only, none blocking)

- Record the checkpoint-2 handoff list (now with the 5 concrete `format=`/`input_format=`/`output_format=` sites above) in `.armature/session/state.md` or `.armature/journal.md` before/when this checkpoint is committed, so it survives beyond this review.

## Rollback Recommendation: NO

No invariant violation, no scope violation, no regression. Safe to commit checkpoint 1 as-is.
