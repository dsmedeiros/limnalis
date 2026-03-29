# Red Team Review: m5-rt-normalizer-models

## Summary

Two narrow changes reviewed: D5 (logical operators data structure change) and D7 (dead code removal). Both are semantically safe -- the dict-to-list refactor produces identical iteration behavior under Python 3.7+ insertion-order guarantees, and the removed class has zero consumers. No critical or high findings. One pre-existing issue (unused `field_validator` import) was already flagged by the prior red team review but remains unaddressed. The primary concern is a MEDIUM-severity test gap: the precedence ordering that D5 now explicitly documents is not enforced by any test or fixture.

## Critical Findings

None.

## Subtle Issues

1. **Unused `field_validator` import persists in `base.py` (pre-existing, still unresolved)**
   - File: `/home/user/limnal/src/limnalis/models/base.py`, line 3
   - `field_validator` is imported from pydantic but never used anywhere in this file. This was flagged as advisory A1 in the prior red team review (`m5-defect-remediation-redteam.md`) but was not addressed. Neither the removed `UniqueStringListModel` nor `LimnalisModel` uses `field_validator` -- the import was dead before D7 and remains dead after.
   - Severity: LOW (no behavioral impact; lint noise)

2. **D5 comment makes a stronger claim than what is enforced**
   - File: `/home/user/limnal/src/limnalis/normalizer.py`, line 100
   - The comment "Ordered by precedence: first match wins (highest precedence first)" documents an invariant that no test verifies. If a future developer reorders the list (e.g., alphabetically: AND, IFF, IMPLIES, OR -- which happens to be the current order, or reverses it), behavior could change silently. The old `dict` had the same implicit ordering but made no explicit claim about it. The new comment raises the bar for what should be tested.
   - Severity: MEDIUM (documented invariant without enforcement)

## Test Gaps

1. **No test exercises logical operator precedence**
   - Every logical expression in the fixture corpus and snapshot files uses only the `and` operator. No fixture or test includes expressions with multiple different operators at the same nesting level (e.g., `(A AND B OR C)` or `(X IMPLIES Y IFF Z)`). This means the iteration order of `_LOGICAL_OPERATORS` -- which D5 explicitly identifies as a precedence order -- has zero test coverage.
   - The "first match wins" parsing strategy in `_parse_expr_text` (line 1035) means the iteration order directly determines which operator binds at each level. Reordering the list would silently change parse results for mixed-operator expressions. With no test enforcing the order, this is a regression waiting to happen.
   - Severity: MEDIUM

2. **No test verifies `IFF`, `IMPLIES`, or `OR` operators in isolation**
   - All fixture and snapshot logical expressions use `and`. The `iff`, `implies`, and `or` code paths in the normalizer are exercised only if there are test inputs using those operators, and grep confirms there are none in the snapshot corpus. These operators are essentially untested at the normalizer level.
   - Severity: MEDIUM

## Semantic Drift Risks

1. **The precedence order AND > IFF > IMPLIES > OR is asserted by comment only**
   - Whether this order is correct for Limnalis semantics cannot be verified from the test suite alone. Standard logic convention would typically give AND highest precedence and OR lowest, which matches. However, IFF and IMPLIES placement varies by convention (some systems give IMPLIES lower precedence than IFF, others the reverse). Without a specification document or test encoding the expected precedence, the correctness of this order is an unverifiable assertion.

2. **`LimnalisModel` integrity is intact but `field_validator` import is misleading**
   - A reader of `base.py` would assume `field_validator` is used somewhere in the file. It is not. This is minor but contributes to semantic drift -- the import list promises functionality that the module does not use.

## Verification Results

- `python -m pytest tests/test_normalizer.py -q`: 22 passed
- `python -m pytest tests/test_ast_models.py -q`: 8 passed
- `python -m pytest tests/ -q`: 313 passed
- MODEL-001 (LimnalisModel inheritance): Confirmed -- `LimnalisModel` inherits from `BaseModel`, all AST models import from `.base`
- MODEL-002 (extra='forbid'): Confirmed -- `extra="forbid"` present in `LimnalisModel.model_config`
- NORM-001 (determinism): No change to determinism -- list-of-tuples has fixed iteration order identical to the prior dict
- Dict-vs-list equivalence: Verified programmatically -- `list(old_dict.items()) == new_list` is `True`
- Zero consumers of `UniqueStringListModel`: Confirmed -- grep finds no imports, no references in `__init__.py`, no usage in tests

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **A1 (LOW, carried forward):** Remove unused `field_validator` import from `/home/user/limnal/src/limnalis/models/base.py` line 3. This was flagged in the prior red team review and remains unaddressed.
- **A2 (MEDIUM, carried forward):** Add a test that verifies logical operator precedence order. A test parsing `(A AND B OR C)` and asserting AND binds tighter than OR would lock in the documented behavior. Without this, the precedence comment on line 100 of `normalizer.py` is an unenforced specification.
- **A3 (MEDIUM):** Add at least one test exercising each of `IFF`, `IMPLIES`, and `OR` logical operators through the normalizer. These code paths currently have zero coverage in the fixture corpus.
