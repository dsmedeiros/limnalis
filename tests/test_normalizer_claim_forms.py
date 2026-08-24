"""Claim-expression pipeline tests for note/declare routing, malformed-operator
warnings, and whitespace-independent causal/dynamic markers.

Milestone 7 T2b (PRD: ``.taskmaster/docs/milestone-7-remediation-track-c.md``),
implementing the three advisories of the T2 review verdict
``.armature/reviews/m7-t2-normalizer-precedence.md``:

1. ``note``/``declare``-rooted top-level claims must flow through the same
   judged_by-aware pipeline as every other CoreExpr. Authority:
   ``spec/Limnalis-v0.2.2-reconstructed.md`` A.9 —
   ``Expr ::= JudgedExpr`` (line 1232),
   ``JudgedExpr ::= LogicalExpr [ "judged_by" Ref ]`` (line 1233),
   ``CoreExpr ::= ... | DeclarationExpr | NoteExpr | ...`` (lines 1246-1247),
   ``DeclarationExpr ::= "declare" Term "as" Symbol [ "within" ... ]``
   (lines 1258-1261), ``NoteExpr ::= "note" String`` (line 1263). So
   ``note "x" judged_by k`` is Judged(Note("x"), k) — previously a crash —
   and ``declare x as y judged_by k`` is Judged(Declaration(x, y), k) —
   previously the trailing text silently corrupted ``declaredAs``.

2. A word operator at the very start or end of a (sub)expression (``AND b``,
   ``a AND``) is not derivable from the EBNF (AndExpr ::= UnaryExpr { AndOp
   UnaryExpr }, line 1238, and likewise lines 1235-1237, 1239-1240): the
   permissive pipeline keeps the text as an atomic predicate name and now
   emits an ``expr_malformed_operator`` normalize-phase warning (NORM-002).

3. The causal ``=>[obs]``/``=>[do]`` (CausalOp, line 1250) and dynamic
   ``-->`` (DynamicOp, line 1266) marker scans are whitespace-independent:
   ``x=>[obs]y`` and ``a-->|0:b|`` parse like their spaced spellings. This is
   unambiguous because ``Ident ::= Letter { Letter | Digit | "_" | "-" }``
   (line 1013) admits ``-`` but never ``>`` or ``=``, so no grammar-valid
   predicate name can contain either marker, and the ImplOp ``->``
   (line 1243) guards reject adjacency to ``-``/``<``/``>``.

Follow-up remediation (T2b review Finding 1,
``.armature/reviews/m7-t2b-claim-forms.md``): baseline/unbound reference
spans — ``BaselineRef ::= "|0:" Ident "|"``, ``UnboundRef ::= "|∞:" Ident
"|" | "|inf:" Ident "|"`` (lines 1279-1280) — carry ids with NO enforced
charset, so the shared top-level scanner shields ``|...|`` spans (opened only
at a ``|`` immediately followed by ``0:``/``inf:``/``∞:``, closed at the next
``|``) from the marker scans AND the word-operator splits:
``a --> |0:some=>[obs]weird|`` keeps its reference id intact (the Finding 1
regression), and ``|0:a AND b|`` never splits.
"""

from __future__ import annotations

import json

import pytest

from limnalis.normalizer import NormalizationError, Normalizer
from limnalis.parser import LimnalisParser
from limnalis.schema import validate_payload

MALFORMED_OPERATOR_CODE = "expr_malformed_operator"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bundle(expr: str) -> str:
    """Build a minimal bundle whose single local claim uses `expr`."""
    return f"""
    bundle claim_forms_test {{
      frame {{
        system Test;
        namespace ClaimForms;
        scale unit;
        task check;
        regime nominal;
      }}

      evaluator ev0 {{
        kind model;
        binding test://eval/atoms_v1;
      }}

      resolution_policy rp0 {{
        kind single;
        members [ev0];
      }}

      local {{
        c1: {expr};
      }}
    }}
    """


