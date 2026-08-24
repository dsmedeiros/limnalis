# Review Verdict: m7-t2-normalizer-precedence

## Scope Compliance
- Declared scope: `src/limnalis/normalizer.py` + its tests (Milestone 7 PRD, T2:
  `.taskmaster/docs/milestone-7-remediation-track-c.md`)
- Files modified (`git diff 73c0154`):
  - `src/limnalis/normalizer.py` (+369/-... net +315/-54 per task framing)
  - `tests/test_operator_precedence.py` (rewritten, 23 -> 42 `def test_` functions, confirmed by grep)
- `git status --porcelain`: exactly these two files. `git diff --stat 0994537 -- fixtures/ schemas/ spec/`: empty.
  Nothing under `fixtures/`, `schemas/`, `spec/`, `src/limnalis/runtime/` touched.
- Out-of-scope modifications: none.
- `restricted` actions from `src/limnalis/agents.md` frontmatter (`cross-cutting-changes`,
  `schema-migration`, `model-changes`): none present.

## Hand-derivation vs. EBNF (spec/Limnalis-v0.2.2-reconstructed.md A.9, lines 1229-1281)

I derived trees by hand from the grammar (`Expr::=JudgedExpr`; `IffExpr::=ImplExpr{IffOp ImplExpr}`;
`ImplExpr::=OrExpr{ImplOp OrExpr}`; `OrExpr::=AndExpr{OrOp AndExpr}`; `AndExpr::=UnaryExpr{AndOp UnaryExpr}`;
`UnaryExpr::=[NotOp]CoreExpr`) independently of the tests, then ran every case live
(`PYTHONPATH=src python`, harness in scratchpad). All 12 matched exactly:

| Input | Hand-derived | Actual (normalizer) |
|---|---|---|
| `(a AND b OR c)` | OR(AND(a,b), c) | OR(AND(a,b), c) match |
| `(a OR b AND c)` | OR(a, AND(b,c)) | OR(a, AND(b,c)) match |
| `(a IMPLIES b IFF c)` | IFF(IMPLIES(a,b), c) | IFF(IMPLIES(a,b), c) match |
| `(NOT a AND b)` | AND(NOT(a), b) | AND(NOT(a), b) match |
| `NOT (a AND b)` | NOT(AND(a,b)) | NOT(AND(a,b)) match |
| `a AND b OR c` (bare) | OR(AND(a,b), c) | OR(AND(a,b), c) match |
| `(a -> b)` | IMPLIES(a,b) | IMPLIES(a,b) match |
| `(a <=> b)` | IFF(a,b) | IFF(a,b) match |
| `p(x) =>[obs] q(y) judged_by policy://k` | Judged(Causal(obs,p(x),q(y)),k) | same, match |
| `x =>[obs] y AND z` | AND(Causal(obs,x,y), z) | AND(Causal(obs,x,y), z) match |
| `a --> \|0:b\|` | Dynamic(approaches,a,Baseline(b)) | same, match |
| `(TARIFF AND BRAND)` | AND(TARIFF, BRAND) (no split on embedded "AND" in BRAND / "IFF" in TARIFF) | AND(TARIFF, BRAND) match |

Traced through the code, the correctness of the AND/BRAND and IMPLIES/`-->` cases rests on two
specific, correctly-implemented mechanisms in `_match_logical_operator`
(`src/limnalis/normalizer.py:1168-1200`): (1) word spellings require a whitespace character
immediately before *and* after the match (`normalizer.py:1183-1187`), which is what stops "AND"
matching inside "BRAND" (preceded by 'R', not whitespace) while still matching the real operator;
(2) the `"->"` symbol match is explicitly rejected when the preceding character is `-` or `<`, or the
following character is `>` (`normalizer.py:1195`), which is what stops it firing inside `-->`.
`x =>[obs] y AND z` binds correctly because the AND/OR/IMPLIES/IFF split in `_parse_expr_text`
(`normalizer.py:1028`) runs *before* `_parse_core_expr_text` ever gets a chance to recognize the
causal marker (`normalizer.py:1103`) — i.e. AndExpr is structurally outside CoreExpr per the
grammar, and the implementation's call order preserves that.

## Adversarial hunt (own inputs, beyond the task's minimum list)

All run live via `PYTHONPATH=src python`; results in scratchpad `adversarial.py`.

Clean (no leaked operator text, no crash, correct shape):
- Nested/mixed spellings: `((a ∧ (b OR c)) -> (NOT d <=> e))` -> `IMPLIES(AND(a,OR(b,c)), IFF(NOT(d),e))`.
- Quoted-string shielding: `(msg("a AND b OR c") AND d)` -> the string argument is preserved verbatim
  inside a `StringTerm`, outer AND still splits correctly.
