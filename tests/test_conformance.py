"""Tests for corpus conformance execution.

Each required fixture case runs end-to-end through the conformance harness
(parse -> normalize -> run -> compare) and must produce zero mismatches.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from limnalis.cli import main
from limnalis.conformance.compare import FieldMismatch, _compare_license, compare_case
from limnalis.conformance.fixtures import load_corpus_from_default
from limnalis.models.ast import FrameNode
from limnalis.conformance.runner import (
    _build_fixture_synthesize_support,
    _build_per_step_support_maps,
    run_case,
)
from limnalis.runtime.models import (
    JointLicenseEntry,
    LicenseOverall,
    LicenseResult,
    MachineState,
    StepContext,
    TruthCore,
)


# ---------------------------------------------------------------------------
# Shared fixture: load corpus once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def corpus():
    return load_corpus_from_default()


# ---------------------------------------------------------------------------
# Helper: run a single case through the full harness
# ---------------------------------------------------------------------------


def _run_and_compare(corpus, case_id: str):
    case = corpus.get_case(case_id)
    assert case is not None, f"Case {case_id} not found in corpus"
    result = run_case(case, corpus)
    assert result.error is None, f"Runner error for {case_id}: {result.error}"
    comparison = compare_case(case, result)
    if not comparison.passed:
        details = "\n".join(str(m) for m in comparison.mismatches)
        pytest.fail(f"Case {case_id} failed:\n{details}")
    return comparison


# ---------------------------------------------------------------------------
# 3A regressions (must still pass)
# ---------------------------------------------------------------------------


class TestRegressions3A:
    """Cases that must continue to pass from iteration 3A."""

    def test_a3_logical_composition(self, corpus):
        _run_and_compare(corpus, "A3")

    def test_a11_session_baseline_timing(self, corpus):
        _run_and_compare(corpus, "A11")

    def test_a13_core_judged_expr(self, corpus):
        _run_and_compare(corpus, "A13")

    def test_a14_adjudicated_resolution(self, corpus):
        _run_and_compare(corpus, "A14")


# ---------------------------------------------------------------------------
# 3B new required targets
# ---------------------------------------------------------------------------


class TestNewTargets3B:
    """Cases newly required in iteration 3B."""

    def test_a1_resolved_shorthand_frame(self, corpus):
        _run_and_compare(corpus, "A1")

    def test_a5_evidence_conflict_partial_support(self, corpus):
        _run_and_compare(corpus, "A5")

    def test_a6_individual_joint_adequacy(self, corpus):
        _run_and_compare(corpus, "A6")

    def test_a10_transport_truth_modes(self, corpus):
        _run_and_compare(corpus, "A10")

    def test_a12_adequacy_method_conflict_circularity(self, corpus):
        _run_and_compare(corpus, "A12")

    def test_b1_grid_contingency_bundle(self, corpus):
        _run_and_compare(corpus, "B1")

    def test_b2_jwt_access_adequacy_bundle(self, corpus):
        _run_and_compare(corpus, "B2")


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestConformanceCLI:
    """Tests for conformance CLI subcommands."""

    def test_conformance_list(self, capsys):
        code = main(["conformance", "list"])
        captured = capsys.readouterr()
        assert code == 0
        # Should list all cases with their IDs
        assert "A1" in captured.out
        assert "B2" in captured.out

    def test_conformance_show(self, capsys):
        code = main(["conformance", "show", "A1"])
        captured = capsys.readouterr()
        assert code == 0
        # Should show case details
        assert "A1" in captured.out

    def test_conformance_run_single(self, capsys):
        code = main(["conformance", "run", "--cases", "A5"])
        captured = capsys.readouterr()
        assert code == 0
        assert "PASS" in captured.out
        assert "A5" in captured.out


# ---------------------------------------------------------------------------
# Intentional mismatch test
# ---------------------------------------------------------------------------


class TestMismatchDetection:
    """Verify that comparison logic correctly detects mismatches."""

    def test_intentional_mismatch_detected(self, corpus):
        """Run a case but tamper with the expected values to verify
        the comparison catches the discrepancy."""
        case = corpus.get_case("A5")
        assert case is not None

        result = run_case(case, corpus)
        assert result.error is None

        # Tamper with the expected truth to force a mismatch
        import copy
        tampered_case = copy.deepcopy(case)
        sessions = tampered_case.expected.get("sessions", [])
        if sessions:
            steps = sessions[0].get("steps", [])
            if steps:
                claims = steps[0].get("claims", {})
                for claim_id in claims:
                    pe = claims[claim_id].get("per_evaluator", {})
                    for ev_id in pe:
                        if isinstance(pe[ev_id], dict):
                            # Flip truth value to force mismatch
                            original = pe[ev_id].get("truth", "T")
                            pe[ev_id]["truth"] = "F" if original == "T" else "T"
                        break
                    break

        comparison = compare_case(tampered_case, result)
        assert not comparison.passed, "Expected comparison to detect tampered mismatch"
        assert len(comparison.mismatches) > 0


class TestConformanceSupportMapping:
    """Verify fixture support expectations are tracked per step."""

    def test_support_map_and_fixture_support_are_step_scoped(self):
        case = SimpleNamespace(
            expected_sessions=lambda: [
                {
                    "steps": [
                        {"claims": {"c1": {"per_evaluator": {"ev1": {"support": "supported"}}}}},
                        {"claims": {"c1": {"per_evaluator": {"ev1": {"support": "conflicted"}}}}},
                    ]
                }
            ]
        )
        per_step = _build_per_step_support_maps(case)
        assert per_step[0]["c1"]["ev1"] == "supported"
        assert per_step[1]["c1"]["ev1"] == "conflicted"

        fixture_synth = _build_fixture_synthesize_support(
            per_step,
            lambda claim, truth_core, evidence_view, ev_id, step_ctx, machine, services: (
                SimpleNamespace(support="absent"), machine, []
            ),
        )
        claim = SimpleNamespace(id="c1")
        truth = TruthCore(truth="T")
        machine = MachineState()

        s1, _, _ = fixture_synth(
            claim, truth, None, "ev1", StepContext(effective_frame=FrameNode(system="sys", namespace="ns", scale="macro", task="predict", regime="standard")), machine, {}
        )
        s2, _, _ = fixture_synth(
            claim, truth, None, "ev1", StepContext(effective_frame=FrameNode(system="sys", namespace="ns", scale="macro", task="predict", regime="standard")), machine, {}
        )

        assert s1.support == "supported"
        assert s2.support == "conflicted"


class TestLicenseComparison:
    """Verify license comparison catches joint-list mismatches."""

    def test_joint_list_compares_all_entries_by_joint_id(self):
        actual = LicenseResult(
            claim_id="c1",
            overall=LicenseOverall(truth="F"),
            joint=[
                JointLicenseEntry(joint_id="j1", anchors=["a1", "a2"], truth="T"),
                JointLicenseEntry(joint_id="j2", anchors=["a2", "a3"], truth="F"),
            ],
        )
        expected = {
            "joint": [
                {"joint_id": "j1", "truth": "T"},
                {"joint_id": "j2", "truth": "T"},
            ]
        }

        mismatches: list[FieldMismatch] = []
        _compare_license("sessions[0].steps[0].claims.c1.license", expected, actual, mismatches)

        assert any(m.path.endswith("joint[j2].truth") for m in mismatches)