def _normalize_expr(expr: str):
    """Normalize a one-claim bundle; return (claim, diagnostics).

    Also schema-validates the canonical AST (SCHEMA-001), pinning that the
    newly reachable shapes — e.g. JudgedExpr wrapping NoteExpr /
    DeclarationExpr — validate against the vendored schema.
    """
    tree = LimnalisParser().parse_text(_make_bundle(expr))
    result = Normalizer().normalize(tree)
    assert result.canonical_ast is not None
    validate_payload(result.canonical_ast.to_schema_data(), "ast")
    return result.canonical_ast.claimBlocks[0].claims[0], result.diagnostics


def _expr(expr: str):
    return _normalize_expr(expr)[0].expr


def _malformed_warnings(diagnostics):
    return [diag for diag in diagnostics if diag["code"] == MALFORMED_OPERATOR_CODE]


def _shape(node):
    """Render an expression node as a nested tuple pinning the FULL tree."""
    kind = node.node
    if kind == "LogicalExpr":
        return (node.op.upper(), *[_shape(arg) for arg in node.args])
    if kind == "PredicateExpr":
        if not node.args:
            return node.name
        return ("PRED", node.name, *[_shape(arg) for arg in node.args])
    if kind == "JudgedExpr":
        return ("JUDGED", _shape(node.expr), node.criterionRef)
    if kind == "CausalExpr":
        intervention = node.intervention
        if intervention is not None and not isinstance(intervention, str):
            intervention = _shape(intervention)
        return ("CAUSAL", node.mode, _shape(node.lhs), _shape(node.rhs), intervention)
    if kind == "DynamicExpr":
        target = _shape(node.target) if node.target is not None else None
        return ("DYNAMIC", node.op, _shape(node.subject), target)
    if kind == "EmergenceExpr":
        return ("EMRG", _shape(node.property), _shape(node.onset))
    if kind == "NoteExpr":
        return ("NOTE", node.text)
    if kind == "DeclarationExpr":
        within = None if node.within is None else _shape(node.within)
        return ("DECLARE", _shape(node.term), node.declaredAs, within)
    if kind == "FramePattern":
        return ("FRAME_PATTERN",)
    if kind == "SymbolTerm":
        return node.value
    if kind == "BaselineRefTerm":
        return ("BASELINE", node.id)
    raise AssertionError(f"unexpected node kind {kind!r}")


# ---------------------------------------------------------------------------
# Advisory 1: note/declare flow through the judged_by-aware pipeline
# (EBNF lines 1232-1233, 1246-1247, 1258-1263)
# ---------------------------------------------------------------------------


class TestNoteThroughPipeline:
    """NoteExpr is a CoreExpr (line 1247), so it is a LogicalExpr leaf and a
    valid JudgedExpr inner: ``note "x" judged_by k`` derives
    Judged(Note("x"), k). The former top-level early-exit fed the whole
    remainder — judged_by clause included — to the string-literal parser and
    crashed (review advisory 1)."""

    def test_note_judged_by_wraps_note(self):
        """note "x" judged_by policy://k -> Judged(Note("x"), policy://k);
        previously NormalizationError: invalid string literal."""
        claim, _ = _normalize_expr('note "x" judged_by policy://k')
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == ("JUDGED", ("NOTE", "x"), "policy://k")

    def test_note_conjunction(self):
        """note "x" AND note "y" -> AND(Note("x"), Note("y")): NoteExprs are
        AndExpr operands via UnaryExpr ::= [NotOp] CoreExpr (lines 1238-1239);
        previously the same string-literal crash."""
        assert _shape(_expr('note "x" AND note "y"')) == (
            "AND",
            ("NOTE", "x"),
            ("NOTE", "y"),
        )

    def test_plain_note_regression(self):
        """note "..." (the vendored-corpus B1 shape) is unchanged."""
        claim, _ = _normalize_expr(
            'note "N-1 is acceptable for dispatch prediction but weak as a '
            'restoration explanation model."'
        )
        assert claim.kind == "note"
        assert claim.expr.node == "NoteExpr"
        assert claim.expr.text.startswith("N-1 is acceptable")

    def test_note_string_shields_operator_and_judged_text(self):
        """Operator words and judged_by INSIDE the note string are content,
        not structure (String, line 1015; quotes shield the top-level scans)."""
        assert _shape(_expr('note "a AND b judged_by k"')) == (
            "NOTE",
            "a AND b judged_by k",
        )


