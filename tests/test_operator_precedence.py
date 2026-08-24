"""Operator precedence tests for the normalizer, per the recovered EBNF.

Authority: ``spec/Limnalis-v0.2.2-reconstructed.md`` A.9 "Expression Grammar"
(lines 1229-1281)::

    Expr        ::= JudgedExpr ;                          (line 1232)
    JudgedExpr  ::= LogicalExpr [ "judged_by" Ref ] ;     (line 1233)
    LogicalExpr ::= IffExpr ;                             (line 1234)
    IffExpr     ::= ImplExpr { IffOp ImplExpr } ;         (line 1235)
    ImplExpr    ::= OrExpr { ImplOp OrExpr } ;            (line 1236)
    OrExpr      ::= AndExpr { OrOp AndExpr } ;            (line 1237)
    AndExpr     ::= UnaryExpr { AndOp UnaryExpr } ;       (line 1238)
    UnaryExpr   ::= [ NotOp ] CoreExpr ;                  (line 1239)
    NotOp ::= "¬" | "NOT" ;  AndOp ::= "∧" | "AND" ;      (lines 1240-1241)
    OrOp  ::= "∨" | "OR" ;   ImplOp ::= "→" | "->" ;      (lines 1242-1243)
    IffOp ::= "↔" | "<=>" ;                               (line 1244)

By grammar nesting, binding tightest -> loosest is NOT > AND > OR > IMPLIES >
IFF, and ``judged_by`` (JudgedExpr) is the outermost construct of all.

The word spellings IMPLIES and IFF are legacy forms retained by the normalizer
for backward compatibility with the vendored corpus era; they are NOT part of
the spec's operator kernel (ImplOp/IffOp are spelled ``->``/``→`` and
``<=>``/``↔``, lines 1243-1244).

History: this file previously asserted the inverted order (AND at the root,
i.e. loosest) produced by the pre-Milestone-7 first-match-splits list
[AND, IFF, IMPLIES, OR], and asserted that unsplit remainders collapse into
atomic predicates literally named e.g. "b OR c". Both behaviors contradicted
the EBNF, and the file was rewritten to assert the spec-mandated trees per the
Milestone 7 PRD (.taskmaster/docs/milestone-7-remediation-track-c.md, T2).
"""

from __future__ import annotations

from limnalis.normalizer import Normalizer
from limnalis.parser import LimnalisParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_source(source: str):
    tree = LimnalisParser().parse_text(source)
    result = Normalizer().normalize(tree)
    assert result.canonical_ast is not None
    return result


def _make_bundle_with_meta_claim(expr: str) -> str:
    """Build a minimal bundle with a single meta claim using the given expression."""
    return f"""
    bundle precedence_test {{
      frame {{
        system Test;
        namespace Prec;
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
        a: p;
        b: p;
        c: p;
        d: p;
      }}

      meta {{
        target: {expr};
      }}
    }}
    """


def _get_meta_claim(source: str):
    """Normalize source and return the first meta-block claim."""
    result = _normalize_source(source)
    bundle = result.canonical_ast
    meta_blocks = [blk for blk in bundle.claimBlocks if blk.stratum == "meta"]
    assert meta_blocks, "No meta block found"
    return meta_blocks[0].claims[0]


def _meta_expr(expr_text: str):
    """Normalize a bundle whose meta claim is `expr_text` and return its expr node."""
    return _get_meta_claim(_make_bundle_with_meta_claim(expr_text)).expr


def _shape(node):
    """Render an expression node as a nested tuple capturing the FULL tree shape.

    Logical nodes become ("AND"|"OR"|"IMPLIES"|"IFF"|"NOT", *arg_shapes);
    argument-less predicates become their bare name; other node kinds keep a
    tagged tuple. Tests assert against these shapes so every operator, operand,
    and nesting level is pinned — not just the root.
    """
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
        return ("CAUSAL", node.mode, _shape(node.lhs), _shape(node.rhs))
    if kind == "DynamicExpr":
        target = _shape(node.target) if node.target is not None else None
        return ("DYNAMIC", node.op, _shape(node.subject), target)
    if kind == "EmergenceExpr":
        return ("EMRG", _shape(node.property), _shape(node.onset))
    if kind == "SymbolTerm":
        return node.value
    if kind == "BaselineRefTerm":
        return ("BASELINE", node.id)
    raise AssertionError(f"unexpected node kind {kind!r}")


