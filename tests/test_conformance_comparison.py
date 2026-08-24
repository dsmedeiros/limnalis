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


# ---------------------------------------------------------------------------
# m7 red-team MEDIUM-2 (remediation cycle 1): claimIds comparison
# ---------------------------------------------------------------------------


class TestClaimIdsComparisonUnit:
    """_compare_block compares claimIds pins ORDER-SENSITIVELY against
    BlockResult.claims (previously the pins were never read)."""

    @staticmethod
    def _step_with_block(claims: list[str]) -> StepResult:
        from limnalis.runtime.models import BlockResult

        return StepResult(
            step_id="step0",
            per_block_aggregates={"local#1": EvalNode(truth="T")},
            block_results=[
                BlockResult(
                    block_id="local#1",
                    aggregate=EvalNode(truth="T"),
                    claims=claims,
                )
            ],
        )

    def _mismatches_for(self, pinned: list[str], actual: list[str]):
        from limnalis.conformance.compare import _compare_block

        step_result = self._step_with_block(actual)
        mismatches: list[FieldMismatch] = []
        _compare_block(
            "steps[0].blocks.local",
            {"claimIds": pinned},
            step_result,
            "local",  # stratum name resolves to local#1
            mismatches,
        )
        return mismatches

    def test_matching_claim_ids_pass(self):
        assert self._mismatches_for(["c1", "c2"], ["c1", "c2"]) == []

    def test_wrong_membership_flagged(self):
        mismatches = self._mismatches_for(["c1", "c2"], ["c1"])
        assert len(mismatches) == 1
        assert mismatches[0].path == "steps[0].blocks.local.claimIds"
        assert mismatches[0].expected == ["c1", "c2"]
        assert mismatches[0].actual == ["c1"]

    def test_wrong_order_flagged(self):
        """The corpus convention pins the declaration order; a reordered
        listing is a mismatch."""
        mismatches = self._mismatches_for(["c2", "c1"], ["c1", "c2"])
        assert len(mismatches) == 1
        assert mismatches[0].path.endswith(".claimIds")

    def test_missing_block_result_flagged(self):
        from limnalis.conformance.compare import _compare_block

        step_result = StepResult(step_id="step0")  # no block results at all
        mismatches: list[FieldMismatch] = []
        _compare_block(
            "steps[0].blocks.local",
            {"claimIds": ["c1"]},
            step_result,
            "local",
            mismatches,
        )
        assert any(
            m.path.endswith(".claimIds") and m.actual is None for m in mismatches
        )

    def test_unpinned_claim_ids_not_compared(self):
        """A block expectation without claimIds pins nothing about the
        listing (§18.2 partial matchers)."""
        from limnalis.conformance.compare import _compare_block

        step_result = self._step_with_block(["c1", "c2"])
        mismatches: list[FieldMismatch] = []
        _compare_block(
            "steps[0].blocks.local",
            {"aggregate": "T"},
            step_result,
            "local",
            mismatches,
        )
        assert mismatches == []


# ---------------------------------------------------------------------------
# m7 red-team MEDIUM-2 (remediation cycle 1): step-level reverse checks
# ---------------------------------------------------------------------------