class TestDeclareThroughPipeline:
    """DeclarationExpr is a CoreExpr (line 1246) whose declaredAs is a single
    Symbol (line 1258): trailing judged_by/operator text belongs to the
    enclosing JudgedExpr/LogicalExpr, never to ``declaredAs`` (review
    advisory 1 — the former early-exit silently absorbed it)."""

    def test_declare_judged_by_wraps_declaration(self):
        """declare x as y judged_by policy://k -> Judged(Declaration(x, y), k)
        with declaredAs EXACTLY "y"; previously declaredAs was the corrupted
        string "y judged_by policy://k"."""
        claim, _ = _normalize_expr("declare x as y judged_by policy://k")
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == ("JUDGED", ("DECLARE", "x", "y", None), "policy://k")
        assert claim.expr.expr.declaredAs == "y"

    def test_declare_as_and_operand(self):
        """declare x as y AND b -> AND(Declaration(x, y), b): DeclarationExpr
        is an AndExpr operand (lines 1238-1239, 1246); previously declaredAs
        was the corrupted string "y AND b"."""
        claim, _ = _normalize_expr("declare x as y AND b")
        assert claim.kind == "logical"
        assert _shape(claim.expr) == ("AND", ("DECLARE", "x", "y", None), "b")
        assert claim.expr.args[0].declaredAs == "y"

    def test_declare_within_frame_pattern_regression(self):
        """The vendored-corpus declare-within shape (A1/B1/B2) is unchanged."""
        claim, _ = _normalize_expr(
            "declare Nminus1 as idealization within "
            "@{system=PowerGrid, namespace=ACLoadFlow, regime=contingency}"
        )
        assert claim.kind == "declaration"
        assert _shape(claim.expr) == (
            "DECLARE",
            "Nminus1",
            "idealization",
            ("FRAME_PATTERN",),
        )

    def test_declare_within_then_judged_by(self):
        """declare x as y within @{...} judged_by k -> the judged_by clause
        wraps the whole declaration, within clause included (lines 1232-1233,
        1258-1259)."""
        claim, _ = _normalize_expr(
            "declare x as y within @{system=Test, namespace=N, regime=r} judged_by policy://k"
        )
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == (
            "JUDGED",
            ("DECLARE", "x", "y", ("FRAME_PATTERN",)),
            "policy://k",
        )

    def test_declared_as_never_retains_clause_text(self):
        """declaredAs integrity: no judged_by/operator text may leak into the
        Symbol field (line 1258) for any of the advisory-1 repro inputs."""
        judged = _expr("declare x as y judged_by policy://k")
        conjoined = _expr("declare x as y AND b")
        for declared_as in (judged.expr.declaredAs, conjoined.args[0].declaredAs):
            assert declared_as == "y"
            assert "judged_by" not in declared_as
            assert "AND" not in declared_as


# ---------------------------------------------------------------------------
# Advisory 2: boundary-malformed word operators warn (permissively)
# (EBNF lines 1235-1240)
# ---------------------------------------------------------------------------


