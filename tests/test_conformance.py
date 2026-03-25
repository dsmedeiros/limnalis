"""Tests for corpus conformance execution.

Each required fixture case runs end-to-end through the conformance harness
(parse -> normalize -> run -> compare) and must produce zero mismatches.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

import limnalis.conformance.runner as conformance_runner_mod
from limnalis.cli import main
from limnalis.conformance.compare import (
    FieldMismatch,
    _compare_adequacy,
    _compare_license,
    compare_case,
)
from limnalis.conformance.fixtures import load_corpus_from_default
from limnalis.models.ast import FrameNode, FramePatternNode, TimeCtxNode
from limnalis.conformance.runner import (
    _build_fixture_eval_expr,
    _build_fixture_synthesize_support,
    _build_per_step_support_maps,
    _build_transport_queries_from_case,
    _build_sessions_from_case,
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

    def test_conformance_run_default_runs_full_corpus(self, capsys):
        code = main(["conformance", "run"])
        captured = capsys.readouterr()
        assert code == 1
        assert "A4" in captured.out
        assert "A12" in captured.out
        assert "B2" in captured.out


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


class TestConformanceParseFailures:
    """Verify parse/normalize failures remain comparable in conformance output."""

    def test_run_case_parse_error_returns_bundle_result_for_comparison(self):
        case = SimpleNamespace(
            id="BAD_PARSE",
            source="<<< definitely not limnalis surface text >>>",
            expected={"diagnostics": [{"code": "parse_normalize_error", "severity": "error"}]},
        )

        run_result = run_case(case, None)

        assert run_result.error is None
        assert run_result.bundle_result is not None

        comparison = compare_case(case, run_result)
        assert comparison.passed

    def test_run_case_schema_validation_fallback_preserves_specific_diagnostic(
        self, monkeypatch
    ):
        calls = {"n": 0}

        fake_bundle = SimpleNamespace(
            resolutionPolicy=SimpleNamespace(id="rp0", kind="single")
        )

        def fake_normalize(source, validate_schema=True):
            calls["n"] += 1
            if validate_schema:
                raise ValueError("baseline-mode-invalid")
            return SimpleNamespace(canonical_ast=fake_bundle)

        monkeypatch.setattr(conformance_runner_mod, "normalize_surface_text", fake_normalize)
        monkeypatch.setattr(conformance_runner_mod, "_build_sessions_from_case", lambda case: [])
        monkeypatch.setattr(
            conformance_runner_mod, "_extract_extra_resolution_policies",
            lambda source, primary_policy_id: {},
        )
        monkeypatch.setattr(
            conformance_runner_mod, "run_bundle",
            lambda *args, **kwargs: SimpleNamespace(
                bundle_id="X",
                session_results=[],
                diagnostics=[],
            ),
        )

        case = SimpleNamespace(
            id="X",
            source="dummy source",
            expected={},
            environment={},
            expected_sessions=lambda: [],
        )

        run_result = run_case(case, None)

        assert run_result.error is None
        assert run_result.bundle_result is not None
        assert calls["n"] == 2
        assert any(
            d.get("code") == "normalize_schema_validation_failed"
            for d in run_result.bundle_result.diagnostics
        )


class TestConformanceCountStrictness:
    """Verify compare_case enforces exact session/step counts."""

    def test_compare_case_flags_extra_sessions(self):
        case = SimpleNamespace(id="X", expected={"sessions": [{"steps": []}]})
        run_result = SimpleNamespace(
            case_id="X",
            error=None,
            bundle_result=SimpleNamespace(
                session_results=[
                    SimpleNamespace(step_results=[], diagnostics=[], baseline_states={}, adequacy_store={}),
                    SimpleNamespace(step_results=[], diagnostics=[], baseline_states={}, adequacy_store={}),
                ],
                diagnostics=[],
            ),
        )

        comparison = compare_case(case, run_result)

        assert not comparison.passed
        assert any(m.path == "sessions.length" for m in comparison.mismatches)

    def test_compare_case_flags_extra_steps_within_session(self):
        case = SimpleNamespace(
            id="Y",
            expected={"sessions": [{"steps": [{"claims": {}, "blocks": {}, "transports": {}}]}]},
        )
        run_result = SimpleNamespace(
            case_id="Y",
            error=None,
            bundle_result=SimpleNamespace(
                session_results=[
                    SimpleNamespace(
                        step_results=[
                            SimpleNamespace(
                                claim_results=[], block_results=[], transport_results={}, diagnostics=[]
                            ),
                            SimpleNamespace(
                                claim_results=[], block_results=[], transport_results={}, diagnostics=[]
                            ),
                        ],
                        diagnostics=[],
                        baseline_states={},
                        adequacy_store={},
                    )
                ],
                diagnostics=[],
            ),
        )

        comparison = compare_case(case, run_result)

        assert not comparison.passed
        assert any(m.path == "sessions[0].steps.length" for m in comparison.mismatches)


class TestConformanceSessionBuilding:
    """Verify environment session parsing preserves step frame overrides."""

    def test_build_sessions_from_environment_parses_step_frame_override(self):
        case = SimpleNamespace(
            environment={
                "sessions": [
                    {
                        "id": "s1",
                        "steps": [
                            {
                                "id": "step0",
                                "frame_override": {
                                    "node": "FramePattern",
                                    "facets": {"task": "diagnose", "regime": "counterfactual"},
                                },
                            }
                        ],
                    }
                ]
            },
            expected_sessions=lambda: [],
        )

        sessions = _build_sessions_from_case(case)

        assert len(sessions) == 1
        step = sessions[0].steps[0]
        assert isinstance(step.frame_override, FramePatternNode)
        assert step.frame_override.facets.task == "diagnose"
        assert step.frame_override.facets.regime == "counterfactual"

    def test_build_sessions_from_environment_parses_session_base_frame_and_time(self):
        case = SimpleNamespace(
            environment={
                "sessions": [
                    {
                        "id": "s1",
                        "base_frame": {
                            "node": "FramePattern",
                            "facets": {"task": "diagnose", "regime": "counterfactual"},
                        },
                        "base_time": {"kind": "point", "t": "2025-01-01T00:00:00Z"},
                        "steps": [{"id": "step0"}],
                    }
                ]
            },
            expected_sessions=lambda: [],
        )

        sessions = _build_sessions_from_case(case)

        assert len(sessions) == 1
        session = sessions[0]
        assert isinstance(session.base_frame, FramePatternNode)
        assert session.base_frame.facets.task == "diagnose"
        assert isinstance(session.base_time, TimeCtxNode)
        assert session.base_time.t == "2025-01-01T00:00:00Z"


class TestConformanceStepIndexing:
    """Verify fixture eval indexing can advance independent of callbacks."""

    def test_fixture_eval_expr_uses_runner_injected_step_index(self):
        per_step_truth_maps = [
            {"c1": {"ev1": TruthCore(truth="T")}},
            {},  # step with no evaluable claims / no eval callback
            {"c1": {"ev1": TruthCore(truth="F")}},
        ]
        fixture_eval = _build_fixture_eval_expr(per_step_truth_maps)
        claim = SimpleNamespace(id="c1")
        step_ctx = StepContext(effective_frame=FrameNode(system="sys", namespace="ns", scale="macro", task="predict", regime="standard"))
        machine = MachineState()

        tc0, _, _ = fixture_eval(claim, "ev1", step_ctx, machine, {"__fixture_step_index__": 0})
        tc2, _, _ = fixture_eval(claim, "ev1", step_ctx, machine, {"__fixture_step_index__": 2})

        assert tc0.truth == "T"
        assert tc2.truth == "F"


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


class TestConformanceTransportQueries:
    """Verify transport query extraction respects step-level scoping."""

    def test_build_transport_queries_includes_step_scope_marker(self):
        case = SimpleNamespace(
            environment={
                "transport_queries": [
                    {"id": "global", "bridgeId": "br1", "claimId": "c_global"}
                ],
                "sessions": [
                    {
                        "id": "s1",
                        "steps": [
                            {
                                "id": "step0",
                                "transport_queries": [
                                    {"id": "step0_q", "bridgeId": "br1", "claimId": "c0"}
                                ],
                            },
                            {
                                "id": "step1",
                                "transport_queries": [
                                    {"id": "step1_q", "bridgeId": "br1", "claimId": "c1"}
                                ],
                            },
                        ],
                    }
                ],
            }
        )

        queries = _build_transport_queries_from_case(case)

        assert [q["id"] for q in queries] == ["global", "step0_q", "step1_q"]
        assert "__fixture_step_index__" not in queries[0]
        assert queries[1]["__fixture_step_index__"] == 0
        assert queries[2]["__fixture_step_index__"] == 1


    def test_build_transport_queries_counts_implicit_default_steps(self):
        case = SimpleNamespace(
            environment={
                "sessions": [
                    {"id": "s0", "steps": []},
                    {
                        "id": "s1",
                        "steps": [
                            {
                                "id": "step0",
                                "transport_queries": [
                                    {"id": "step_q", "bridgeId": "br1", "claimId": "c1"}
                                ],
                            }
                        ],
                    },
                ]
            }
        )

        queries = _build_transport_queries_from_case(case)

        assert [q["id"] for q in queries] == ["step_q"]
        assert queries[0]["__fixture_step_index__"] == 1



class TestAdequacyComparison:
    """Verify adequacy comparison merges stores across sessions."""

    def test_compare_adequacy_merges_nested_sections_across_sessions(self):
        bundle_result = SimpleNamespace(
            session_results=[
                SimpleNamespace(adequacy_store={"per_assessment": {"aa1": {"truth": "T"}}}),
                SimpleNamespace(adequacy_store={"per_assessment": {"aa2": {"truth": "F"}}}),
            ]
        )
        expected = {
            "aa1": {"truth": "T"},
            "aa2": {"truth": "F"},
        }
        mismatches: list[FieldMismatch] = []

        _compare_adequacy("adequacy_expectations", expected, bundle_result, mismatches)

        assert mismatches == []

    def test_compare_adequacy_preserves_flat_store_entries(self):
        bundle_result = SimpleNamespace(
            session_results=[
                SimpleNamespace(adequacy_store={"aa_flat_1": {"truth": "T"}}),
                SimpleNamespace(adequacy_store={"aa_flat_2": {"truth": "F"}}),
            ]
        )
        expected = {
            "aa_flat_1": {"truth": "T"},
            "aa_flat_2": {"truth": "F"},
        }
        mismatches: list[FieldMismatch] = []

        _compare_adequacy("adequacy_expectations", expected, bundle_result, mismatches)

        assert mismatches == []

    def test_compare_adequacy_preserves_flat_entries_with_nested_sections(self):
        bundle_result = SimpleNamespace(
            session_results=[
                SimpleNamespace(
                    adequacy_store={
                        "per_assessment": {"aa_nested_1": {"truth": "T"}},
                        "aa_flat_1": {"truth": "F"},
                    }
                ),
                SimpleNamespace(
                    adequacy_store={
                        "per_anchor_task": {"at_nested_1": {"truth": "B"}},
                        "aa_flat_2": {"truth": "N"},
                    }
                ),
            ]
        )
        expected = {
            "aa_nested_1": {"truth": "T"},
            "at_nested_1": {"truth": "B"},
            "aa_flat_1": {"truth": "F"},
            "aa_flat_2": {"truth": "N"},
        }
        mismatches: list[FieldMismatch] = []

        _compare_adequacy("adequacy_expectations", expected, bundle_result, mismatches)

        assert mismatches == []


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