# ---------------------------------------------------------------------------
# Binary operator precedence (EBNF lines 1235-1238)
# ---------------------------------------------------------------------------


class TestBinaryOperatorPrecedence:
    """NOT > AND > OR > IMPLIES > IFF: the looser operator forms the root.

    Each case mixes two operators at the same parenthesization level; the
    EBNF's nesting (IffExpr ::= ImplExpr { IffOp ImplExpr } ; ImplExpr ::=
    OrExpr { ImplOp OrExpr } ; OrExpr ::= AndExpr { OrOp AndExpr } ; AndExpr
    ::= UnaryExpr { AndOp UnaryExpr }, lines 1235-1238) dictates which one
    binds tighter regardless of left-to-right order.
    """

    def test_and_binds_tighter_than_or(self):
        """(a AND b OR c) -> OR(AND(a, b), c).

        OrExpr ::= AndExpr { OrOp AndExpr } (line 1237): OR's operands are
        AndExprs, so AND groups first and OR is the root.
        """
        assert _shape(_meta_expr("(a AND b OR c)")) == ("OR", ("AND", "a", "b"), "c")

    def test_and_binds_tighter_than_or_reversed(self):
        """(a OR b AND c) -> OR(a, AND(b, c)).

        Same production as above with the operators reversed in source order,
        proving the split keys on precedence, not first occurrence (line 1237).
        """
        assert _shape(_meta_expr("(a OR b AND c)")) == ("OR", "a", ("AND", "b", "c"))

    def test_and_binds_tighter_than_iff(self):
        """(a IFF b AND c) -> IFF(a, AND(b, c)).

        IffExpr ::= ImplExpr { IffOp ImplExpr } (line 1235) with AndExpr
        nested three levels tighter (line 1238): IFF is the loosest binder.
        """
        assert _shape(_meta_expr("(a IFF b AND c)")) == ("IFF", "a", ("AND", "b", "c"))

    def test_and_binds_tighter_than_iff_reversed(self):
        """(a AND b IFF c) -> IFF(AND(a, b), c) (lines 1235, 1238)."""
        assert _shape(_meta_expr("(a AND b IFF c)")) == ("IFF", ("AND", "a", "b"), "c")

    def test_or_binds_tighter_than_implies(self):
        """(a OR b IMPLIES c) -> IMPLIES(OR(a, b), c).

        ImplExpr ::= OrExpr { ImplOp OrExpr } (line 1236): IMPLIES' operands
        are OrExprs, so OR groups first.
        """
        assert _shape(_meta_expr("(a OR b IMPLIES c)")) == (
            "IMPLIES",
            ("OR", "a", "b"),
            "c",
        )

    def test_implies_binds_tighter_than_iff(self):
        """(a IMPLIES b IFF c) -> IFF(IMPLIES(a, b), c).

        IffExpr ::= ImplExpr { IffOp ImplExpr } (line 1235): IFF's operands
        are ImplExprs, so IMPLIES groups first.
        """
        assert _shape(_meta_expr("(a IMPLIES b IFF c)")) == (
            "IFF",
            ("IMPLIES", "a", "b"),
            "c",
        )

    def test_iff_looser_than_implies_reversed(self):
        """(a IFF b IMPLIES c) -> IFF(a, IMPLIES(b, c)) (lines 1235-1236)."""
        assert _shape(_meta_expr("(a IFF b IMPLIES c)")) == (
            "IFF",
            "a",
            ("IMPLIES", "b", "c"),
        )

    def test_full_precedence_chain(self):
        """(a IFF b IMPLIES c OR d AND e) -> IFF(a, IMPLIES(b, OR(c, AND(d, e)))).

        One expression exercising every binary level of the tower at once
        (lines 1235-1238).
        """
        assert _shape(_meta_expr("(a IFF b IMPLIES c OR d AND e)")) == (
            "IFF",
            "a",
            ("IMPLIES", "b", ("OR", "c", ("AND", "d", "e"))),
        )

    def test_explicit_parens_override_precedence(self):
        """(a AND (b OR c)) -> AND(a, OR(b, c)).

        CoreExpr ::= ... | "(" Expr ")" (line 1246): parentheses reset the
        grammar to Expr, overriding the default grouping.
        """
        assert _shape(_meta_expr("(a AND (b OR c))")) == ("AND", "a", ("OR", "b", "c"))

    def test_deeply_nested_mixed_operators(self):
        """(((a AND b) IFF (c AND d)) OR (a IMPLIES b))
        -> OR(IFF(AND(a,b), AND(c,d)), IMPLIES(a, b)).

        Explicitly grouped subtrees (line 1246) survive intact under an OR root.
        """
        assert _shape(_meta_expr("(((a AND b) IFF (c AND d)) OR (a IMPLIES b))")) == (
            "OR",
            ("IFF", ("AND", "a", "b"), ("AND", "c", "d")),
            ("IMPLIES", "a", "b"),
        )