class TestMalformedBoundaryOperatorWarning:
    """A word operator at the very start or end of a (sub)expression has a
    missing operand — underivable from lines 1235-1240 — and survives as an
    atomic predicate name (permissive-parser philosophy, unchanged). The
    normalizer now flags it with an ``expr_malformed_operator`` warning
    (NORM-002; review advisory 2)."""

    def test_leading_word_operator_warns(self):
        """AND b -> PredicateExpr("AND b") + exactly one warning diagnostic
        with the stable code, normalize phase, and the claim id as subject."""
        claim, diagnostics = _normalize_expr("AND b")
        assert claim.kind == "atomic"
        assert _shape(claim.expr) == "AND b"
        warnings = _malformed_warnings(diagnostics)
        assert len(warnings) == 1
        assert warnings[0]["severity"] == "warning"
        assert warnings[0]["phase"] == "normalize"
        assert warnings[0]["subject"] == "c1"
        assert "'AND'" in warnings[0]["message"]

    def test_trailing_word_operator_warns(self):
        """a AND -> PredicateExpr("a AND") + warning (same silent-swallow
        boundary case, trailing side)."""
        claim, diagnostics = _normalize_expr("a AND")
        assert _shape(claim.expr) == "a AND"
        assert len(_malformed_warnings(diagnostics)) == 1

    @pytest.mark.parametrize(
        "expr_text",
        ["OR b", "IFF b", "IMPLIES b", "a OR", "a IFF", "a IMPLIES", "a NOT"],
    )
    def test_every_word_operator_boundary_warns(self, expr_text: str):
        """Each word spelling (NOT/AND/OR/IMPLIES/IFF, lines 1240-1244) is
        flagged at either boundary. (A leading NOT with an operand is the
        valid prefix NotOp, line 1239, so only trailing NOT is malformed.)"""
        claim, diagnostics = _normalize_expr(expr_text)
        assert claim.expr.node == "PredicateExpr"
        assert claim.expr.name == expr_text
        assert len(_malformed_warnings(diagnostics)) == 1

    def test_nested_boundary_operator_warns(self):
        """(AND b) OR c -> OR(PredicateExpr("AND b"), c) + warning: the walk
        covers sub-expressions, not just the claim root."""
        claim, diagnostics = _normalize_expr("(AND b) OR c")
        assert _shape(claim.expr) == ("OR", "AND b", "c")
        assert len(_malformed_warnings(diagnostics)) == 1

    @pytest.mark.parametrize(
        "expr_text",
        [
            "(a AND b OR c)",
            "a AND b OR c",
            "(TARIFF AND BRAND)",
            "(NOT a AND b)",
            'note "x" judged_by policy://k',
            "declare x as y AND b",
            "p(x) =>[obs] q(y) judged_by policy://k",
            "a --> |0:b|",
            "x=>[obs]y AND z",
            "v EMRG when m --> |0:base|",
        ],
    )
    def test_valid_inputs_emit_no_malformed_warning(self, expr_text: str):
        """No grammar-derivable input triggers the warning: zero behavior and
        zero diagnostic change for valid input (task requirement)."""
        _claim, diagnostics = _normalize_expr(expr_text)
        assert _malformed_warnings(diagnostics) == []

    def test_symbol_operator_at_boundary_still_errors(self):
        """Symbol spellings never swallow silently: `-> b` already raises a
        missing-operand error (which is why the warning covers only the
        whitespace-delimited word forms)."""
        with pytest.raises(NormalizationError, match="missing an operand"):
            _normalize_expr("-> b")


# ---------------------------------------------------------------------------
# Advisory 3: whitespace-independent causal/dynamic markers
# (EBNF lines 1249-1250, 1265-1266; Ident line 1013)
# ---------------------------------------------------------------------------


