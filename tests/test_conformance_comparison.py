"""Targeted unit tests for conformance comparison fixes D3, D4, and F1.

These tests isolate specific fixes to the conformance comparison logic:
- D3: Extra-diagnostic blindness — extra error/fatal diagnostics are flagged
- D4: Reverse evaluator check — extra evaluators in actual are flagged
- F1: Frame completion — bundle_frame_completion prevents frame_unresolved diagnostics
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from limnalis.conformance.compare import (
    FieldMismatch,
    _compare_claim,
    _compare_diagnostics,
    compare_case,
)
from limnalis.conformance.fixtures import load_corpus_from_default
from limnalis.conformance.runner import run_case
from limnalis.runtime.models import EvalNode
from limnalis.runtime.runner import BundleResult, SessionResult, StepResult


# ---------------------------------------------------------------------------
# Shared fixture: load corpus once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus():
    return load_corpus_from_default()


# ---------------------------------------------------------------------------
# R5a — D3: Extra-diagnostic blindness
# ---------------------------------------------------------------------------


class TestD3ExtraDiagnosticDetection:
    """Verify that extra error/fatal diagnostics in actual are flagged as mismatches.

    These tests exercise _compare_diagnostics return values directly.
    The D3 fix (promoting unmatched error/fatal diagnostics to FieldMismatch)
    is tested end-to-end in test_compare_case_flags_extra_error_diagnostic_end_to_end below.
    """

    def test_extra_error_diagnostic_flagged(self):
        """When actual has an extra error-level diagnostic not in expected,
        compare_case must flag it as a FieldMismatch."""
        expected_diags = [
            {"code": "expected_diag", "severity": "warning"},
        ]
        actual_diags = [
            {"code": "expected_diag", "severity": "warning"},
            {"code": "surprise_error", "severity": "error"},
        ]
        mismatches: list[FieldMismatch] = []

        unmatched = _compare_diagnostics(
            "diagnostics", expected_diags, actual_diags, mismatches
        )

        # _compare_diagnostics returns unmatched actuals; the caller (compare_case)
        # flags error/fatal ones as mismatches. Verify the unmatched list.
        assert len(mismatches) == 0, "No expected diag should be missing"
        assert len(unmatched) == 1
        assert unmatched[0]["code"] == "surprise_error"
        assert unmatched[0]["severity"] == "error"

    def test_extra_fatal_diagnostic_flagged(self):
        """Extra fatal diagnostics should also be flagged."""
        expected_diags = [
            {"code": "expected_diag", "severity": "info"},
        ]
        actual_diags = [
            {"code": "expected_diag", "severity": "info"},
            {"code": "crash", "severity": "fatal"},
        ]
        mismatches: list[FieldMismatch] = []

        unmatched = _compare_diagnostics(
            "diagnostics", expected_diags, actual_diags, mismatches
        )

        assert len(mismatches) == 0
        assert len(unmatched) == 1
        assert unmatched[0]["severity"] == "fatal"

    def test_extra_warning_diagnostic_not_flagged(self):
        """Extra warning-level diagnostics should NOT be flagged as mismatches."""
        expected_diags = [
            {"code": "expected_diag", "severity": "info"},
        ]
        actual_diags = [
            {"code": "expected_diag", "severity": "info"},
            {"code": "harmless_warning", "severity": "warning"},
        ]
        mismatches: list[FieldMismatch] = []

        unmatched = _compare_diagnostics(
            "diagnostics", expected_diags, actual_diags, mismatches
        )

        assert len(mismatches) == 0
        # Warning is in unmatched but NOT error/fatal, so compare_case won't flag it
        assert len(unmatched) == 1
        assert unmatched[0]["severity"] == "warning"

    def test_compare_case_flags_extra_error_diagnostic_end_to_end(self):
        """End-to-end: compare_case must produce a mismatch for extra error diagnostics."""
        case = SimpleNamespace(
            id="D3_TEST",
            expected={
                "diagnostics": [
                    {"code": "known_diag", "severity": "warning"},
                ],
            },
        )
        run_result = SimpleNamespace(
            case_id="D3_TEST",
            error=None,
            bundle_result=SimpleNamespace(
                session_results=[],
                diagnostics=[
                    {"code": "known_diag", "severity": "warning"},
                    {"code": "unexpected_error", "severity": "error"},
                ],
            ),
        )

        comparison = compare_case(case, run_result)

        assert not comparison.passed, "Extra error diagnostic should cause failure"
        extra_diag_mismatches = [
            m for m in comparison.mismatches
            if "not expected" in str(m.expected)
        ]
        assert len(extra_diag_mismatches) >= 1
        assert any(
            m.actual.get("code") == "unexpected_error"
            for m in extra_diag_mismatches
            if isinstance(m.actual, dict)
        )


# ---------------------------------------------------------------------------
# R5b — D4: Reverse evaluator check
# ---------------------------------------------------------------------------


class TestD4ReverseEvaluatorCheck:
    """Verify that extra evaluators in actual per_evaluator are flagged."""

    def test_extra_evaluator_flagged_via_compare_claim(self):
        """When actual has evaluators {ev0, ev1} but expected only has {ev0},
        ev1 must appear as a FieldMismatch."""
        claim_exp = {
            "per_evaluator": {
                "ev0": {"truth": "T"},
            },
        }

        # Build a mock StepResult with per_claim_per_evaluator containing ev0 and ev1
        step_result = SimpleNamespace(
            per_claim_per_evaluator={
                "c1": {
                    "ev0": EvalNode(truth="T"),
                    "ev1": EvalNode(truth="F"),
                },
            },
            per_claim_aggregates={},
            per_claim_licenses={},
        )

        mismatches: list[FieldMismatch] = []
        _compare_claim(
            "steps[0].claims.c1",
            claim_exp,
            step_result,
            "c1",
            mismatches,
        )

        # ev0 should match, ev1 should be flagged
        extra_ev_mismatches = [
            m for m in mismatches if "ev1" in m.path
        ]
        assert len(extra_ev_mismatches) == 1, (
            f"Expected 1 mismatch for extra ev1, got {len(extra_ev_mismatches)}: {mismatches}"
        )
        assert extra_ev_mismatches[0].expected == "not expected"

    def test_no_extra_evaluator_when_sets_match(self):
        """When expected and actual have the same evaluator set, no extra mismatch."""
        claim_exp = {
            "per_evaluator": {
                "ev0": {"truth": "T"},
                "ev1": {"truth": "F"},
            },
        }

        step_result = SimpleNamespace(
            per_claim_per_evaluator={
                "c1": {
                    "ev0": EvalNode(truth="T"),
                    "ev1": EvalNode(truth="F"),
                },
            },
            per_claim_aggregates={},
            per_claim_licenses={},
        )

        mismatches: list[FieldMismatch] = []
        _compare_claim(
            "steps[0].claims.c1",
            claim_exp,
            step_result,
            "c1",
            mismatches,
        )

        assert len(mismatches) == 0

    def test_multiple_extra_evaluators_all_flagged(self):
        """When actual has two extra evaluators, both should be flagged."""
        claim_exp = {
            "per_evaluator": {
                "ev0": {"truth": "T"},
            },
        }

        step_result = SimpleNamespace(
            per_claim_per_evaluator={
                "c1": {
                    "ev0": EvalNode(truth="T"),
                    "ev_extra1": EvalNode(truth="F"),
                    "ev_extra2": EvalNode(truth="N"),
                },
            },
            per_claim_aggregates={},
            per_claim_licenses={},
        )

        mismatches: list[FieldMismatch] = []
        _compare_claim(
            "steps[0].claims.c1",
            claim_exp,
            step_result,
            "c1",
            mismatches,
        )

        extra_paths = [m.path for m in mismatches if "not expected" in str(m.expected)]
        assert "steps[0].claims.c1.per_evaluator.ev_extra1" in extra_paths
        assert "steps[0].claims.c1.per_evaluator.ev_extra2" in extra_paths


    def test_compare_case_flags_extra_evaluator_end_to_end(self):
        """End-to-end: compare_case must produce passed=False when actual has
        an extra evaluator not present in expected per_evaluator."""
        case = SimpleNamespace(
            id="D4_TEST",
            expected={
                "sessions": [
                    {
                        "steps": [
                            {
                                "claims": {
                                    "c1": {
                                        "per_evaluator": {
                                            "ev0": {"truth": "T"},
                                        },
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        )
        run_result = SimpleNamespace(
            case_id="D4_TEST",
            error=None,
            bundle_result=BundleResult(
                bundle_id="D4_TEST",
                session_results=[
                    SessionResult(
                        session_id="s0",
                        step_results=[
                            StepResult(
                                step_id="step0",
                                per_claim_per_evaluator={
                                    "c1": {
                                        "ev0": EvalNode(truth="T"),
                                        "ev_extra": EvalNode(truth="F"),
                                    },
                                },
                            ),
                        ],
                    ),
                ],
            ),
        )

        comparison = compare_case(case, run_result)

        assert not comparison.passed, "Extra evaluator should cause failure"
        extra_ev_mismatches = [
            m for m in comparison.mismatches
            if "ev_extra" in m.path
        ]
        assert len(extra_ev_mismatches) >= 1, (
            f"Expected mismatch for extra evaluator ev_extra, got: {comparison.mismatches}"
        )
        assert any(
            "not expected" in str(m.expected)
            for m in extra_ev_mismatches
        )


# ---------------------------------------------------------------------------
# R5c — F1: Frame completion
# ---------------------------------------------------------------------------


class TestF1FrameCompletion:
    """Verify that frame_resolver.bundle_frame_completion prevents
    frame_unresolved_for_evaluation diagnostics."""

    def test_a1_has_frame_completion_no_unresolved_diagnostic(self, corpus):
        """A1 provides bundle_frame_completion in its environment.
        The result should NOT contain a frame_unresolved_for_evaluation diagnostic."""
        case = corpus.get_case("A1")
        assert case is not None

        # Verify A1 actually has frame_resolver with completion data
        frame_resolver = case.environment.get("frame_resolver")
        assert frame_resolver is not None
        assert "bundle_frame_completion" in frame_resolver

        result = run_case(case, corpus)
        assert result.error is None

        # Collect all diagnostics
        from limnalis.conformance.compare import _collect_all_diagnostics
        all_diags = _collect_all_diagnostics(result.bundle_result)

        # No frame_unresolved_for_evaluation diagnostic should appear
        unresolved_diags = [
            d for d in all_diags if d.get("code") == "frame_unresolved_for_evaluation"
        ]
        assert len(unresolved_diags) == 0, (
            f"A1 with frame completion should have no frame_unresolved diagnostic, "
            f"but found: {unresolved_diags}"
        )

    def test_a2_without_frame_completion_expects_unresolved_diagnostic(self, corpus):
        """A2 has frame_resolver=None, so frame_unresolved_for_evaluation IS expected."""
        case = corpus.get_case("A2")
        assert case is not None

        # Verify A2 does NOT have frame completion
        frame_resolver = case.environment.get("frame_resolver")
        assert frame_resolver is None

        # The expected diagnostics should include frame_unresolved_for_evaluation
        expected_diags = case.expected.get("diagnostics", [])
        has_unresolved = any(
            d.get("code") == "frame_unresolved_for_evaluation" for d in expected_diags
        )
        assert has_unresolved, (
            "A2 should expect a frame_unresolved_for_evaluation diagnostic"
        )

        # Run the case and verify the diagnostic appears
        result = run_case(case, corpus)
        assert result.error is None

        from limnalis.conformance.compare import _collect_all_diagnostics
        all_diags = _collect_all_diagnostics(result.bundle_result)

        unresolved_diags = [
            d for d in all_diags if d.get("code") == "frame_unresolved_for_evaluation"
        ]
        assert len(unresolved_diags) >= 1, (
            "A2 without frame completion should produce frame_unresolved diagnostic"
        )

    def test_a1_a2_contrast_frame_completion_effect(self, corpus):
        """Contrast A1 (with completion) and A2 (without): only A2 should have
        the frame_unresolved_for_evaluation diagnostic."""
        from limnalis.conformance.compare import _collect_all_diagnostics

        case_a1 = corpus.get_case("A1")
        case_a2 = corpus.get_case("A2")
        assert case_a1 is not None
        assert case_a2 is not None

        result_a1 = run_case(case_a1, corpus)
        result_a2 = run_case(case_a2, corpus)

        diags_a1 = _collect_all_diagnostics(result_a1.bundle_result)
        diags_a2 = _collect_all_diagnostics(result_a2.bundle_result)

        a1_unresolved = [d for d in diags_a1 if d.get("code") == "frame_unresolved_for_evaluation"]
        a2_unresolved = [d for d in diags_a2 if d.get("code") == "frame_unresolved_for_evaluation"]

        assert len(a1_unresolved) == 0, "A1 (with frame completion) should have no unresolved"
        assert len(a2_unresolved) >= 1, "A2 (without frame completion) should have unresolved"
