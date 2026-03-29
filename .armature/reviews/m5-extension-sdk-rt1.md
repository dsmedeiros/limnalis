# Red Team Review: m5-extension-sdk-rt1

## Summary

The Milestone 5 Extension SDK changeset is well-structured and passes all 439 tests, all CLI stress tests, and all consumer examples. The plugin registry, fixture plugin pack, example packs, public API surface, and CLI additions are functionally correct for all tested scenarios. However, the code contains one subtle logic error in an exported-but-unused handler class, a coupling to private functions that creates a fragile dependency, and several test gaps that would allow regressions in edge cases. No critical-severity findings. Overall quality is solid; the standard reviewer's PASS verdict is defensible, but I identify additional issues below that the standard review missed.

## Critical Findings

None.

## Subtle Issues

### S1. FixtureEvalHandler returns arbitrary evaluator result for multi-evaluator claims (MEDIUM)

**File:** `src/limnalis/plugins/fixtures.py`, lines 55-61

`FixtureEvalHandler.__call__` iterates `ev_truths.items()` and returns the first entry it finds, regardless of which evaluator the handler is supposed to represent. This means for claims with multiple evaluators (e.g., `{"ev1": TruthCore(truth="T"), "ev2": TruthCore(truth="F")}`), the handler always returns whichever evaluator happens to be iterated first. This is nondeterministic in the semantic sense (depends on dict insertion order) and incorrect if the caller expects evaluator-scoped results.