class TestWhitespaceIndependentCausalMarker:
    """CausalOp ``=>[obs]``/``=>[do]`` (line 1250) is recognized at the top
    level of the text regardless of surrounding whitespace; `Ident`
    (line 1013) admits neither `=` nor `>`, so the scan cannot split a valid
    predicate name (review advisory 3)."""

    @pytest.mark.parametrize(
        "expr_text",
        ["x =>[obs] y", "x=>[obs]y", "x =>[obs]y", "x=>[obs] y"],
    )
    def test_causal_marker_whitespace_variants(self, expr_text: str):
        """All spacings of x =>[obs] y produce the identical CausalExpr;
        the zero-whitespace form previously collapsed to
        PredicateExpr("x=>[obs]y")."""
        claim, _ = _normalize_expr(expr_text)
        assert claim.kind == "causal"
        assert _shape(claim.expr) == ("CAUSAL", "obs", "x", "y", None)

    def test_zero_whitespace_do_marker_with_intervention(self):
        """x=>[do:f(z)]y -> CausalExpr(do, x, y, intervention=f(z))
        (InterventionClause, line 1251)."""
        assert _shape(_expr("x=>[do:f(z)]y")) == (
            "CAUSAL",
            "do",
            "x",
            "y",
            ("PRED", "f", "z"),
        )

    def test_zero_whitespace_causal_judged_by(self):
        """x=>[obs]y judged_by policy://k -> Judged(Causal(x, y), k):
        JudgedExpr stays outermost (lines 1232-1233) for the zero-whitespace
        spelling too."""
        claim, _ = _normalize_expr("x=>[obs]y judged_by policy://k")
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == (
            "JUDGED",
            ("CAUSAL", "obs", "x", "y", None),
            "policy://k",
        )

    def test_zero_whitespace_causal_composes_with_logical_layer(self):
        """x=>[obs]y AND z -> AND(Causal(x, y), z): CausalExpr is a CoreExpr
        (line 1246) below the logical levels, spacing notwithstanding."""
        assert _shape(_expr("x=>[obs]y AND z")) == (
            "AND",
            ("CAUSAL", "obs", "x", "y", None),
            "z",
        )

    @pytest.mark.parametrize(
        "expr_text",
        ["a =>[obs] b =>[do] c", "a=>[obs]b=>[do]c"],
    )
    def test_multiple_causal_markers_rejected(self, expr_text: str):
        """CausalExpr ::= SimpleExpr CausalOp SimpleExpr (line 1249) admits
        exactly one CausalOp per level; the pre-existing spaced-form error is
        preserved and now applies to the zero-whitespace spelling too."""
        with pytest.raises(NormalizationError, match="one causal operator"):
            _normalize_expr(expr_text)


class TestWhitespaceIndependentDynamicMarker:
    """DynamicOp ``-->`` (line 1266) is recognized whitespace-independently,
    guarded against ImplOp ``->`` (line 1243) and hyphen-bearing Idents
    (line 1013), which can never contain ``-->`` (review advisory 3)."""

    def test_zero_whitespace_dynamic_baseline_target(self):
        """a-->|0:b| -> DynamicExpr(approaches, a, |0:b|); previously
        collapsed to PredicateExpr("a-->|0:b|")."""
        claim, _ = _normalize_expr("a-->|0:b|")
        assert claim.kind == "dynamic"
        assert _shape(claim.expr) == ("DYNAMIC", "approaches", "a", ("BASELINE", "b"))

    def test_zero_whitespace_dynamic_symbol_target(self):
        """a-->b -> DynamicExpr(approaches, a, b) (Term target, line 1265)."""
        assert _shape(_expr("a-->b")) == ("DYNAMIC", "approaches", "a", "b")

    def test_spaced_dynamic_regression(self):
        """a --> |0:b| (the vendored-corpus B1 spelling) is unchanged."""
        claim, _ = _normalize_expr("a --> |0:b|")
        assert claim.kind == "dynamic"
        assert _shape(claim.expr) == ("DYNAMIC", "approaches", "a", ("BASELINE", "b"))

    def test_emergence_onset_accepts_zero_whitespace_marker(self):
        """v EMRG when m-->|0:base| -> the onset clause (line 1253) benefits
        from the same whitespace-independent scan."""
        claim, _ = _normalize_expr("v EMRG when m-->|0:base|")
        assert claim.kind == "emergence"
        assert _shape(claim.expr) == (
            "EMRG",
            "v",
            ("DYNAMIC", "approaches", "m", ("BASELINE", "base")),
        )

    def test_zero_whitespace_implies_is_not_dynamic(self):
        """a->b -> IMPLIES(a, b): the single-dash ImplOp (line 1243) never
        collides with the ``-->`` scan."""
        claim, _ = _normalize_expr("a->b")
        assert claim.kind == "logical"
        assert _shape(claim.expr) == ("IMPLIES", "a", "b")

    def test_hyphenated_predicate_names_unaffected(self):
        """well-formed AND x-y -> AND(well-formed, x-y): Idents may contain
        ``-`` (line 1013) and are never split by the marker scan."""
        assert _shape(_expr("well-formed AND x-y")) == ("AND", "well-formed", "x-y")

    def test_longer_dash_arrow_runs_stay_opaque(self):
        """a--->b -> PredicateExpr("a--->b"): runs longer than the exact
        ``-->`` DynamicOp (line 1266) are not derivable from the EBNF, and the
        scan's adjacency guards (no preceding ``-``/``<``, no following ``>``)
        deliberately leave them as opaque predicate names — the documented
        resolution of the ``->`` / ``-`` ambiguity boundary."""
        claim, _ = _normalize_expr("a--->b")
        assert claim.kind == "atomic"
        assert _shape(claim.expr) == "a--->b"