# ---------------------------------------------------------------------------
# NOT binds tightest (EBNF line 1239)
# ---------------------------------------------------------------------------


class TestNotBindsTightest:
    """UnaryExpr ::= [ NotOp ] CoreExpr (line 1239).

    NOT applies to a single CoreExpr, so it binds tighter than every binary
    operator: a prefix NOT never consumes a following binary remainder.
    """

    def test_not_binds_tighter_than_and(self):
        """(NOT a AND b) -> AND(NOT(a), b), NOT AND(NOT(a AND b))."""
        assert _shape(_meta_expr("(NOT a AND b)")) == ("AND", ("NOT", "a"), "b")

    def test_not_binds_tighter_than_or(self):
        """(NOT a OR b) -> OR(NOT(a), b) (lines 1237, 1239)."""
        assert _shape(_meta_expr("(NOT a OR b)")) == ("OR", ("NOT", "a"), "b")

    def test_not_binds_tighter_than_implies(self):
        """(NOT a IMPLIES b) -> IMPLIES(NOT(a), b) (lines 1236, 1239)."""
        assert _shape(_meta_expr("(NOT a IMPLIES b)")) == (
            "IMPLIES",
            ("NOT", "a"),
            "b",
        )

    def test_not_over_parenthesized_group(self):
        """NOT (a AND b) -> NOT(AND(a, b)): the CoreExpr operand may be a
        parenthesized Expr (lines 1239, 1246)."""
        assert _shape(_meta_expr("NOT (a AND b)")) == ("NOT", ("AND", "a", "b"))

    def test_not_in_isolation(self):
        """(NOT a) -> NOT(a) (line 1239)."""
        assert _shape(_meta_expr("(NOT a)")) == ("NOT", "a")


# ---------------------------------------------------------------------------
# Unparenthesized expressions receive structure (Expr ::= JudgedExpr, line 1232)
# ---------------------------------------------------------------------------


class TestUnparenthesizedExpressions:
    """The Expr grammar does not require outer parentheses, and split
    remainders are recursively parsed: no operand may collapse into an atomic
    predicate literally named "b OR c"."""

    def test_unparenthesized_claim_gets_structure(self):
        """a AND b OR c (no outer parens) -> OR(AND(a, b), c) (lines 1237-1238)."""
        claim = _get_meta_claim(_make_bundle_with_meta_claim("a AND b OR c"))
        assert claim.kind == "logical"
        assert _shape(claim.expr) == ("OR", ("AND", "a", "b"), "c")

    def test_unparenthesized_single_operator(self):
        """a IMPLIES b (no outer parens) -> IMPLIES(a, b) (line 1236)."""
        assert _shape(_meta_expr("a IMPLIES b")) == ("IMPLIES", "a", "b")

    def test_remainders_never_become_operator_named_predicates(self):
        """No PredicateExpr anywhere in a mixed tree keeps operator text in its
        name (the pre-rewrite defect produced e.g. PredicateExpr("b OR c"))."""
        expr = _meta_expr("(a AND b OR c IMPLIES d)")

        def collect_names(node, acc):
            if node.node == "PredicateExpr":
                acc.append(node.name)
            if node.node == "LogicalExpr":
                for arg in node.args:
                    collect_names(arg, acc)
            return acc

        for name in collect_names(expr, []):
            assert " " not in name, f"unsplit remainder leaked into predicate {name!r}"