This class is exported in `__all__` and importable by downstream consumers, but is NOT used by `register_fixture_plugins` (which correctly uses `FixtureEvalHandlerForEvaluator` instead). The risk is that a downstream consumer imports `FixtureEvalHandler` (it's in the public exports), uses it, and gets silently wrong results for multi-evaluator fixtures.

**How to trigger:** Construct a truth_map with 2+ evaluators for a claim, instantiate `FixtureEvalHandler(truth_map)`, call it. It returns the first evaluator's truth regardless of which evaluator the caller intended.

**Severity:** MEDIUM -- not triggered by any current code path, but exported as public API.

### S2. FixtureAdjudicator imports private underscored functions from runtime.builtins (MEDIUM)

**File:** `src/limnalis/plugins/fixtures.py`, line 185

`FixtureAdjudicator.__call__` does a deferred import of `_aggregate_truth` and `_aggregate_support` from `..runtime.builtins`. These are private (underscore-prefixed) functions. If the builtins module refactors or renames these functions, the FixtureAdjudicator breaks silently (the deferred import means the breakage only manifests at runtime when the mixed-truth-non-conflict path is hit). This is a coupling hazard.

**How to trigger:** Rename `_aggregate_truth` in builtins.py. No test fails until a conformance case with mixed truths (not T-vs-F) is processed through the adjudicator.

**Severity:** MEDIUM -- fragile internal coupling to private API.

### S3. CLI `plugins list --kind nonexistent_kind` exits 0 with empty output (LOW)

**File:** `src/limnalis/cli.py`, line 1019

When `--kind` specifies a kind that doesn't exist, the CLI prints a header row with no data and exits 0. This is defensible (empty results are a valid result set), but deviates from the `plugins show` pattern which returns exit code 1 for missing plugins. Inconsistent UX between "list --kind" and "show" for nonexistent targets.

**Severity:** LOW -- design choice, not a bug.

### S4. PluginRegistry not thread-safe for concurrent registration (LOW)

**File:** `src/limnalis/plugins/__init__.py`, line 79

The docstring claims "Thread-safe for read operations after registration." The read-after-write safety relies on CPython's GIL, which is not a portable guarantee (e.g., free-threaded Python 3.13t, other implementations). More importantly, `register()` and `unregister()` are not protected by any lock, so concurrent registration from multiple threads can corrupt the `_plugins` dict. This is acceptable for the current single-threaded usage pattern but the docstring overpromises.

**Severity:** LOW -- no current multi-threaded usage.

## Test Gaps

### T1. No test for FixtureEvalHandler (the non-ForEvaluator variant)

**File:** `tests/test_fixture_plugin_pack.py`, line 181

The test class `TestFixtureEvalHandler` exists (line 181) but every test method within it actually tests `FixtureEvalHandlerForEvaluator`, not `FixtureEvalHandler`. The base `FixtureEvalHandler` class has zero test coverage. Its buggy iteration-returns-first behavior (see S1) is not caught. The test class name is misleading.

### T2. No test for FixtureAdjudicator mixed-truth-non-conflict path

**File:** `tests/test_fixture_plugin_pack.py`, class `TestFixtureAdjudicator`

Tests cover: empty input (N), agreement (all T), and conflict (T vs F). Missing: mixed truths that are NOT T-vs-F (e.g., T and N, or T and B). This path hits the deferred import of `_aggregate_truth`/`_aggregate_support` (line 185-196 of fixtures.py). If that import breaks, no test catches it.

### T3. No negative test for `plugins list --kind` with nonexistent kind via JSON output

The test `test_plugins_list_kind_filter_json` only tests with a valid kind. No test verifies that `--kind nonexistent --json` returns an empty JSON array `[]` rather than an error or malformed output.

### T4. Grid/JWT handler tests don't exercise input-dependent logic

The grid and JWT handlers are currently hardcoded (always return the same TruthCore regardless of input). The tests verify only the hardcoded output. When these handlers are later made input-dependent (as the "not production-ready" disclaimer suggests), no test structure exists to catch regressions in input handling. This is acceptable for example code but should be noted.

### T5. No test for FixtureSupportHandler's `default_synth` fallback path

**File:** `src/limnalis/plugins/fixtures.py`, lines 120-127

The `FixtureSupportHandler` has a `default_synth` parameter that accepts a fallback callable. When the fallback returns a tuple, line 126 extracts `result[0]`. No test covers the `default_synth` path at all -- neither the tuple case nor the non-tuple case.

### T6. No test for `_has_adjudicated_policy` with non-dict aggregate

**File:** `src/limnalis/plugins/fixtures.py`, line 283

`_has_adjudicated_policy` checks `isinstance(agg, dict)` before accessing `agg.get("reason")`. No test verifies behavior when `aggregate` is a non-dict value (e.g., a string or None).

## Semantic Drift Risks

### D1. `FixtureEvalHandler` vs `FixtureEvalHandlerForEvaluator` naming confusion

Both classes are exported. `FixtureEvalHandler` is the buggy one that ignores evaluator identity. `FixtureEvalHandlerForEvaluator` is the correct one. The naming suggests `FixtureEvalHandler` is the base/default and `FixtureEvalHandlerForEvaluator` is the specialized variant. A plugin author who reads the `__all__` list would likely reach for `FixtureEvalHandler` first, getting the wrong behavior.

### D2. `build_services_from_registry` silently omits ADJUDICATOR and CRITERION_BINDING

The `build_services_from_registry` function (lines 181-210 of `__init__.py`) builds a services dict from the registry but only handles `EVALUATOR_BINDING`, `EVIDENCE_POLICY`, and `ADEQUACY_METHOD`. It does not wire up `ADJUDICATOR`, `CRITERION_BINDING`, `TRANSPORT_HANDLER`, `BASELINE_HANDLER`, or `BINDING_RESOLVER` plugins. These kinds can be registered but `build_services_from_registry` silently ignores them. No documentation or diagnostic indicates this limitation.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

1. **S1/T1 (MEDIUM):** `FixtureEvalHandler` is exported but buggy for multi-evaluator claims and has no test coverage. Either add tests and fix the class, or remove it from `__all__` and mark it as deprecated/internal.

2. **S2/T2 (MEDIUM):** `FixtureAdjudicator` depends on private `_aggregate_truth`/`_aggregate_support` functions via deferred import. The mixed-truth-non-conflict code path has no test coverage. Add a test for this path.

3. **T5 (MEDIUM):** `FixtureSupportHandler.default_synth` fallback (including tuple-unwrap) is untested. Add coverage.

4. **D2 (MEDIUM):** `build_services_from_registry` silently ignores 5 of 8 plugin kinds. Document this limitation or wire up the remaining kinds.

5. **S3 (LOW):** CLI `plugins list --kind nonexistent_kind` exits 0 (inconsistent with `plugins show` which exits 1 for missing targets). Consider whether this inconsistency is intentional.