- `¬` abutting its operand, with and without parens: `¬a ∨ b`, `¬(a ∧ b)` both correct.
- ASCII `->` with **zero** surrounding whitespace inside an otherwise-normal expression: `(a->b)` ->
  `IMPLIES(a,b)` (symbol forms are deliberately allowed to abut their operands per
  `normalizer.py:1176`).
- Multiple/irregular whitespace (extra spaces, tabs, embedded newline) around `AND`: all correct —
  the boundary check only requires *a* whitespace char, not a specific count or type.
- `declare x as y within @{system=Test, ...}` (frame-pattern `within`): unaffected, correct.
- `a AND AND b` (doubled operator): correctly raises `NormalizationError: ... missing an operand`
  (`normalizer.py:1081` region, the `any(not part for part in parts)` guard).

Two genuine defect classes found (both confirmed **pre-existing**, not introduced by this diff — see
verification method below):

1. **`note`/`declare`-rooted top-level claims never reach the judged_by/logical pipeline.**
   `_normalize_claim_expr` (`normalizer.py:877-890`) still special-cases
   `tokens[0] == "note"` (line 880) and `tokens[0] == "declare"` (line 882), dispatching straight to
   `_parse_note`/`_parse_declaration` on the *raw* token list — the same pattern that used to also
   apply to causal and EMRG, but the causal/EMRG branches were deliberately removed by this diff so
   those forms now flow through `_parse_expr_text` (comment at `normalizer.py:884-889` explicitly
   says why). `note`/`declare` were not given the same treatment. Repro:
   - `note "x" judged_by policy://k` (bare, top-level) -> **crashes**:
     `NormalizationError: invalid string literal '"x" judged_by policy://k'`, because `_parse_note`
     (`normalizer.py:892-901`) tries to `ast.literal_eval` the whole remainder including
     `judged_by policy://k` as one Python string.
   - `note "x" AND note "y"` -> same crash mode.
   - `declare x as y judged_by policy://k` -> **does not crash, silently wrong**: parses to
     `DeclarationExpr(declaredAs="y judged_by policy://k")` — `judged_by` text is absorbed into the
     `declaredAs` scalar because `_parse_declaration`'s `declared_as_end`
     (`normalizer.py:910`) only knows about `within`, not `judged_by`.
   - `declare x as y AND b` -> same silent-absorption pattern (`declaredAs="y AND b"`).
   - Wrapping the *identical* expressions in one extra pair of parens works correctly:
     `(note "x" judged_by policy://k)` -> `Judged(Note("x"), "policy://k")`, and
     `(declare x as y judged_by policy://k)` -> `Judged(Declaration(x,y), "policy://k")`. This
     confirms the dispatch logic in `_parse_core_expr_text` (`normalizer.py:1103`, the
     `words[0]=="note"`/`"declare"` branches) is itself correct — the bug is only that the
     unparenthesized top-level entry point bypasses it.
   - **Verified pre-existing**: I checked out `73c0154` (pre-T2, T1-only) into a scratch worktree and
     ran the identical four inputs — byte-identical crash/silent-corruption behavior. This diff did
     not introduce or worsen this; it fixed the analogous causal/EMRG case but left the note/declare
     case in its prior broken state.
   - Not exercised by the vendored corpus, the examples, or any of the 42 new / 910 total tests
     (confirmed by grep for `judged_by` co-occurring with `note`/`declare` across
     `fixtures/`, `examples/`, `tests/`).

2. **Boundary-adjacent malformed word operators are silently swallowed rather than rejected**
   (lower severity, also pre-existing). `_match_logical_operator` requires `index > 0`
   (`normalizer.py:1183`) and `end < len(text)` (`normalizer.py:1185`), so a word operator occupying
   the very first or very last position of a (stripped) expression can never be recognized as an
   operator. `AND b` -> `PredicateExpr(name="AND b")`; `a AND` -> `PredicateExpr(name="a AND")` —
   both silent, no diagnostic, rather than a clear normalization error. This is invalid input per the
   grammar to begin with (AndExpr requires a preceding UnaryExpr), so its being silently accepted
   is a permissiveness/robustness gap rather than a correctness bug for well-formed EBNF input; I
   list it for completeness since it does technically produce a `PredicateExpr` whose name contains
   an operator token, which is the exact pattern this changeset otherwise correctly eliminates for
   valid input.

3. **Zero-whitespace causal/dynamic markers** (`x=>[obs]y`, `a-->|0:b|` with no surrounding spaces)
   are not recognized and collapse to a single opaque `PredicateExpr`. Root cause is
   `_split_words` (`normalizer.py:1267`) / the `"-->" in words` check (`normalizer.py:1127`), which
   only recognize these markers when they arrive as their own whitespace-delimited word — a property
   of how the token stream reaches the text-splitter, not of the AND/OR/IFF/IMPLIES precedence engine
   this diff targets. **Verified pre-existing** via the same 73c0154 worktree comparison: identical
   failure mode, including for `a --> |0:b|` *with* normal spacing under the old code (which never
   attempted `-->` recognition at all before this diff added it). Fixing the zero-whitespace case
   would require grammar/lexer changes (`grammar/limnalis.lark`, `src/limnalis/parser.py`), which are
   outside this changeset's declared scope and outside Milestone 7 T2's file list.

