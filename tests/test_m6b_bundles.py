"""Tests for M6B stress-test bundles: parse and normalize."""

from __future__ import annotations

from pathlib import Path

import pytest

from limnalis.parser import LimnalisParser
from limnalis.loader import normalize_surface_text

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
CWT_BUNDLE = EXAMPLES_DIR / "cwt_transport_bundle.lmn"
GOV_BUNDLE = EXAMPLES_DIR / "governance_stack_bundle.lmn"


@pytest.fixture(scope="module")
def cwt_source():
    return CWT_BUNDLE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gov_source():
    return GOV_BUNDLE.read_text(encoding="utf-8")


# ===================================================================
# CWT Transport Bundle
# ===================================================================


class TestCWTBundle:
    def test_cwt_bundle_parses(self, cwt_source):
        """CWT bundle parses without error."""
        parser = LimnalisParser()
        tree = parser.parse_text(cwt_source)
        assert tree is not None

    def test_cwt_bundle_normalizes(self, cwt_source):
        """CWT bundle normalizes, produces valid AST."""
        result = normalize_surface_text(cwt_source, validate_schema=False)
        assert result is not None
        ast = result.canonical_ast
        assert ast is not None
        assert ast.node == "Bundle"

    def test_cwt_bundle_has_bridges(self, cwt_source):
        """Normalized AST has 2 bridges."""
        result = normalize_surface_text(cwt_source, validate_schema=False)
        ast = result.canonical_ast
        assert ast is not None
        assert len(ast.bridges) == 2

    def test_cwt_bundle_has_transport(self, cwt_source):
        """Bridges have transport nodes."""
        result = normalize_surface_text(cwt_source, validate_schema=False)
        ast = result.canonical_ast
        assert ast is not None
        for bridge in ast.bridges:
            assert bridge.transport is not None
            assert bridge.transport.mode in (
                "metadata_only", "preserve", "degrade", "remap_recompute"
            )


# ===================================================================
# Governance Stack Bundle
# ===================================================================


class TestGovernanceBundle:
    def test_governance_bundle_parses(self, gov_source):
        """Governance bundle parses."""
        parser = LimnalisParser()
        tree = parser.parse_text(gov_source)
        assert tree is not None

    def test_governance_bundle_normalizes(self, gov_source):
        """Governance bundle normalizes."""
        result = normalize_surface_text(gov_source, validate_schema=False)
        assert result is not None
        ast = result.canonical_ast
        assert ast is not None
        assert ast.node == "Bundle"

    def test_governance_bundle_has_evaluators(self, gov_source):
        """Has 3 evaluators."""
        result = normalize_surface_text(gov_source, validate_schema=False)
        ast = result.canonical_ast
        assert ast is not None
        assert len(ast.evaluators) == 3

    def test_governance_bundle_has_evidence_relations(self, gov_source):
        """Has evidence relations."""
        result = normalize_surface_text(gov_source, validate_schema=False)
        ast = result.canonical_ast
        assert ast is not None
        assert len(ast.evidenceRelations) >= 1

    def test_governance_bundle_has_adequacy(self, gov_source):
        """Has adequacy assessments."""
        result = normalize_surface_text(gov_source, validate_schema=False)
        ast = result.canonical_ast
        assert ast is not None
        # Adequacy can be on anchors
        has_adequacy = any(len(a.adequacy) > 0 for a in ast.anchors)
        assert has_adequacy, "Expected at least one anchor with adequacy assessments"
