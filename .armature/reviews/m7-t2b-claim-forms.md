# Review Verdict: m7-t2b-claim-forms

## Scope Compliance

- Declared scope: `src/limnalis/normalizer.py` (working-tree diff against HEAD `3692f57`, the
  committed T2 changeset) + new `tests/test_normalizer_claim_forms.py`. PRD:
  `.taskmaster/docs/milestone-7-remediation-track-c.md` (Milestone 7, T2 remediation track /
  "T2b"). Origin: advisories 1-3 of `.armature/reviews/m7-t2-normalizer-precedence.md`.
- Files modified:
  - `src/limnalis/normalizer.py` — `git diff --stat`: `271 insertions(+), 47 deletions(-)`.
  - `tests/test_normalizer_claim_forms.py` — new file, 56 tests.
- Out-of-scope check: the working tree also contains a parallel task's in-progress edits
  (`src/limnalis/runtime/*`, `src/limnalis/conformance/*`, `tests/test_conformance.py`,
  `tests/test_runtime_runner.py`), per the task briefing. I did not review those. Confirmed by
  listing `git status --porcelain` paths minus that declared set: exactly
  `src/limnalis/normalizer.py` and `tests/test_normalizer_claim_forms.py` remain.
  `git diff --stat -- 'src/limnalis/*.py' ':(exclude)src/limnalis/runtime'
  ':(exclude)src/limnalis/conformance'` shows only `normalizer.py`.
  `git diff --stat -- src/limnalis/models/` is empty (no AST model changes — MODEL-001/002 N/A).
  `git diff --stat -- tests/test_operator_precedence.py tests/test_normalizer.py` is empty (no
  existing test modified; both files are untouched, `test_normalizer_claim_forms.py` is the only
  new/changed test file among T2b's paths).
- Out-of-scope modifications: none.

## Declared-behavior verification (independently reproduced, `PYTHONPATH=src python`)

All three advisories are correctly and thoroughly implemented for their stated purpose:

1. **note/declare through the judged_by-aware pipeline** (`normalizer.py:894-910`,
   `_normalize_claim_expr` — the old `tokens[0] == "note"` / `"declare"` early-exits are gone; ALL
   claim forms now go through `_parse_expr_text`, matching the causal/EMRG treatment T2 already
   applied). Reproduced directly:
   - `note "x" judged_by policy://k` -> `Judged(Note("x"), "policy://k")` (previously
     `NormalizationError: invalid string literal '"x" judged_by policy://k'`).
   - `declare x as y judged_by policy://k` -> `Judged(Declaration(x,y), "policy://k")`, and I
     confirmed `declaredAs == "y"` **exactly**, directly on the raw `model_dump(mode="json")`
     output (not just via a shape helper):
     `{"declaredAs": "y", "node": "DeclarationExpr", "term": {...}, "within": null}` wrapped in
     `{"criterionRef": "policy://k", "expr": {...}, "node": "JudgedExpr"}`.
   - `declare x as y AND b` -> `AND(Declaration(x,y), b)`, `declaredAs == "y"` exactly (same raw-JSON
     check) — no leaked `"AND"` or `"judged_by"` text.
2. **`expr_malformed_operator` warning** (`_warn_boundary_operator_predicates`,
   `normalizer.py:912-957`; `_boundary_operator_token`, `normalizer.py:979-984`). Confirmed: fires
   exactly once per boundary-swallowed word operator (`AND b`, `a AND`, `OR b`, `a NOT`, `a OR`,
   `a IFF`, `a IMPLIES`, and combinations like `(AND b) OR (a AND)` -> 2 warnings, correctly ordered
   left-to-right), with correct `severity="warning"`, `phase="normalize"`, `subject=<claim id>`,
   stable `code="expr_malformed_operator"`. Symbol spellings (`-> b`) still hard-error
   ("missing an operand"), unchanged. Zero behavior change on valid input — see the
   corpus/example run below (0 occurrences across all 21 valid sources).
3. **Whitespace-independent causal/dynamic markers** (`_find_causal_split`/`_match_causal_marker`,
   `normalizer.py:1744-1798`; `_find_dynamic_split`/`_match_dynamic_marker`,
   `normalizer.py:1800-1837`). Confirmed: all four spacings of `x =>[obs] y` /
   `x=>[obs]y` / `x =>[obs]y` / `x=>[obs] y` produce an identical `CausalExpr`;
   `x=>[do:f(z)]y` correctly builds `intervention=PredicateExpr(f,z)`; `a-->|0:b|` ->
   `DynamicExpr(approaches, a, Baseline(b))`; `a->b` still `IMPLIES(a,b)`; `a--->b` still stays an
   opaque `PredicateExpr` (guarded per `normalizer.py:1832-1836`); `well-formed AND x-y` unaffected
   (hyphenated Idents untouched); `v EMRG when m-->|0:base|` (onset clause) also benefits.

**Byte-identity reproduction (independent of the implementer's claim).** I checked out HEAD
(`3692f57`)'s `normalizer.py` via `git show HEAD:src/limnalis/normalizer.py` into an isolated copy
of the `limnalis` package under scratchpad (`head_pkg/`), leaving the working tree untouched, then
ran both normalizer versions (via separate `PYTHONPATH` subprocess invocations of the same
harness) over all 16 vendored corpus case sources (`fixtures/limnalis_fixture_corpus_v0.2.2.yaml`,
ids A1-A14, B1, B2 — extracted via PyYAML, not via the conformance runner, since that module is
mid-edit by the parallel task) and all 5 `examples/*.lmn` files, comparing full
`model_dump(mode="json")` AST + full diagnostics list for each. **All 21 outputs are byte-identical
between HEAD and the working tree.** Zero `expr_malformed_operator` diagnostics appear anywhere in
this set (diagnostic codes seen: `extra_resolution_policy_omitted`, `adequacy_id_synthesized`,
`assessment_id_synthesized`, `evaluator_kind_canonicalized`, `fictional_anchor_subtype_defaulted`,
`resolution_policy_defaulted` — all pre-existing, unrelated to this diff).

## Test audit (`tests/test_normalizer_claim_forms.py`)

- 56 tests collected (`pytest --collect-only -q`), matching the claimed count exactly (6 classes,
  28 `def test_` functions, expanded via `@pytest.mark.parametrize` to 56).
- `_shape()` (`test_normalizer_claim_forms.py:103-135`) renders the full nested tree recursively
  (not root-only), covering every node kind reachable from these tests.
- Every test that produces a claim also schema-validates the full bundle AST via
  `validate_payload(result.canonical_ast.to_schema_data(), "ast")` inside the shared
  `_normalize_expr` helper (`test_normalizer_claim_forms.py:81-92`) — SCHEMA-001 is exercised on
  every case, including the newly-reachable `Judged(Note(...))` / `Judged(Declaration(...))` shapes.
  Diagnostics are asserted for stable `code`, `severity`, `phase`, `subject`, and message substring
  (`test_normalizer_claim_forms.py:263-274`).
- `TestNewFormsDeterminism` (`test_normalizer_claim_forms.py:461-490`) independently exercises
  NORM-001 for 10 of the new forms via double-run JSON comparison — same technique I used
  independently below.
- EBNF line-number citations in both the diff's docstrings and the test module's docstrings were
  checked against `spec/Limnalis-v0.2.2-reconstructed.md` and are exact: 1013 (`Ident`), 1232-1244
  (`Expr` through `IffOp`), 1246-1247 (`CoreExpr`), 1249-1250 (`CausalExpr`/`CausalOp`), 1258-1263
  (`DeclarationExpr`/`NoteExpr`), 1265-1266 (`DynamicExpr`/`DynamicOp`). No citation drift found.
- No existing test file modified or weakened (confirmed empty diff for
  `tests/test_operator_precedence.py` and `tests/test_normalizer.py`).

## Determinism (NORM-001)

Independently double-ran 5 of the newly-reachable forms (`note "x" judged_by policy://k`,
`declare x as y AND b`, `x=>[obs]y AND z judged_by policy://k`, `AND b`, `a-->|0:b|`) through two
independent parse+normalize invocations each, comparing `sort_keys=True` JSON dumps of AST +
diagnostics: all 5 identical across both runs. **PASS.**

## Suite / conformance run

- `PYTHONPATH=src python -m pytest tests/test_normalizer_claim_forms.py
  tests/test_operator_precedence.py tests/test_normalizer.py -q`: **121 passed**, 0 failed
  (56 + 42 + 23, confirmed per-file via `--collect-only`), exit 0.
- `PYTHONPATH=src python -m limnalis conformance run`: **16 passed, 0 failed, 0 errors out of 16
  cases** (A1-A14, B1, B2 all `PASS`), exit 0.

## Adversarial findings

I ran probes well beyond the task's minimum list; all live via `PYTHONPATH=src python`, harnesses
in scratchpad (`probe.py`, `dump_adversarial.py`, `dump_adversarial2.py`, `dump_corpus.py`).

### Finding 1 — REGRESSION: causal-marker scan is unshielded inside `|0:...|` baseline-reference syntax when the reference is not nested inside a call's parentheses

**Location:** `_scan_top_level_matches` (`normalizer.py:1347-1400`) is the shared shielding state
machine used by `_find_causal_split`/`_match_causal_marker` (`normalizer.py:1744-1798`) and
`_find_dynamic_split`/`_match_dynamic_marker` (`normalizer.py:1800-1837`). Its delimiter-tracking
chain (`normalizer.py:1377-1390`) has cases for `"`/`'` (quotes), `(`/`)`, `[`/`]`, `{`/`}` — but
**no case for `|`**, the delimiter used by the baseline-reference term syntax
(`_parse_arg_text`'s `|0:...|` handling, `normalizer.py:1467-1478`, which imposes no character
restriction on the reference id beyond "non-empty").

**Repro** (`c1: a --> |0:some=>[obs]weird|;`, a syntactically-permitted claim body — the surface
grammar's `ATOM: /[^{}\s;"']+/`, `grammar/limnalis.lark:35`, freely admits `=`, `>`, `[`, `]`, `|`
in one token; nothing rejects this at the parse stage):

| | HEAD (`3692f57`, pre-T2b) | Working tree (T2b) |
|---|---|---|
| Result | `DynamicExpr(approaches, a, BaselineRefTerm(id="some=>[obs]weird"))` | `CausalExpr(obs, lhs=DynamicExpr(approaches, a, SymbolTerm("\|0:some")), rhs=PredicateExpr("weird\|"))` |
| Diagnostics | none | none |
| Schema-valid? | yes | yes (confirmed via `validate_payload`) |

This is a **confirmed regression, not a pre-existing gap** — I verified it by running the identical
input through both the HEAD-swapped scratch copy and the working tree (same technique as the
byte-identity check above). Pre-T2b, causal-marker detection operated on already word-split tokens
and required an **exact whole-token** match against `_CAUSAL_RE`
(the old `_find_causal_index`: `self._CAUSAL_RE.fullmatch(token)`), so a token like
`|0:some=>[obs]weird|` — which does not *fullmatch* `^=>\[...\]$` because of its `|0:` prefix and
`weird|` suffix — was never mistaken for a marker; the whole pipe-delimited blob passed through
intact to the baseline-ref handler. Post-T2b, `_match_causal_marker` scans for `=>[` as a
**substring** at any top-level position, and because pipes aren't depth-tracked, the scan reaches
inside the `|...|` content and matches there, producing the corrupted split above with zero
diagnostic.

The docstring safety argument for this design (`normalizer.py:1226-1229`, `_parse_core_expr_text`:
*"the scans cannot collide with grammar-valid predicate names: `Ident` ... admits `-` but never `>`
or `=`, so neither marker can occur inside a valid Ident"*; similarly `normalizer.py:1751-1753` and
`normalizer.py:1814-1816`) is true only against the idealized EBNF `Ident` production
(`spec/...reconstructed.md:1013`) and does not address baseline-reference ids, which this
normalizer accepts with **no character restriction** (`normalizer.py:1471`:
`if kind != "0" or not ref_id: raise` — no charset check), nor against the actual surface grammar's
`ATOM` terminal (`grammar/limnalis.lark:35`), which is materially more permissive than the spec's
idealized `Ident` and is what the normalizer's tokens are actually drawn from.

**Scope of reachability** (I checked this precisely, not just the one repro): the corruption
requires the `|0:...|` term to be a **bare** operand reaching `_parse_core_expr_text` directly
(e.g. as the RHS of a top-level `-->`, or as a bare claim expression) — it does **not** reproduce
when the same pipe term is nested inside a predicate call's `(...)` (confirmed:
`matches_baseline(sensor_A, |0:some=>[obs]weird|)` parses identically and correctly under both HEAD
and working tree, because the enclosing parens are tracked and the causal scan for the outer text
never reaches inside them; individual call arguments are parsed via `_parse_arg_text`, which does
not itself invoke the marker scanners for non-call, non-wrapped text). The equivalent probe for the
**dynamic** `-->` marker embedded inside a pipe term (`|0:weird-->name|`) does **not** reproduce
either, because `_find_dynamic_split` takes only the first top-level match and hands everything
after it to `_parse_arg_text` as one opaque blob without re-scanning — so this is specifically a
**causal-marker-vs-pipe-content** interaction, not a general pipe-shielding failure.
`@{...}` frame-pattern content and JSON annotation maps are safe (brace-tracked, and annotations are
parsed via `json.loads` before ever reaching the marker scanners) — confirmed via
`declare x as y within @{system=Test, namespace=hasarrow=>[obs]x, regime=r}` and
`p(x) annotations {"note": "a=>[obs]b"}`, both byte-identical pre/post T2b.

**Practical impact:** this requires deliberately authoring a baseline-reference id containing a
literal `=>[obs]`/`=>[do...]`-shaped substring, which is not a plausible authoring mistake (unlike,
say, a stray boundary `AND`) and does not occur anywhere in the vendored corpus (its one use of
`|0:...|`, case A11's `matches_baseline(sensor_A, |0:b_fixed|)`, is both an ordinary id and inside
call parens — safe either way) or the 5 examples. It is real, reproducible, silent (no diagnostic —
arguably a `NORM-002` "every non-trivial normalization decision must produce a structured
diagnostic" gap in the same code this task otherwise strengthened diagnostic coverage for), and
schema-valid, so nothing downstream would catch it. I flag this as the primary, load-bearing
advisory below rather than a blocking failure, because it sits outside T2b's three declared
behaviors, the corpus/examples are unaffected, and the trigger surface is narrow — but it should be
tracked as a prioritized follow-up, not deferred indefinitely, given how directly it undercuts this
diff's own stated safety rationale for advisory 3.

### Other adversarial probes — all clean (no leaked operator text, no crash, correct shape, matches pre-T2b where applicable)

- `note "a judged_by b"` and `note "a AND b judged_by k"` -> quotes correctly shield both `AND` and
  `judged_by` as pure note text (`("NOTE", "a judged_by b")` / `("NOTE", "a AND b judged_by k")`).
- `declare x as y ∧ b` / `∨ b` / `→ b` / `↔ b`, and `¬declare x as y` — all four Unicode binary
  operators plus the Unicode `¬` prefix compose correctly with `declare`, `declaredAs` staying
  exactly `"y"` in every AND/OR/IMPLIES/IFF case.
- `p("x=>[obs]y")` and `p("a-->b")` — markers inside quoted call-argument strings are preserved as
  literal `StringTerm` content, not split.
- `(a judged_by k1) judged_by k2` -> correctly nests to
  `Judged(Judged(a, k1), k2)`; `(a judged_by k1) AND (b judged_by k2)` -> correctly produces
  `AND(Judged(a,k1), Judged(b,k2))`; `a judged_by k1 judged_by k2` (two top-level occurrences, no
  parens) correctly raises the pre-existing "`at most one 'judged_by'`" error.
- `x=>[do:f(z)]y` -> `CausalExpr(do, x, y, intervention=PredicateExpr(f,z))` with zero whitespace.
- `x=>[obs]y OR a-->b` -> both zero-whitespace marker families compose correctly in the same
  expression: `OR(Causal(obs,x,y), Dynamic(approaches,a,b))`.
- Re-confirmed via the corpus/example dump: `expr_malformed_operator` fires **zero** times across
  all 16 vendored cases and 5 examples.

### Minor observations (pre-existing, unrelated to T2b, verified byte-identical between HEAD and the working tree — not counted against this changeset)

- `judged_by`'s criterion is parsed as a scalar (`_parse_scalar_text`, matching the EBNF's
  `Ref ::= Ident | Uri | String`, `spec/...reconstructed.md:1013`-adjacent — not a recursive
  `Expr`), so unparenthesized text like `p judged_by k AND q` greedily absorbs `"k AND q"` as one
  criterion-ref string rather than erroring or splitting. Confirmed byte-identical under HEAD and
  working tree for both `p judged_by k AND q` and `p judged_by policy://k AND q` — this logic
  (`_parse_expr_text`'s judged_by branch) is untouched by this diff.
- `_find_dynamic_split` (`normalizer.py:1800-1826`) does not reject a second top-level `-->`
  occurrence the way `_find_causal_split` explicitly does (`normalizer.py:1758-1759`,
  `"causal expressions may only contain one causal operator"`); it silently takes the first match.
  This asymmetry pre-dates T2b (the old `_parse_dynamic`'s `tokens.index("-->")` had the same
  property) and is unchanged by this diff.

## Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| NORM-001 (Normalizer Determinism) | PASS | Verified independently (5 forms, double-run, JSON-diffed) plus the test file's own `TestNewFormsDeterminism` (10 forms); Finding 1 is deterministically *wrong*, not non-deterministic. |
| NORM-002 (Diagnostic Coverage) | PARTIAL | The declared scope's malformed-operator warning is correctly and thoroughly delivered (advisory 2). Finding 1 identifies one additional non-trivial, silent normalization decision (severity: high, not critical) newly reachable via the broadened marker scan, that emits no diagnostic. |
| FIXTURE-001 (Fixture Conformance Authority) | PASS | 16/16 vendored cases green (`conformance run`); vendored corpus/schema/spec files untouched; byte-identity independently reproduced against HEAD for all 16 cases. |
| SCHEMA-001 | PASS | Every new test schema-validates its output; corpus/example outputs unchanged; Finding 1's corrupted tree happens to still be schema-valid (schema does not catch this class of semantic corruption — noted for completeness, not a schema gap in scope here). |
| MODEL-001/002 | N/A | No changes to `src/limnalis/models/`. |
| PARSER-001/002/003 | N/A | `grammar/limnalis.lark` / `src/limnalis/parser.py` not touched by this diff (Finding 1 is about how the normalizer's own text-level scan treats already-permissively-tokenized text, not a grammar defect). |

## Verdict (first pass): PASS_WITH_ADVISORIES — superseded, see "Finding 1 Remediation Verification" below

The three declared T2b behaviors are correctly, thoroughly, and deterministically implemented, and
independently reproduced by me end-to-end: note/declare-rooted claims now flow through the same
judged_by-aware pipeline as every other form (fixing a real crash and a real silent
`declaredAs`-corruption case), `expr_malformed_operator` fires precisely on boundary-swallowed word
operators and nowhere else (confirmed zero false positives across the full vendored corpus and
examples), and causal/dynamic markers are correctly recognized independent of surrounding
whitespace for every spacing variant and composition (causal+AND, causal+judged_by, dynamic+EMRG
onset, etc.) I could construct. All 56 new tests pass, cite exact EBNF line numbers, assert full
tree shapes via schema-validated output, and no existing test was touched. The 16/16 vendored
conformance result and all 5 examples are byte-identical to pre-T2b HEAD, which I reproduced
independently rather than trusting the implementer's claim. Scope is clean.

Finding 1 (`|0:...|` baseline-reference content unshielded from the causal-marker scan when not
inside call-argument parens) is a genuine, reproducible **regression** introduced by the same
character-level scanning that correctly delivers advisory 3's zero-whitespace requirement, and it
directly undercuts that fix's own documented safety rationale. It does not touch the corpus, the
examples, or any of T2b's three declared behaviors, and its trigger requires an implausible
authored id — so it does not block acceptance — but it should be logged as a prioritized follow-up
(same treatment this task itself received for the prior review's advisories), not left as an
open-ended "awareness only" item.

## Advisories (from first pass; item 1 addressed by the remediation below)

1. **(Elevated — confirmed regression, recommend prioritizing over a purely cosmetic backlog item.)**
   Shield `|...|` baseline-reference content from the top-level causal/dynamic marker scan (or
   otherwise prevent `_match_causal_marker`/`_match_dynamic_marker` from firing on text that will
   ultimately be consumed as a single baseline-reference term), so a causal-marker-shaped substring
   inside a bare `|0:...|` term cannot silently corrupt the parse the way `a --> |0:some=>[obs]weird|`
   does today. See Finding 1 above for exact locations (`normalizer.py:1347-1400`,
   `normalizer.py:1744-1798`, `normalizer.py:1800-1837`) and repro.
2. The `judged_by`-criterion-swallows-trailing-text behavior and the dynamic-marker
   single-match-without-rejection asymmetry (see "Minor observations") are both pre-existing and
   unaffected by this diff; flagged for awareness only, not as follow-up work for this track.

## Rollback Recommendation (first pass): NO

No regression was introduced in the declared scope, the corpus, or the examples; all required gates
(determinism, targeted suite, 16/16 conformance, scope cleanliness, citation accuracy) pass, and
Finding 1's trigger surface is narrow and outside the corpus/examples/declared-behavior set. Rolling
back would discard a correct, well-tested fix for two real, previously-crashing/corrupting defects
to guard against one narrow, newly-surfaced, non-corpus-reachable edge case that is better handled
as a scoped follow-up.

---

## Finding 1 Remediation Verification

**Implementer's reported change:** `_scan_top_level_matches` (`normalizer.py:1347-1400+`) gained a
boolean `pipe_span` state that OPENS only at a `|` immediately followed by `0:`, `inf:`, or `∞:`
(the reference sigils per EBNF A.9 lines 1279-1280) and CLOSES at the next `|`; span content is
fully opaque to every matcher (causal, dynamic, and — because the word-operator splitter
(`_split_logical_level`/`_match_logical_operator`) shares this same scanning primitive — the
AND/OR/IMPLIES/IFF splitter too). Docstrings in `_parse_core_expr_text`, `_find_causal_split`, and
`_find_dynamic_split` were corrected to describe the new shielding. `tests/test_normalizer_claim_forms.py`
grew from 56 to 66 tests: a new `TestReferenceSpanShielding` class (7 tests, one parametrized over
`["inf", "∞"]` for 8 collected cases) plus 2 new parametrizations added to the existing
`TestNewFormsDeterminism`.

I re-verified this independently rather than trusting the report, using the same techniques as the
original review, and confirmed the working tree's `normalizer.py`/`tests/test_normalizer_claim_forms.py`
remain the only uncommitted application files (commit `a393de4`, the parallel T3/T4 track, is
confirmed via `git show --stat a393de4 --name-only` to touch neither file — my diff/comparison
commands stayed scoped to these two paths throughout).

### 1. Exact Finding 1 repro

`a --> |0:some=>[obs]weird|` under the current working tree now produces
`DynamicExpr(approaches, SymbolTerm("a"), BaselineRefTerm(id="some=>[obs]weird"))`, with **zero**
diagnostics — byte-for-byte identical to the pre-T2b HEAD (`3692f57`) result I captured in the
original Finding 1 table. **Closed.**

### 2. Adversarial probes of the shielding rule (own harness, `PYTHONPATH=src python`)

| Probe | Input | Result |
|---|---|---|
| Stray `|`, not a reference sigil | `a \| b` | Stays opaque `PredicateExpr("a \| b")`; span never opens (lookahead after `\|` doesn't match `0:`/`inf:`/`∞:`); no swallowing, no warning. |
| Boundary token `\|\|` | `a \|\| b`, bare `\|\|` | Neither `\|` opens a span (second `\|` is not itself `0:`/`inf:`/`∞:`); both stay literal, opaque predicate names, no crash. |
| Unclosed reference | `a --> \|0:oops` (no closing `\|`) | No hang (scan terminates normally at end-of-text since `index` always advances). Degrades gracefully to `DynamicExpr(approaches, a, SymbolTerm("\|0:oops"))` — the unterminated span fails `_parse_arg_text`'s `text.endswith("\|")` check and falls through to a plain symbol, preserving the raw text rather than crashing or silently misparsing into an operator split. |
| `x AND \|0:a AND b\|` | outer/inner AND | `AND(x, PredicateExpr("\|0:a AND b\|"))` — outer `AND` splits (2 args), the embedded `AND` inside the span is never seen by the word-operator scanner (span content is opaque to it too, since it shares `_scan_top_level_matches`). No `expr_malformed_operator` false positive (the span content isn't a boundary token on the final predicate name). |
| `\|∞:...\|` variant | `a --> \|∞:some=>[obs]weird\|` and `\|inf:...\|` | Both raise `NormalizationError: invalid baseline reference '\|...\|'` — **byte-identical to pre-T2b HEAD** (verified directly against the `head_pkg` scratch copy with a plain id, `\|inf:plain\|`/`\|∞:plain\|`: same error both before and after this diff). `UnboundRef` (`kind` other than `"0"`) was never implemented in `_parse_arg_text`'s semantic layer (`normalizer.py:1471`, unchanged by either T2b diff) — the shielding logic is correctly forward-compatible with all 3 EBNF sigils (so a marker-shaped substring inside an `inf:`/`∞:` span can't silently bypass this pre-existing, clear error via a corrupted `CausalExpr` split instead), but doesn't (and isn't expected to) newly implement `UnboundRef` semantics. Out of scope for T2b; unaffected. |

Additional probes beyond the coordinator's list, all clean:
- `p("\|0:not a real ref=>[obs]x")` — pipe-sigil-shaped text inside an actual quoted string stays a
  pure `StringTerm`; quote-tracking still takes priority over pipe-span detection, as designed.
- `p(\|0:a\|) AND \|0:b=>[obs]c\|` — a shielded span inside call parens and a second bare shielded
  span in the same expression both resolve correctly and independently:
  `AND(p(BaselineRefTerm(a)), PredicateExpr("\|0:b=>[obs]c\|"))`.
  `p journey judged_by \|0:notarealcriterion\|` — `judged_by`'s criterion is parsed as a scalar and
  was never routed through the marker scanners in the first place, so it is unaffected either way.
- `AND \|0:x\|` / `\|0:x\| AND` — the `expr_malformed_operator` boundary check (advisory 2) still
  fires correctly on the final predicate name in both cases; the pipe-shielding change only affects
  the internal *scanning/splitting* phase, not the post-hoc boundary-token string check, so advisory
  2 and Finding-1's remediation compose correctly with no interference in either direction.
- Own double-run determinism check on 4 of the above forms (`a --> \|0:some=>[obs]weird\|`,
  `x AND \|0:a AND b\|`, `a --> \|0:oops`, `p(\|0:a\|) AND \|0:b=>[obs]c\|`): all identical
  across two independent parse+normalize runs. **PASS.**

**Bonus finding (strict improvement, not a new risk):** `\|0:a AND b\|` and `x AND \|0:a AND b\|`
were **already broken** under pre-T2b HEAD before this remediation — I confirmed via the `head_pkg`
scratch copy that HEAD's word-operator splitter (which has always shared the same underlying
scanning primitive) also lacked pipe-tracking and incorrectly split *inside* the span (e.g.
`\|0:a AND b\|` alone produced a spurious 2-arg `AND(PredicateExpr("\|0:a"), PredicateExpr("b\|"))`
under HEAD). Because the remediation added pipe-span tracking to the one shared low-level primitive
(`_scan_top_level_matches`) rather than special-casing it only inside the causal/dynamic finders,
this pre-existing, older defect is fixed as a side effect — a strict improvement over HEAD, not a
divergence to be concerned about; it does not touch the corpus or examples (confirmed below) and is
explicitly covered by `TestReferenceSpanShielding.test_word_operator_inside_baseline_ref_does_not_split`
(`tests/test_normalizer_claim_forms.py:507-517`), whose docstring correctly documents it as
"harden[ing] beyond pre-T2b HEAD."

### 3. Byte-identity re-confirmation (16 corpus + 5 examples)

Repeated the isolated-copy technique from the original review — rebuilt a fresh `head_pkg` scratch
copy from `git show 3692f57:src/limnalis/normalizer.py` (confirmed identical to the original
review's copy via `diff`), ran both normalizer versions over all 16 vendored corpus case sources and
all 5 `examples/*.lmn` files, and compared full `model_dump(mode="json")` AST + diagnostics for each.
**All 21 outputs remain byte-identical between pre-T2b HEAD and the current working tree** (0
mismatches; `diff -q` on the two JSON dumps reports no differences). **Confirmed, unchanged from the
first-pass result.**

### 4. Suite / conformance run

- `PYTHONPATH=src python -m pytest tests/test_normalizer_claim_forms.py
  tests/test_operator_precedence.py tests/test_normalizer.py`: **131 passed**, 0 failed
  (66 + 42 + 23, confirmed per-file via `--collect-only`), exit 0. Matches the expected count
  exactly.
- `PYTHONPATH=src python -m limnalis conformance run`: **16 passed, 0 failed, 0 errors out of 16
  cases**, exit 0.

### 5. Scope re-confirmation

`git status --porcelain`: `M src/limnalis/normalizer.py`, `?? tests/test_normalizer_claim_forms.py`,
plus this review file itself (`?? .armature/reviews/m7-t2b-claim-forms.md`) — no other uncommitted
application files. `git show --stat a393de4 --name-only` (the committed T3/T4 changeset) touches
`src/limnalis/{conformance/runner.py, runtime/builtins.py, runtime/models.py, runtime/runner.py}`,
`tests/{test_conformance.py, test_runtime_runner.py}`, and governance docs — **not**
`normalizer.py` or `tests/test_normalizer_claim_forms.py`, confirming the diff I reviewed here is
exactly and only the Finding-1 remediation on top of the changeset from the first pass.

### Updated Invariant Compliance

| Invariant | Status | Notes |
|---|---|---|
| NORM-001 (Normalizer Determinism) | PASS | Unchanged; re-verified on 4 additional pipe-shielding-relevant forms. |
| NORM-002 (Diagnostic Coverage) | PASS | Upgraded from PARTIAL: Finding 1 was the specific silent, undiagnosed normalization decision cited here; it is now shielded (the marker scan never fires inside a reference span, so there is no longer a silent decision to diagnose at this site). |
| FIXTURE-001 (Fixture Conformance Authority) | PASS | Unchanged; 16/16 green, byte-identity re-confirmed. |
| SCHEMA-001 | PASS | Unchanged; all outputs, including the new `TestReferenceSpanShielding` cases, validate. |
| MODEL-001/002 | N/A | Still no changes to `src/limnalis/models/`. |
| PARSER-001/002/003 | N/A | `grammar/limnalis.lark`/`src/limnalis/parser.py` still untouched. |

### Result: Finding 1 is CLOSED. No new issues found.

Every element of the coordinator's verification list passed on independent reproduction: the exact
repro matches pre-T2b HEAD; all six adversarial shielding probes (non-sigil stray `|`, `||`,
unclosed reference, outer/inner AND, `inf:`/`∞:` variants) behave correctly and degrade gracefully
with no hangs, no crashes, and no silent mis-splits; the 16-corpus+5-example byte-identity claim
re-confirms exactly as before; the targeted suite is 131/131 and conformance is 16/16. The
remediation is narrowly scoped to the one shared shielding primitive, correctly documented, and — as
a side effect of being applied at the right layer — also closes a second, older latent defect
(word-operator splitting inside reference spans) that predates T2b entirely, without touching the
corpus, the examples, or any previously-passing behavior.

## FINAL VERDICT: PASS

All three of T2b's declared advisories are correctly, deterministically, and scope-cleanly
implemented and independently verified end-to-end. The one substantive finding from the first-pass
review (Finding 1: causal-marker scan unshielded inside bare `|0:...|` reference spans) has been
remediated with a narrowly-scoped, well-documented, thoroughly-tested fix that I independently
reproduced and adversarially probed beyond the coordinator's minimum list, finding no regressions
and no new gaps — and which, as a byproduct of fixing the shielding at the correct shared layer,
also closes a related pre-existing defect in word-operator splitting. Byte-identity against pre-T2b
HEAD holds for all 16 vendored corpus cases and all 5 examples. 131/131 targeted tests pass, 16/16
conformance passes, determinism holds. No required changes remain.

## Rollback Recommendation: NO

No regression exists anywhere in the reviewed scope, the corpus, or the examples. The changeset
(T2b base + Finding-1 remediation) is ready to commit as-is.