# ---------------------------------------------------------------------------
# Operator spellings: spec kernel symbols + legacy words (lines 1240-1244)
# ---------------------------------------------------------------------------


class TestOperatorSpellings:
    """ASCII kernel spellings ``->``/``<=>`` (lines 1243-1244), Unicode forms
    ``¬ ∧ ∨ → ↔`` (lines 1240-1244), and the legacy word forms.

    IMPLIES and IFF as words are legacy spellings kept for backward
    compatibility with the vendored corpus and examples; the spec kernel
    defines only ``->``/``→`` (ImplOp) and ``<=>``/``↔`` (IffOp).
    """

    def test_ascii_arrow_is_implies(self):
        """(a -> b) -> IMPLIES(a, b): ImplOp ::= "→" | "->" (line 1243)."""
        assert _shape(_meta_expr("(a -> b)")) == ("IMPLIES", "a", "b")

    def test_ascii_iff_arrow_is_iff(self):
        """(a <=> b) -> IFF(a, b): IffOp ::= "↔" | "<=>" (line 1244)."""
        assert _shape(_meta_expr("(a <=> b)")) == ("IFF", "a", "b")

    def test_unicode_operators(self):
        """¬ ∧ ∨ → ↔ parse as NOT/AND/OR/IMPLIES/IFF (lines 1240-1244)."""
        assert _shape(_meta_expr("(a ∧ b)")) == ("AND", "a", "b")
        assert _shape(_meta_expr("(a ∨ b)")) == ("OR", "a", "b")
        assert _shape(_meta_expr("(¬a ∨ b)")) == ("OR", ("NOT", "a"), "b")
        assert _shape(_meta_expr("(a → b)")) == ("IMPLIES", "a", "b")
        assert _shape(_meta_expr("(a ↔ b)")) == ("IFF", "a", "b")

    def test_unicode_precedence_matches_words(self):
        """(a ∧ b ∨ ¬c) -> OR(AND(a, b), NOT(c)): the Unicode spellings share
        their word forms' precedence levels (lines 1237-1240)."""
        assert _shape(_meta_expr("(a ∧ b ∨ ¬c)")) == (
            "OR",
            ("AND", "a", "b"),
            ("NOT", "c"),
        )

    def test_legacy_word_spellings_still_parse(self):
        """(a IMPLIES b) / (a IFF b): legacy word forms retained for backward
        compatibility (not in the spec kernel, lines 1243-1244)."""
        assert _shape(_meta_expr("(a IMPLIES b)")) == ("IMPLIES", "a", "b")
        assert _shape(_meta_expr("(a IFF b)")) == ("IFF", "a", "b")

    def test_word_operators_require_word_boundaries(self):
        """(TARIFF AND BRAND) -> AND(TARIFF, BRAND): the IFF suffix of TARIFF
        and the AND suffix of BRAND are symbol-name text, not operators
        (word spellings match only between whitespace)."""
        assert _shape(_meta_expr("(TARIFF AND BRAND)")) == ("AND", "TARIFF", "BRAND")


# ---------------------------------------------------------------------------
# Each operator in isolation (regression coverage retained from the old file)
# ---------------------------------------------------------------------------