# ---------------------------------------------------------------------------
# T2b review Finding 1: |...| reference spans shield every top-level scan
# (.armature/reviews/m7-t2b-claim-forms.md; EBNF lines 1279-1280)
# ---------------------------------------------------------------------------


class TestReferenceSpanShielding:
    """Reference-term ids (`BaselineRef ::= "|0:" Ident "|"`, `UnboundRef ::=
    "|∞:" Ident "|" | "|inf:" Ident "|"`, lines 1279-1280) are consumed
    verbatim by the term parser with no charset restriction, so the shared
    top-level scanner must never match markers or word operators inside a
    ``|...|`` span. A span opens only at a ``|`` immediately followed by
    ``0:``/``inf:``/``∞:`` and closes at the next ``|`` (documented in
    `_scan_top_level_matches`), so stray ``|`` characters elsewhere cannot
    swallow the scan. Remediation of the T2b review's Finding 1
    (.armature/reviews/m7-t2b-claim-forms.md)."""

    def test_causal_marker_inside_baseline_ref_does_not_split(self):
        """a --> |0:some=>[obs]weird| -> DynamicExpr(approaches, a,
        BaselineRef("some=>[obs]weird")): the reviewer's exact Finding 1
        repro. The unshielded scan corrupted this into a nonsensical
        CausalExpr with zero diagnostics; the shielded scan restores the
        pre-T2b HEAD parse — reference id intact."""
        claim, diagnostics = _normalize_expr("a --> |0:some=>[obs]weird|")
        assert claim.kind == "dynamic"
        assert _shape(claim.expr) == (
            "DYNAMIC",
            "approaches",
            "a",
            ("BASELINE", "some=>[obs]weird"),
        )
        assert _malformed_warnings(diagnostics) == []

    def test_bare_baseline_ref_with_marker_stays_opaque(self):
        """|0:some=>[obs]weird| as a whole claim stays one opaque
        PredicateExpr (the pre-T2b HEAD behavior): the causal scan must not
        fire inside the span even with no surrounding expression."""
        claim, _ = _normalize_expr("|0:some=>[obs]weird|")
        assert claim.kind == "atomic"
        assert _shape(claim.expr) == "|0:some=>[obs]weird|"

    def test_word_operator_inside_baseline_ref_does_not_split(self):
        """|0:a AND b| never splits on the embedded AND: the word-operator
        split runs on the same `_scan_top_level_matches` state machine, so the
        span shielding covers it too. (This hardens beyond pre-T2b HEAD, whose
        splitter also lacked pipe tracking and split inside the span; required
        by the Finding 1 remediation directive.) No malformed-operator warning
        fires — the AND is span content, not a boundary token."""
        claim, diagnostics = _normalize_expr("|0:a AND b|")
        assert claim.kind == "atomic"
        assert _shape(claim.expr) == "|0:a AND b|"
        assert _malformed_warnings(diagnostics) == []

    def test_word_operator_outside_span_still_splits(self):
        """x AND |0:a AND b| -> AND(x, PredicateExpr("|0:a AND b|")): only the
        AND outside the span is an operator; the span stays one operand."""
        assert _shape(_expr("x AND |0:a AND b|")) == ("AND", "x", "|0:a AND b|")

    def test_unbound_ref_span_shields_word_scan(self):
        """x AND |inf:a IMPLIES b| -> AND(x, PredicateExpr(...)): the
        `inf:` sigil (line 1280) opens a span exactly like `0:`, so the
        embedded IMPLIES is span content, not the expression root."""
        assert _shape(_expr("x AND |inf:a IMPLIES b|")) == (
            "AND",
            "x",
            "|inf:a IMPLIES b|",
        )

    @pytest.mark.parametrize("sigil", ["inf", "∞"])
    def test_unbound_ref_span_shields_causal_scan(self, sigil: str):
        """a --> |inf:some=>[obs]weird| (and the ∞ spelling, line 1280) raises
        the same 'invalid baseline reference' the pre-T2b HEAD raised (unbound
        refs are not yet supported by the term parser): the shielding keeps
        the embedded marker from silently bypassing that error via a
        corrupted CausalExpr split."""
        with pytest.raises(NormalizationError, match="invalid baseline reference"):
            _normalize_expr(f"a --> |{sigil}:some=>[obs]weird|")

    def test_ordinary_baseline_ref_control(self):
        """a --> |0:margin| (the vendored-corpus-style spelling) is unchanged
        by the span shielding — the control case for Finding 1."""
        claim, diagnostics = _normalize_expr("a --> |0:margin|")
        assert claim.kind == "dynamic"
        assert _shape(claim.expr) == ("DYNAMIC", "approaches", "a", ("BASELINE", "margin"))
        assert diagnostics == []


