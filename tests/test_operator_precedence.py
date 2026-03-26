"""R6: Operator precedence enforcement tests for the normalizer.

Verifies the normalizer's logical operator precedence order:
AND > IFF > IMPLIES > OR (first-match-wins in _LOGICAL_OPERATORS).

The normalizer's _parse_expr_text tries operators in order from the
_LOGICAL_OPERATORS list. The first operator found at the top level (outside
nested parentheses) causes the split. This means the FIRST operator in the
list (AND) has the HIGHEST precedence and binds tightest.
"""

from __future__ import annotations

import pytest

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


def _get_meta_claim_expr(source: str):
    """Normalize source and return the expr of the first meta block claim."""
    result = _normalize_source(source)
    bundle = result.canonical_ast
    meta_block = [blk for blk in bundle.claimBlocks if blk.id.startswith("meta")]
    assert meta_block, "No meta block found"
    claim = meta_block[0].claims[0]
    assert claim.kind == "logical", f"Expected logical claim, got {claim.kind}"
    return claim.expr


# ---------------------------------------------------------------------------
# R6a — Precedence order tests
# ---------------------------------------------------------------------------


class TestLogicalOperatorPrecedence:
    """Test that operator precedence follows AND > IFF > IMPLIES > OR."""

    def test_and_binds_tighter_than_or(self):
        """((a AND b) OR c) should parse as OR(AND(a,b), c).
        AND is resolved inside inner parens first."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("((a AND b) OR c)")
        )
        assert expr.op == "or"
        assert len(expr.args) == 2
        # First arg should be AND(a, b)
        and_expr = expr.args[0]
        assert and_expr.node == "LogicalExpr"
        assert and_expr.op == "and"
        assert [a.name for a in and_expr.args] == ["a", "b"]
        # Second arg should be c
        assert expr.args[1].name == "c"

    def test_and_binds_tighter_than_implies(self):
        """(a IMPLIES (b AND c)) should parse as IMPLIES(a, AND(b,c))."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IMPLIES (b AND c))")
        )
        assert expr.op == "implies"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        and_expr = expr.args[1]
        assert and_expr.op == "and"
        assert [a.name for a in and_expr.args] == ["b", "c"]

    def test_and_binds_tighter_than_iff(self):
        """((a AND b) IFF c) should parse as IFF(AND(a,b), c)."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("((a AND b) IFF c)")
        )
        assert expr.op == "iff"
        assert len(expr.args) == 2
        and_expr = expr.args[0]
        assert and_expr.op == "and"
        assert [a.name for a in and_expr.args] == ["a", "b"]
        assert expr.args[1].name == "c"

    def test_iff_binds_tighter_than_or(self):
        """((a IFF b) OR c) should parse as OR(IFF(a,b), c)."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("((a IFF b) OR c)")
        )
        assert expr.op == "or"
        assert len(expr.args) == 2
        iff_expr = expr.args[0]
        assert iff_expr.op == "iff"
        assert [a.name for a in iff_expr.args] == ["a", "b"]
        assert expr.args[1].name == "c"

    def test_implies_binds_tighter_than_or(self):
        """((a IMPLIES b) OR c) should parse as OR(IMPLIES(a,b), c)."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("((a IMPLIES b) OR c)")
        )
        assert expr.op == "or"
        assert len(expr.args) == 2
        impl_expr = expr.args[0]
        assert impl_expr.op == "implies"
        assert [a.name for a in impl_expr.args] == ["a", "b"]
        assert expr.args[1].name == "c"

    def test_iff_binds_tighter_than_implies(self):
        """((a IFF b) IMPLIES c) should parse as IMPLIES(IFF(a,b), c)."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("((a IFF b) IMPLIES c)")
        )
        assert expr.op == "implies"
        assert len(expr.args) == 2
        iff_expr = expr.args[0]
        assert iff_expr.op == "iff"
        assert [a.name for a in iff_expr.args] == ["a", "b"]
        assert expr.args[1].name == "c"

    def test_precedence_first_match_wins_and_over_iff(self):
        """Within a single paren group containing both AND and IFF at top level,
        AND should be matched first (higher precedence).

        (a AND b IFF c) -> inner text 'a AND b IFF c':
          - Try AND: found at top level -> split into ['a', 'b IFF c']
          - 'a' becomes predicate a
          - 'b IFF c' becomes predicate 'b IFF c' (not wrapped)
        Result: AND(a, pred('b IFF c'))
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a AND b IFF c)")
        )
        # AND is tried first and found, so this becomes an AND expression
        assert expr.op == "and"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        # Second arg is the unsplit remainder treated as a predicate
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b IFF c"

    def test_precedence_first_match_wins_iff_over_or(self):
        """Within a single paren group containing both IFF and OR at top level,
        IFF should be matched first (higher precedence).

        (a IFF b OR c) -> inner text 'a IFF b OR c':
          - Try AND: not found
          - Try IFF: found at top level -> split into ['a', 'b OR c']
        Result: IFF(a, pred('b OR c'))
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IFF b OR c)")
        )
        assert expr.op == "iff"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b OR c"

    def test_precedence_first_match_wins_iff_over_implies(self):
        """Within a single paren group containing both IFF and IMPLIES at top level,
        IFF should be matched first (higher precedence).

        (a IFF b IMPLIES c) -> inner text 'a IFF b IMPLIES c':
          - Try AND: not found
          - Try IFF: found at top level -> split into ['a', 'b IMPLIES c']
        Result: IFF(a, pred('b IMPLIES c'))
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IFF b IMPLIES c)")
        )
        assert expr.op == "iff"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b IMPLIES c"

    def test_precedence_first_match_wins_and_over_implies(self):
        """Within a single paren group containing both AND and IMPLIES at top level,
        AND should be matched first (higher precedence).

        (a AND b IMPLIES c) -> inner text 'a AND b IMPLIES c':
          - Try AND: found at top level -> split into ['a', 'b IMPLIES c']
          - 'a' becomes predicate a
          - 'b IMPLIES c' becomes predicate 'b IMPLIES c' (not wrapped)
        Result: AND(a, pred('b IMPLIES c'))
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a AND b IMPLIES c)")
        )
        # AND is tried first and found, so this becomes an AND expression
        assert expr.op == "and"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        # Second arg is the unsplit remainder treated as a predicate
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b IMPLIES c"

    def test_precedence_first_match_wins_and_over_or(self):
        """Within a single paren group containing both AND and OR at top level,
        AND should be matched first (higher precedence).

        (a AND b OR c) -> inner text 'a AND b OR c':
          - Try AND: found at top level -> split into ['a', 'b OR c']
          - 'a' becomes predicate a
          - 'b OR c' becomes predicate 'b OR c' (not wrapped)
        Result: AND(a, pred('b OR c'))
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a AND b OR c)")
        )
        # AND is tried first and found, so this becomes an AND expression
        assert expr.op == "and"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        # Second arg is the unsplit remainder treated as a predicate
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b OR c"

    def test_precedence_first_match_wins_implies_over_or(self):
        """Within a single paren group, IMPLIES should match before OR.

        (a IMPLIES b OR c) -> inner text 'a IMPLIES b OR c':
          - Try AND: not found
          - Try IFF: not found
          - Try IMPLIES: found! -> split into ['a', 'b OR c']
        """
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IMPLIES b OR c)")
        )
        assert expr.op == "implies"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].node == "PredicateExpr"
        assert expr.args[1].name == "b OR c"

    def test_deeply_nested_mixed_operators(self):
        """(((a AND b) IFF (c AND d)) OR (a IMPLIES b))
        -> OR(IFF(AND(a,b), AND(c,d)), IMPLIES(a, b))"""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim(
                "(((a AND b) IFF (c AND d)) OR (a IMPLIES b))"
            )
        )
        assert expr.op == "or"
        assert len(expr.args) == 2

        # First arg: IFF(AND(a,b), AND(c,d))
        iff_expr = expr.args[0]
        assert iff_expr.op == "iff"
        assert iff_expr.args[0].op == "and"
        assert [a.name for a in iff_expr.args[0].args] == ["a", "b"]
        assert iff_expr.args[1].op == "and"
        assert [a.name for a in iff_expr.args[1].args] == ["c", "d"]

        # Second arg: IMPLIES(a, b)
        impl_expr = expr.args[1]
        assert impl_expr.op == "implies"
        assert [a.name for a in impl_expr.args] == ["a", "b"]


# ---------------------------------------------------------------------------
# R6b — All operators in isolation
# ---------------------------------------------------------------------------


class TestEachLogicalOperatorInIsolation:
    """Test that each of the 4 logical operators can be parsed in isolation."""

    def test_and_operator(self):
        """(a AND b) parses to LogicalExpr with op='and'."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a AND b)")
        )
        assert expr.node == "LogicalExpr"
        assert expr.op == "and"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].name == "b"

    def test_or_operator(self):
        """(a OR b) parses to LogicalExpr with op='or'."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a OR b)")
        )
        assert expr.node == "LogicalExpr"
        assert expr.op == "or"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].name == "b"

    def test_iff_operator(self):
        """(a IFF b) parses to LogicalExpr with op='iff'."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IFF b)")
        )
        assert expr.node == "LogicalExpr"
        assert expr.op == "iff"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].name == "b"

    def test_implies_operator(self):
        """(a IMPLIES b) parses to LogicalExpr with op='implies'."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a IMPLIES b)")
        )
        assert expr.node == "LogicalExpr"
        assert expr.op == "implies"
        assert len(expr.args) == 2
        assert expr.args[0].name == "a"
        assert expr.args[1].name == "b"

    def test_not_operator(self):
        """(NOT a) parses to LogicalExpr with op='not'."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(NOT a)")
        )
        assert expr.node == "LogicalExpr"
        assert expr.op == "not"
        assert len(expr.args) == 1
        assert expr.args[0].name == "a"

    def test_and_with_three_operands(self):
        """(a AND b AND c) should produce AND with 3 args."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a AND b AND c)")
        )
        assert expr.op == "and"
        assert len(expr.args) == 3
        assert [a.name for a in expr.args] == ["a", "b", "c"]

    def test_or_with_three_operands(self):
        """(a OR b OR c) should produce OR with 3 args."""
        expr = _get_meta_claim_expr(
            _make_bundle_with_meta_claim("(a OR b OR c)")
        )
        assert expr.op == "or"
        assert len(expr.args) == 3
        assert [a.name for a in expr.args] == ["a", "b", "c"]