class TestEachLogicalOperatorInIsolation:
    """Single-operator expressions produce the matching LogicalExpr node."""

    def test_and_operator(self):
        """(a AND b) -> AND(a, b): AndOp ::= "∧" | "AND" (line 1241)."""
        expr = _meta_expr("(a AND b)")
        assert expr.node == "LogicalExpr"
        assert _shape(expr) == ("AND", "a", "b")

    def test_or_operator(self):
        """(a OR b) -> OR(a, b): OrOp ::= "∨" | "OR" (line 1242)."""
        assert _shape(_meta_expr("(a OR b)")) == ("OR", "a", "b")

    def test_iff_operator(self):
        """(a IFF b) -> IFF(a, b) (legacy word spelling of IffOp, line 1244)."""
        assert _shape(_meta_expr("(a IFF b)")) == ("IFF", "a", "b")

    def test_implies_operator(self):
        """(a IMPLIES b) -> IMPLIES(a, b) (legacy word spelling of ImplOp,
        line 1243)."""
        assert _shape(_meta_expr("(a IMPLIES b)")) == ("IMPLIES", "a", "b")


# ---------------------------------------------------------------------------
# Associativity of repeated same-precedence operators
# ---------------------------------------------------------------------------


class TestRepeatedOperatorAssociativity:
    """Repeated same-level operators flatten into one n-ary LogicalExpr.

    Documented choice: the EBNF writes each level as a repetition —
    e.g. AndExpr ::= UnaryExpr { AndOp UnaryExpr } (line 1238) — and the
    canonical AST's LogicalExprNode carries ``args: list[ExprNode]`` with
    arity >= 2, so the repetition maps to a FLAT n-ary argument list
    (matching the pre-existing AST shape used by the vendored corpus) rather
    than a left-folded binary chain.
    """

    def test_and_three_operands_flatten(self):
        """(a AND b AND c) -> AND(a, b, c) — flat, not AND(AND(a,b),c)."""
        assert _shape(_meta_expr("(a AND b AND c)")) == ("AND", "a", "b", "c")

    def test_or_three_operands_flatten(self):
        """(a OR b OR c) -> OR(a, b, c) (line 1237 repetition)."""
        assert _shape(_meta_expr("(a OR b OR c)")) == ("OR", "a", "b", "c")

    def test_implies_three_operands_flatten(self):
        """(a IMPLIES b IMPLIES c) -> IMPLIES(a, b, c) (line 1236 repetition)."""
        assert _shape(_meta_expr("(a IMPLIES b IMPLIES c)")) == (
            "IMPLIES",
            "a",
            "b",
            "c",
        )

    def test_mixed_spellings_share_a_level(self):
        """(a AND b ∧ c) -> AND(a, b, c): AndOp ::= "∧" | "AND" (line 1241)
        makes the spellings the same operator, so they flatten together."""
        assert _shape(_meta_expr("(a AND b ∧ c)")) == ("AND", "a", "b", "c")

    def test_flattening_respects_precedence_boundaries(self):
        """(a AND b AND c OR d) -> OR(AND(a, b, c), d): flattening never
        crosses a precedence level (lines 1237-1238)."""
        assert _shape(_meta_expr("(a AND b AND c OR d)")) == (
            "OR",
            ("AND", "a", "b", "c"),
            "d",
        )


# ---------------------------------------------------------------------------
# judged_by is outermost (EBNF lines 1232-1233)
# ---------------------------------------------------------------------------