class TestReferenceSpanShieldingAllScanners:
    """`|...|` reference spans are opaque to EVERY top-level scanner, not just
    the operator/marker scan: the argument/list splitter `_split_top_level`,
    the surface-word splitter `_split_words`, and the wrapped-group check
    `_is_wrapped_expression` share the `_pipe_span_opens` rule. The T2b
    remediation shielded only `_scan_top_level_matches`, so span content
    containing `,`, quotes, or parens still corrupted these scanners —
    m7 red-team MEDIUM-3 (.armature/reviews/m7-redteam.md)."""

    def test_comma_inside_baseline_ref_does_not_split_args(self):
        """p(|0:a,b|, c) -> PredicateExpr(p, [BaselineRef("a,b"),
        Symbol("c")]) — the red team's exact repro. The unshielded argument
        splitter produced THREE args with two bogus SymbolTerms ("|0:a" and
        "b|")."""
        claim, diagnostics = _normalize_expr("p(|0:a,b|, c)")
        assert _shape(claim.expr) == ("PRED", "p", ("BASELINE", "a,b"), "c")
        assert _malformed_warnings(diagnostics) == []

    def test_comma_inside_baseline_ref_does_not_split_list_items(self):
        """p([|0:a,b|, c]) -> the list keeps two items: the same
        `_split_top_level` path splits list items, so the span shields there
        too."""
        claim, _ = _normalize_expr("p([|0:a,b|, c])")
        expr = claim.expr
        assert expr.node == "PredicateExpr" and len(expr.args) == 1
        list_term = expr.args[0]
        assert list_term.node == "ListTerm" and len(list_term.items) == 2
        assert list_term.items[0].node == "BaselineRefTerm"
        assert list_term.items[0].id == "a,b"
        assert list_term.items[1].node == "SymbolTerm"
        assert list_term.items[1].value == "c"

    def test_quote_inside_baseline_ref_keeps_wrapped_group(self):
        """(a AND |0:x'y|) -> AND(a, |0:x'y|): the unshielded
        `_is_wrapped_expression` treated the apostrophe as an unterminated
        string quote, rejected the wrapping parens, and collapsed the whole
        text into one atomic predicate name."""
        claim, diagnostics = _normalize_expr("(a AND |0:x'y|)")
        assert _shape(claim.expr) == ("AND", "a", "|0:x'y|")
        assert _malformed_warnings(diagnostics) == []

    def test_paren_inside_baseline_ref_keeps_wrapped_group(self):
        """(a AND |0:x(y|) -> AND(a, |0:x(y|): the span's `(` is content,
        not nesting — the unshielded check saw unbalanced parens and
        collapsed the text into one atomic predicate."""
        claim, _ = _normalize_expr("(a AND |0:x(y|)")
        assert _shape(claim.expr) == ("AND", "a", "|0:x(y|")

    def test_quote_inside_baseline_ref_keeps_declaration_words(self):
        """(declare |0:x'y| as fiction) -> a DeclarationExpr with the span as
        its term: the unshielded `_split_words` swallowed everything after
        the apostrophe into one pseudo-word, losing the 'as' clause and
        raising NormalizationError. (The unparenthesized spelling is rejected
        earlier by the Lark surface grammar's charset, so the parenthesized
        form is the normalizer-level repro.)"""
        claim, _ = _normalize_expr("(declare |0:x'y| as fiction)")
        assert claim.kind == "declaration"
        assert _shape(claim.expr) == ("DECLARE", ("BASELINE", "x'y"), "fiction", None)

    def test_plain_span_argument_control(self):
        """p(|0:ab|, c) — no delimiter-shaped span content — is unchanged by
        the extended shielding (the control case)."""
        claim, _ = _normalize_expr("p(|0:ab|, c)")
        assert _shape(claim.expr) == ("PRED", "p", ("BASELINE", "ab"), "c")

    def test_shielded_scanner_forms_are_deterministic(self):
        """NORM-001: two independent parse+normalize runs agree on the newly
        shielded forms."""
        for expr_text in (
            "p(|0:a,b|, c)",
            "(a AND |0:x'y|)",
            "(a AND |0:x(y|)",
            "(declare |0:x'y| as fiction)",
        ):
            claim_a, diags_a = _normalize_expr(expr_text)
            claim_b, diags_b = _normalize_expr(expr_text)
            assert claim_a.model_dump() == claim_b.model_dump()
            assert diags_a == diags_b


# ---------------------------------------------------------------------------
# NORM-001: determinism of every newly reachable form
# ---------------------------------------------------------------------------


class TestNewFormsDeterminism:
    """Two independent parse+normalize runs must agree byte-for-byte on AST
    and diagnostics for the forms this task made reachable (NORM-001)."""

    @pytest.mark.parametrize(
        "expr_text",
        [
            'note "x" judged_by policy://k',
            'note "x" AND note "y"',
            "declare x as y judged_by policy://k",
            "declare x as y AND b",
            "AND b",
            "a AND",
            "x=>[obs]y",
            "x=>[do:f(z)]y judged_by policy://k",
            "a-->|0:b|",
            "v EMRG when m-->|0:base|",
            "a --> |0:some=>[obs]weird|",
            "|0:a AND b|",
        ],
    )
    def test_double_run_identical(self, expr_text: str):
        def run():
            tree = LimnalisParser().parse_text(_make_bundle(expr_text))
            result = Normalizer().normalize(tree)
            assert result.canonical_ast is not None
            return (
                json.dumps(result.canonical_ast.model_dump(mode="json"), sort_keys=True),
                json.dumps(result.diagnostics, sort_keys=True),
            )

        assert run() == run()
