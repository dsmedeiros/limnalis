"""Tests for M6B CLI commands: summarize and list-summary-policies."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from limnalis.cli import main
from limnalis.models.conformance import SummaryResult
from limnalis.runtime.models import EvalNode
from limnalis.runtime.runner import BundleResult, SessionResult, StepResult

ROOT = Path(__file__).resolve().parents[1]
MINIMAL_BUNDLE = str(ROOT / "examples" / "minimal_bundle.lmn")


class TestSummarizeCommand:
    def test_summarize_command_runs(self, capsys) -> None:
        """Run summarize on minimal_bundle.lmn with default policy, verify exit code 0."""
        code = main(["summarize", MINIMAL_BUNDLE])
        assert code == 0

    def test_summarize_command_json_output(self, capsys) -> None:
        """Run with --json, verify output is valid JSON containing expected keys."""
        code = main(["summarize", "--json", MINIMAL_BUNDLE])
        captured = capsys.readouterr()

        assert code == 0
        payload = json.loads(captured.out)
        assert "policy_id" in payload
        assert "scope" in payload
        assert "normative" in payload

    def test_summarize_command_severity_max(self, capsys) -> None:
        """Run with --policy severity_max, verify exit code 0."""
        code = main(["summarize", "--policy", "severity_max", MINIMAL_BUNDLE])
        assert code == 0

    def test_summarize_command_invalid_file(self, tmp_path: Path, capsys) -> None:
        """Run with nonexistent file, verify non-zero exit code."""
        nonexistent = str(tmp_path / "nonexistent.lmn")
        code = main(["summarize", nonexistent])
        assert code != 0

    def test_summarize_command_invalid_policy(self, capsys) -> None:
        """Run with --policy nonexistent, verify non-zero exit code."""
        code = main(["summarize", "--policy", "nonexistent", MINIMAL_BUNDLE])
        assert code != 0

    def test_summarize_flattens_bundle_result_for_policy(self, monkeypatch) -> None:
        """Summary execution receives step-level aggregates, not the bundle envelope."""
        import limnalis.cli._existing as cli_mod
        import limnalis.runtime as runtime_mod
        import limnalis.runtime.runner as runner_mod

        def fake_normalize_surface_file(path, validate_schema=True):
            return SimpleNamespace(canonical_ast=object())

        def fake_run_bundle(bundle, sessions, env):
            return BundleResult(
                bundle_id="b1",
                session_results=[
                    SessionResult(
                        session_id="s1",
                        step_results=[
                            StepResult(
                                step_id="step0",
                                per_claim_aggregates={"c1": EvalNode(truth="T", reason="ok")},
                                per_block_aggregates={"b1": EvalNode(truth="T", reason="ok")},
                            )
                        ],
                    )
                ],
            )

        def fake_execute_summary(request, eval_results, services, policies):
            assert "per_claim_aggregates" in eval_results
            assert eval_results["per_claim_aggregates"]
            return SummaryResult(policy_id=request.policy_id, scope=request.scope, summary_truth="T")

        monkeypatch.setattr(cli_mod, "normalize_surface_file", fake_normalize_surface_file)
        monkeypatch.setattr(runner_mod, "run_bundle", fake_run_bundle)
        monkeypatch.setattr(runtime_mod, "execute_summary", fake_execute_summary)
        monkeypatch.setattr(runtime_mod, "get_builtin_summary_policies", lambda: {"passthrough_normative": object()})

        code = main(["summarize", "dummy.lmn"])
        assert code == 0

    def test_summarize_populates_block_target_ids_from_eval_payload(self, monkeypatch) -> None:
        """Block scope without explicit target IDs should auto-select available blocks."""
        import limnalis.cli._existing as cli_mod
        import limnalis.runtime as runtime_mod
        import limnalis.runtime.runner as runner_mod

        def fake_normalize_surface_file(path, validate_schema=True):
            return SimpleNamespace(canonical_ast=object())

        def fake_run_bundle(bundle, sessions, env):
            return BundleResult(
                bundle_id="b1",
                session_results=[
                    SessionResult(
                        session_id="s1",
                        step_results=[
                            StepResult(
                                step_id="step0",
                                per_block_aggregates={"block-1": EvalNode(truth="T", reason="ok")},
                            )
                        ],
                    )
                ],
            )

        def fake_execute_summary(request, eval_results, services, policies):
            assert request.scope == "block"
            assert request.target_ids == ["block-1"]
            return SummaryResult(policy_id=request.policy_id, scope=request.scope, summary_truth="T")

        monkeypatch.setattr(cli_mod, "normalize_surface_file", fake_normalize_surface_file)
        monkeypatch.setattr(runner_mod, "run_bundle", fake_run_bundle)
        monkeypatch.setattr(runtime_mod, "execute_summary", fake_execute_summary)
        monkeypatch.setattr(runtime_mod, "get_builtin_summary_policies", lambda: {"passthrough_normative": object()})

        code = main(["summarize", "--scope", "block", "dummy.lmn"])
        assert code == 0


class TestListSummaryPoliciesCommand:
    def test_list_summary_policies_runs(self, capsys) -> None:
        """Run list-summary-policies, verify exit code 0 and output mentions built-in policies."""
        code = main(["list-summary-policies"])
        captured = capsys.readouterr()

        assert code == 0
        output = captured.out
        assert "passthrough_normative" in output
        assert "severity_max" in output
        assert "majority_vote" in output