class TestJudgedByOutermost:
    """Expr ::= JudgedExpr ; JudgedExpr ::= LogicalExpr [ "judged_by" Ref ]
    (lines 1232-1233): a trailing judged_by wraps the WHOLE preceding
    expression — including causal forms, whose operands are SimpleExprs
    (CausalExpr ::= SimpleExpr CausalOp SimpleExpr, line 1249) and therefore
    can never absorb the judged_by clause themselves.
    """

    def test_judged_by_wraps_causal(self):
        """p(x) =>[obs] q(y) judged_by policy://k
        -> Judged(Causal(p(x), q(y)), policy://k), NOT
        Causal(p(x), pred("q(y) judged_by policy://k")) (the pre-rewrite
        defect)."""
        claim = _get_meta_claim(
            _make_bundle_with_meta_claim("p(x) =>[obs] q(y) judged_by policy://k")
        )
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == (
            "JUDGED",
            ("CAUSAL", "obs", ("PRED", "p", "x"), ("PRED", "q", "y")),
            "policy://k",
        )

    def test_judged_by_wraps_logical(self):
        """a AND b judged_by policy://k -> Judged(AND(a, b), policy://k):
        the inner of JudgedExpr is a full LogicalExpr (line 1233)."""
        assert _shape(_meta_expr("a AND b judged_by policy://k")) == (
            "JUDGED",
            ("AND", "a", "b"),
            "policy://k",
        )

    def test_plain_judged_predicate_regression(self):
        """safe(grid_state) judged_by test://eval/judged_inner_v1 keeps the
        vendored-corpus shape (A13): Judged(safe(grid_state), ref)."""
        claim = _get_meta_claim(
            _make_bundle_with_meta_claim("safe(grid_state) judged_by test://eval/judged_inner_v1")
        )
        assert claim.kind == "judgment"
        assert _shape(claim.expr) == (
            "JUDGED",
            ("PRED", "safe", "grid_state"),
            "test://eval/judged_inner_v1",
        )

    def test_parenthesized_judged_by_stays_inner(self):
        """(a judged_by k) AND b -> AND(Judged(a, k), b): parentheses re-enter
        Expr (line 1246), so an inner judged_by binds inside its group only."""
        assert _shape(_meta_expr("(a judged_by policy://k) AND b")) == (
            "AND",
            ("JUDGED", "a", "policy://k"),
            "b",
        )


# ---------------------------------------------------------------------------
# Operator-token non-collision regressions (lines 1249-1252, 1266)
# ---------------------------------------------------------------------------


class TestOperatorTokenNonCollision:
    """Adding ImplOp ``->`` and IffOp ``<=>`` must not disturb the longer /
    distinct operator tokens: dynamic ``-->`` (DynamicOp, line 1266) and
    causal ``=>[obs]`` / ``=>[do]`` (CausalOp, line 1250)."""

    def test_dynamic_arrow_still_dynamic(self):
        """a --> |0:b| -> DynamicExpr(approaches, a, |0:b|): the ``->``
        ImplOp must not match inside the ``-->`` DynamicOp (line 1266)."""
        claim = _get_meta_claim(_make_bundle_with_meta_claim("a --> |0:b|"))
        assert claim.kind == "dynamic"
        assert _shape(claim.expr) == ("DYNAMIC", "approaches", "a", ("BASELINE", "b"))

    def test_dynamic_arrow_still_dynamic_inside_emergence(self):
        """v EMRG when m --> |0:base| keeps its DynamicExpr onset (the
        vendored-corpus A9 shape; EmergenceExpr, lines 1253-1255)."""
        claim = _get_meta_claim(_make_bundle_with_meta_claim("v EMRG when m --> |0:base|"))
        assert claim.kind == "emergence"
        assert _shape(claim.expr) == (
            "EMRG",
            "v",
            ("DYNAMIC", "approaches", "m", ("BASELINE", "base")),
        )

    def test_observational_causal_still_causal(self):
        """x =>[obs] y -> CausalExpr(obs, x, y): CausalOp ``=>[obs]``
        (line 1250) is untouched by the ``<=>``/``->`` spellings."""
        claim = _get_meta_claim(_make_bundle_with_meta_claim("x =>[obs] y"))
        assert claim.kind == "causal"
        assert _shape(claim.expr) == ("CAUSAL", "obs", "x", "y")

    def test_interventional_causal_still_causal(self):
        """x =>[do] y -> CausalExpr(do, x, y) (line 1250)."""
        claim = _get_meta_claim(_make_bundle_with_meta_claim("x =>[do] y"))
        assert claim.kind == "causal"
        assert _shape(claim.expr) == ("CAUSAL", "do", "x", "y")

    def test_causal_operands_compose_with_logical_layer(self):
        """x =>[obs] y AND z -> AND(Causal(x, y), z): CausalExpr is a CoreExpr
        (line 1246) with SimpleExpr operands (line 1249), so it binds tighter
        than the logical connectives."""
        assert _shape(_meta_expr("x =>[obs] y AND z")) == (
            "AND",
            ("CAUSAL", "obs", "x", "y"),
            "z",
        )