class TestStepLevelReverseChecksUnit:
    """_compare_session flags actual claims/blocks/transports absent from a
    pinned map, with the two documented exemptions (non-evaluable note
    claims; per-bridge transport scaffolding)."""

    @staticmethod
    def _classification(claim_id: str, evaluable: bool):
        from limnalis.runtime.models import ClaimClassification

        return ClaimClassification(
            claim_id=claim_id,
            evaluable=evaluable,
            expr_kind="NoteExpr" if not evaluable else "PredicateExpr",
        )

    def _compare(self, sess_exp, step_result, bridge_ids=None):
        from limnalis.conformance.compare import _compare_session
        from limnalis.runtime.runner import SessionResult

        sess_result = SessionResult(session_id="s0", step_results=[step_result])
        mismatches: list[FieldMismatch] = []
        _compare_session(
            "sessions[0]", sess_exp, sess_result, mismatches,
            warnings=None, bridge_ids=bridge_ids,
        )
        return mismatches

    def test_extra_evaluable_claim_flagged(self):
        step_result = StepResult(
            step_id="step0",
            per_claim_aggregates={
                "c1": EvalNode(truth="T"),
                "c_leak": EvalNode(truth="F"),
            },
            per_claim_classifications={
                "c1": self._classification("c1", True),
                "c_leak": self._classification("c_leak", True),
            },
        )
        sess_exp = {"steps": [{"claims": {"c1": {"aggregate": "T"}}}]}
        mismatches = self._compare(sess_exp, step_result)
        assert any(
            m.path == "sessions[0].steps[0].claims.c_leak"
            and m.expected == "not expected"
            for m in mismatches
        )

    def test_note_claim_exempt(self):
        """Non-evaluable claims are omitted from expectations by the
        vendored convention (e.g. B1 c5) and must not be flagged."""
        step_result = StepResult(
            step_id="step0",
            per_claim_aggregates={
                "c1": EvalNode(truth="T"),
                "n1": EvalNode(truth="N", reason="non_evaluable_note"),
            },
            per_claim_classifications={
                "c1": self._classification("c1", True),
                "n1": self._classification("n1", False),
            },
        )
        sess_exp = {"steps": [{"claims": {"c1": {"aggregate": "T"}}}]}
        assert self._compare(sess_exp, step_result) == []

    def test_unclassified_extra_claim_flagged(self):
        """A claim with no classification entry defaults to the strict side
        of the check."""
        step_result = StepResult(
            step_id="step0",
            per_claim_aggregates={
                "c1": EvalNode(truth="T"),
                "c_mystery": EvalNode(truth="F"),
            },
        )
        sess_exp = {"steps": [{"claims": {"c1": {"aggregate": "T"}}}]}
        mismatches = self._compare(sess_exp, step_result)
        assert any("c_mystery" in m.path for m in mismatches)

    def test_no_claims_key_no_reverse_check(self):
        """A step expectation that pins no claims map triggers no reverse
        check (§18.2 partial matchers)."""
        step_result = StepResult(
            step_id="step0",
            per_claim_aggregates={"c1": EvalNode(truth="T")},
        )
        sess_exp = {"steps": [{}]}
        assert self._compare(sess_exp, step_result) == []

    def test_extra_block_flagged(self):
        step_result = StepResult(
            step_id="step0",
            per_block_aggregates={
                "local#1": EvalNode(truth="T"),
                "meta#1": EvalNode(truth="N"),
            },
        )
        sess_exp = {"steps": [{"blocks": {"local#1": {"aggregate": "T"}}}]}
        mismatches = self._compare(sess_exp, step_result)
        assert any(
            m.path == "sessions[0].steps[0].blocks.meta#1"
            and m.expected == "not expected"
            for m in mismatches
        )

    def test_extra_transport_query_flagged_bridge_exempt(self):
        from limnalis.runtime.models import TransportResult

        step_result = StepResult(
            step_id="step0",
            transport_results={
                "q1": TransportResult(status="preserved"),
                "q_extra": TransportResult(status="preserved"),
                "b_bridge": TransportResult(status="preserved"),
            },
        )
        sess_exp = {
            "steps": [{"transports": {"q1": {"status": "preserved"}}}]
        }
        mismatches = self._compare(
            sess_exp, step_result, bridge_ids={"b_bridge"}
        )
        flagged = [m.path for m in mismatches]
        assert "sessions[0].steps[0].transports.q_extra" in flagged
        assert "sessions[0].steps[0].transports.b_bridge" not in flagged

    def test_transport_reverse_check_skipped_without_bridge_ids(self):
        """bridge_ids=None means the bundle is unavailable, so the
        scaffolding exemption cannot be computed and the transport reverse
        check is skipped."""
        from limnalis.runtime.models import TransportResult

        step_result = StepResult(
            step_id="step0",
            transport_results={
                "q1": TransportResult(status="preserved"),
                "q_extra": TransportResult(status="preserved"),
            },
        )
        sess_exp = {
            "steps": [{"transports": {"q1": {"status": "preserved"}}}]
        }
        assert self._compare(sess_exp, step_result, bridge_ids=None) == []

    def test_compare_case_stub_without_bundle_attr_does_not_crash(self):
        """compare_case tolerates stubbed run results that lack a .bundle
        attribute (bridge_ids resolves to None -> transport reverse check
        skipped)."""
        from limnalis.runtime.models import TransportResult

        case = SimpleNamespace(
            id="STUB",
            expected={
                "sessions": [
                    {
                        "steps": [
                            {"transports": {"q1": {"status": "preserved"}}}
                        ],
                    },
                ],
            },
        )
        run_result = SimpleNamespace(
            case_id="STUB",
            error=None,
            bundle_result=BundleResult(
                bundle_id="STUB",
                session_results=[
                    SessionResult(
                        session_id="s0",
                        step_results=[
                            StepResult(
                                step_id="step0",
                                transport_results={
                                    "q1": TransportResult(status="preserved"),
                                    "q_extra": TransportResult(status="preserved"),
                                },
                            ),
                        ],
                    ),
                ],
            ),
        )
        comparison = compare_case(case, run_result)
        assert comparison.passed


