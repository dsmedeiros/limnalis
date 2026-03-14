# Review Verdict: pr4-review-fixes-2

**Scope:** src/limnalis/runtime, tests
**Invariants checked:** RUNTIME-001, RUNTIME-002, RUNTIME-003, RUNTIME-004
**Verdict:** PASS
**Confidence:** high

## Scope Compliance
- Declared scope: src/limnalis/runtime, tests
- Files modified: src/limnalis/runtime/runner.py, src/limnalis/runtime/builtins.py, tests/test_runtime_runner.py
- Out-of-scope modifications: none

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| RUNTIME-001 | PASS | 12 phases execute in strict ascending order (1-12). Phase swap (build_step_context=1, resolve_ref=2) is internally consistent: docstring, comments, trace event phase numbers, and test expectations all agree. Test `test_trace_contains_all_12_phases` asserts `phases == list(range(1, 13))`. Test `test_trace_primitive_names_match` asserts correct primitive-to-phase mapping. |
| RUNTIME-002 | PASS | All primitives follow uniform shape `op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)`. Stubs and builtins consistent. |
| RUNTIME-003 | PASS | NoteExpr claims bypass eval_expr (runner.py line 393) and synthesize_support (line 426). Non-evaluable claims receive N/non_evaluable_note/inapplicable EvalNodes in phase 9. Four dedicated tests verify this behavior. |
| RUNTIME-004 | PASS | PrimitiveSet dataclass holds all 13 primitives with builtin defaults. compose_license included with comment documenting it has no runner phase yet. All stubs raise NotImplementedError. Tests verify custom injection flows through to results. |

## Change Verification

1. **compose_license comment** (runner.py lines 77-78): Present. Documents Protocol contract status and deferred scheduling.
2. **empty_effective_frame diagnostic** (builtins.py lines 125-131): Warning diagnostic emitted when all merged facets are None before `_facets_to_frame`. Code is `"empty_effective_frame"`, severity is `"warning"`.
3. **Module-level numbering note** (builtins.py lines 6-9): Explains section numbering follows Protocol numbering (1-13), not runner phase numbering (1-12).
4. **paraconsistent_union member filtering** (builtins.py lines 372-375): `per_evaluator` is filtered to `policy.members` when members is non-empty. Falls back to unfiltered when members is empty. Correct.
5. **B truth conflict support override** (builtins.py lines 388-391): When T and F are both present in truth set (producing B), `agg_support` is overridden to `"conflicted"`. Correct.
6. **Phase order swap** (runner.py lines 211-237): build_step_context runs as phase 1, resolve_ref as phase 2. Docstring (lines 177-178), comments, and trace events all reflect the new ordering. step_ctx is initialized before resolve_ref receives it. Test expectations updated to match.

## Test Results

All 51 tests pass (34 primitives + 17 runner). No warnings other than an unrelated importlib deprecation.

## Findings

No issues found.

## Recommendations

None.