None of these three findings regress previously-passing behavior, none are reachable from the
vendored fixture corpus or the example files, and none are newly asserted (incorrectly or otherwise)
by the rewritten test file.

## Test audit (`tests/test_operator_precedence.py`)

- 42 `def test_` functions (grep-confirmed) vs. 23 in the pre-T2 version at `73c0154`.
- Every assertion goes through a `_shape()` helper (`test_operator_precedence.py:101-129`) that
  renders the **full** nested tree as a tuple (operator, then recursively-shaped args; predicates
  distinguish bare-name vs. call form; Judged/Causal/Dynamic/Emergence nodes carry their own
  sub-shapes) — confirmed this is not a root-only check.
- Every test class and most individual tests cite specific EBNF line numbers in their docstrings,
  keyed to the same `spec/Limnalis-v0.2.2-reconstructed.md` line range the module docstring cites
  (1229-1281).
- Diffed the removed 23 against the new 42, then independently verified (not trusting either file)
  by re-running the removed tests' literal input strings against the new normalizer:
  - The old `TestLogicalOperatorPrecedence.test_precedence_first_match_wins_*` (6 tests) and
    `TestReverseOrderPrecedence.*` (3 tests) asserted that an unsplit remainder becomes a
    `PredicateExpr` literally named e.g. `"b OR c"` or `"a IMPLIES b"` — i.e. exactly the
    swallowed-operator defect this changeset fixes. Of these 9, 6 have an exact 1:1 replacement in
    the new file using the *identical* input string with the corrected assertion (e.g. old
    `test_precedence_first_match_wins_and_over_or("(a AND b OR c)")` asserting the broken
    `AND(a, pred("b OR c"))` -> new `test_and_binds_tighter_than_or` asserting the correct
    `OR(AND(a,b), c)` for the same string). The remaining 3 (`iff_over_or`, `and_over_implies`,
    `implies_over_or` literal orderings) are not re-tested under the identical string but are
    covered transitively by the adjacent-pair tests plus `test_full_precedence_chain`; I hand-ran all
    three original strings live and confirmed correct output in each case (see table above's method).
  - The old `test_*_binds_tighter_than_*` tests (6 tests) used explicit double-parenthesization,
    which forces structure regardless of algorithm correctness — 3 of the 6 (`and_binds_tighter_*`)
    stated a true general precedence claim; the other 3 (`iff_binds_tighter_than_or`,
    `implies_binds_tighter_than_or`, `iff_binds_tighter_than_implies`) stated the relationship
    **backwards** from the actual spec order (spec: NOT>AND>OR>IMPLIES>IFF, so OR binds tighter than
    both IMPLIES and IFF, and IMPLIES binds tighter than IFF — the opposite of those three names),
    even though their forced-parenthesization assertions still evaluate true today. The rewrite
    replaces all six with correctly-named, *unparenthesized* (harder, precedence-derived rather than
    grouping-forced) equivalents. This is a strict improvement, not a loss of correct coverage.
  - `test_deeply_nested_mixed_operators` (explicit full parenthesization) and
    `TestEachLogicalOperatorInIsolation`'s four single-operator tests carry over with unchanged
    assertions (single-operator ones now routed through `_shape()`).
  - I found no case of a uniquely-correct assertion being deleted without an equivalent or stronger
    replacement elsewhere.
- The three documented ambiguity resolutions are present and cited:
  - Flat n-ary associativity: `TestRepeatedOperatorAssociativity` (`test_operator_precedence.py:400-440`),
    explicit "Documented choice" rationale citing the `{ Op ... }` EBNF repetition.
  - Causal binds tighter than the logical layer: `TestOperatorTokenNonCollision.test_causal_operands_compose_with_logical_layer`
    (`test_operator_precedence.py:544-552`), citing CausalExpr's SimpleExpr operands (line 1249).
  - judged_by attaches outermost, after clause-bearing forms: `TestJudgedByOutermost`
    (`test_operator_precedence.py:448-500`), including the causal case and a parenthesized-inner-judged_by
    counter-case (`test_parenthesized_judged_by_stays_inner`).

## Determinism (NORM-001)

Ran the normalizer twice on four expressions of varying complexity (including a full
IFF/IMPLIES/OR/AND chain, a fully-parenthesized nested mix, a judged causal claim, and a
NOT/AND/OR/IMPLIES/IFF combination), comparing `model_dump(mode="json")` with `sort_keys=True`:
all four identical across both runs. **PASS.**

## Regression / conformance

- `PYTHONPATH=src python -m pytest tests/ -q`: **910 passed**, 0 failed, 0 errors (confirmed via
  exit code 0 and an unsuppressed run showing `910 passed in 87.20s`; matches the task's expected count).
- `PYTHONPATH=src python -m pytest tests/test_conformance.py -v`: **41 passed** (includes the 16/16
  vendored fixture cases).
- All 5 `examples/*.lmn` files normalize successfully via
  `PYTHONPATH=src python -m limnalis normalize <file>` (exit 0, no stderr).

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| NORM-001 (Normalizer Determinism) | PASS | Verified directly (two independent runs, JSON-diffed) on 4 nontrivial expressions; also implicitly covered by `tests/test_normalizer.py` in the 910-test run. |
| FIXTURE-001 (Fixture Conformance Authority) | PASS | 16/16 vendored cases green via `tests/test_conformance.py` (41/41 total); vendored fixture/schema/spec files byte-unchanged (`git diff --stat` empty for those dirs). |
| PARSER-001/002/003 | N/A | `grammar/limnalis.lark` and `src/limnalis/parser.py` not touched by this diff. |
| MODEL-001/002 | N/A | No changes to `src/limnalis/models/`; AST node shapes (LogicalExprNode, JudgedExprNode, etc.) are unchanged, only how the normalizer arrives at them. |
| SCHEMA-001 | PASS | Full suite includes `tests/test_schema_validation.py`; all outputs still validate. |
| NORM-002 (Diagnostic Coverage) | PASS (unaffected) | Diagnostic call-site count/shape in the diff is unchanged from `73c0154` (same `_append_diagnostic` locations); this changeset neither adds nor removes diagnostic coverage for expression-parsing decisions, consistent with pre-existing behavior. |
| NORM-003 (Canonical Output) | PASS | One input maps to one deterministic tree; confirmed above. |

## Verdict: PASS_WITH_ADVISORIES

The core T2 deliverable is correctly and thoroughly implemented: the precedence table is
loosest-first or `[iff, implies, or, and]` (`normalizer.py:36-41`) which correctly yields
tightest-to-loosest binding NOT>AND>OR>IMPLIES>IFF under the first-match-splits algorithm; every
split remainder recurses through the same EBNF-driven pipeline so no valid construct collapses into
an operator-bearing predicate name; NOT is a genuine prefix unary that binds tighter than every
binary operator; `judged_by` is correctly outermost for causal, emergence, logical, and bare-predicate
forms; canonical `->`/`<=>` and the five Unicode operators are accepted as aliases sharing the same
canonical `op` value as their word-form/legacy counterparts; legacy `IMPLIES`/`IFF` words still work;
`-->` and `=>[obs]`/`=>[do]` do not collide with the new `->`/`<=>` matching. All of this was verified
independently by hand-derivation against the cited EBNF lines and by live execution, not by trusting
the new tests. Determinism, the full 910-test suite, 16/16 vendored conformance, and all
`examples/*.lmn` are green, and the changeset is scope-clean.

Advisories (not blocking, recommended as a small tightly-scoped follow-up, not a re-delegation of T2):
1. Extend the same fix already applied to causal/EMRG to `note`/`declare`: remove the
   `tokens[0] == "note"` / `tokens[0] == "declare"` early-exits in `_normalize_claim_expr`
   (`normalizer.py:880-883`) and let those forms fall through to `_parse_expr_text`, relying on the
   already-correct `words[0]=="note"`/`"declare"` dispatch inside `_parse_core_expr_text`
   (`normalizer.py:1103` region) to handle them post-judged_by-split. This closes a real crash
   (`note ... judged_by ...`) and a real silent-data-corruption case (`declare ... judged_by/AND ...`)
   for unparenthesized top-level claims, both pre-existing and unrelated to the vendored corpus, but
   both directly on-theme with T2's "Expr ::= JudgedExpr is outermost" objective.
2. Consider a diagnostic/error (rather than silent acceptance) when a word operator sits at the very
   start or end of a (sub)expression with no operand on that side (`normalizer.py:1183`,
   `normalizer.py:1185` boundary guards) — currently silently becomes a literal predicate name (e.g.
   `AND b`, `a AND`). Low severity: only reachable via already-invalid-per-grammar input.
3. Zero-whitespace `=>[obs]`/`-->` markers (e.g. `x=>[obs]y`) collapse to an opaque predicate; fixing
   this needs grammar/lexer work outside `normalizer.py` and is explicitly out of this changeset's
   file scope — flagged for awareness only.

## Rollback Recommendation: NO
No regression was introduced; all required gates (determinism, full suite, conformance, examples,
scope) pass. The advisories describe pre-existing, narrowly-scoped gaps outside the vendored/tested
surface, not a defect in what this changeset delivers.