# ---------------------------------------------------------------------------
# m7 red-team comparator follow-up (remediation cycle 1): B/N reason
# under-pin warnings
# ---------------------------------------------------------------------------


class TestReasonUnderPinWarningUnit:
    """_compare_eval_snapshot surfaces a WARNING (never a mismatch) when a
    B/N truth is pinned without a reason while the actual result carries
    one — §8.5 makes B/N reasons mandatory on the result side, so the
    actual is spec-correct and only the pin is under-specified."""

    def _run(self, expected, actual_node):
        from limnalis.conformance.compare import _compare_eval_snapshot

        mismatches: list[FieldMismatch] = []
        warnings: list[FieldMismatch] = []
        _compare_eval_snapshot("p", expected, actual_node, mismatches, warnings)
        return mismatches, warnings

    def test_b_truth_without_reason_pin_warns(self):
        mismatches, warnings = self._run(
            {"truth": "B"}, EvalNode(truth="B", reason="source_conflict")
        )
        assert mismatches == []
        assert len(warnings) == 1
        assert warnings[0].path == "p.reason"
        assert warnings[0].actual == "source_conflict"

    def test_n_truth_without_reason_pin_warns(self):
        mismatches, warnings = self._run(
            {"truth": "N"}, EvalNode(truth="N", reason="undefined_term")
        )
        assert mismatches == []
        assert [w.actual for w in warnings] == ["undefined_term"]

    def test_pinned_reason_does_not_warn(self):
        mismatches, warnings = self._run(
            {"truth": "N", "reason": "undefined_term"},
            EvalNode(truth="N", reason="undefined_term"),
        )
        assert mismatches == []
        assert warnings == []

    def test_t_truth_without_reason_does_not_warn(self):
        mismatches, warnings = self._run(
            {"truth": "T"}, EvalNode(truth="T", reason="some_annotation")
        )
        assert mismatches == []
        assert warnings == []

    def test_reasonless_actual_does_not_warn(self):
        mismatches, warnings = self._run({"truth": "B"}, EvalNode(truth="B"))
        assert mismatches == []
        assert warnings == []

    def test_warning_channel_optional(self):
        """Callers that pass no warnings list (the pre-existing positional
        signature) keep working; the warning is simply suppressed."""
        from limnalis.conformance.compare import _compare_eval_snapshot

        mismatches: list[FieldMismatch] = []
        _compare_eval_snapshot(
            "p", {"truth": "B"}, EvalNode(truth="B", reason="source_conflict"),
            mismatches,
        )
        assert mismatches == []

    def test_warning_never_affects_passed(self):
        """End-to-end: a case whose only divergence is an under-pinned B/N
        reason still passes, with the warning on the comparison report."""
        case = SimpleNamespace(
            id="WARN_TEST",
            expected={
                "sessions": [
                    {
                        "steps": [
                            {
                                "claims": {
                                    "c1": {"aggregate": {"truth": "N"}},
                                },
                            },
                        ],
                    },
                ],
            },
        )
        run_result = SimpleNamespace(
            case_id="WARN_TEST",
            error=None,
            bundle_result=BundleResult(
                bundle_id="WARN_TEST",
                session_results=[
                    SessionResult(
                        session_id="s0",
                        step_results=[
                            StepResult(
                                step_id="step0",
                                per_claim_aggregates={
                                    "c1": EvalNode(
                                        truth="N", reason="undefined_term"
                                    ),
                                },
                            ),
                        ],
                    ),
                ],
            ),
        )
        comparison = compare_case(case, run_result)
        assert comparison.passed
        assert len(comparison.warnings) == 1
        assert comparison.warnings[0].path.endswith("claims.c1.aggregate.reason")
