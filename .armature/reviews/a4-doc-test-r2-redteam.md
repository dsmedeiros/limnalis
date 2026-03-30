# Red Team Review: a4-doc-test-r2

## Summary

Documentation-only changeset adding comments to `ast.py` and `test_normalizer.py`, plus one new test. All factual claims in the comments are verified against the JSON schema, runtime code, and loader. The new test passes and exercises the correct code path. No invariants are violated. No issues found.

## Critical Findings

None.

## Subtle Issues

None. Every claim in the added comments was cross-referenced:

- The JSON schema at `schemas/limnalis_ast_schema_v0.2.2.json` lines 686-701 confirms the `if kind=moving then evaluationMode must be tracked` constraint via `allOf[].if/then`.
- The runtime at `src/limnalis/runtime/builtins.py` line 639 confirms the `baseline_mode_invalid` diagnostic emission for `kind=moving` with `eval_mode != tracked`.
- The loader at `src/limnalis/loader.py` line 28 confirms `normalize_surface_text` accepts `validate_schema=True` (it is the default).
- The schema module at `src/limnalis/schema.py` line 33 confirms `SchemaValidationError` is the correct exception type raised by `validate_payload`.
- Commit `549e3ce` exists and its message is consistent with the referenced change.
- The A4 exclusion comment correctly cross-references `test_normalizer_accepts_invalid_moving_baseline_fixture` at line 108.

## Test Gaps

None introduced by this changeset. The new test `test_a4_public_api_rejects_moving_fixed_baseline` directly exercises the public API path (`normalize_surface_text` with `validate_schema=True`) and asserts `SchemaValidationError` is raised. It is not tautological -- it proves that the schema constraint rejected by the JSON schema is enforced at the public API layer.

## Semantic Drift Risks

None. The comments accurately describe the current architecture's intentional layering of constraints (model permissive, schema strict, runtime diagnostic).

## Verdict: PASS

No blocking issues. No advisories. The changeset is accurate documentation of an existing intentional design decision, and the new test adds meaningful coverage.
