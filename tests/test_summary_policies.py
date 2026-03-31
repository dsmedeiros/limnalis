"""Tests for the summary policy framework (T3 functions)."""

from __future__ import annotations

import copy

import pytest

from limnalis.models.conformance import SummaryRequest, SummaryResult
from limnalis.runtime.builtins import (
    MajorityVotePolicy,
    PassthroughNormativePolicy,
    SeverityMaxPolicy,
    execute_summary,
    get_builtin_summary_policies,
    run_summaries,
)
from limnalis.runtime.models import EvalNode


# ===================================================================
# Helpers
# ===================================================================


def _block_results(claims: list[str], block_id: str = "blk1"):
    """Create a minimal block_results entry."""
    return {"block_id": block_id, "claims": claims}


def _eval_results(
    per_claim: dict[str, str] | None = None,
    per_block: dict[str, str] | None = None,
    block_results_list: list[dict] | None = None,
) -> dict:
    """Build a minimal eval_results dict.

    per_claim/per_block map id -> truth value string.
    """
    result: dict = {}
    if per_claim is not None:
        result["per_claim_aggregates"] = {
            cid: EvalNode(truth=t) for cid, t in per_claim.items()
        }
    if per_block is not None:
        result["per_block_aggregates"] = {
            bid: EvalNode(truth=t) for bid, t in per_block.items()
        }
    if block_results_list is not None:
        result["block_results"] = block_results_list
    return result


# ===================================================================
# PassthroughNormativePolicy
# ===================================================================


class TestPassthroughPolicy:
    def test_passthrough_block_scope(self):
        """Passthrough policy on block scope, verify returns block aggregate."""
        policy = PassthroughNormativePolicy()
        request = SummaryRequest(
            policy_id="passthrough_normative",
            scope="block",
            target_ids=["blk1"],
        )
        er = _eval_results(per_block={"blk1": "T"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "T"
        assert result.scope == "block"
        assert result.normative is False

    def test_passthrough_block_scope_aggregates_multiple_targets(self):
        """Block scope should aggregate across all targeted blocks, not just first match."""
        policy = PassthroughNormativePolicy()
        request = SummaryRequest(
            policy_id="passthrough_normative",
            scope="block",
            target_ids=["blk1", "blk2"],
        )
        er = _eval_results(per_block={"blk1": "T", "blk2": "F"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "F"
        assert result.detail["block_count"] == 2

    def test_passthrough_bundle_scope(self):
        """Passthrough on bundle scope, verify worst-of-blocks."""
        policy = PassthroughNormativePolicy()
        request = SummaryRequest(
            policy_id="passthrough_normative",
            scope="bundle",
        )
        er = _eval_results(per_block={"blk1": "T", "blk2": "F"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "F"

    def test_passthrough_claim_collection(self):
        """Passthrough on specific claims."""
        policy = PassthroughNormativePolicy()
        request = SummaryRequest(
            policy_id="passthrough_normative",
            scope="claim_collection",
            target_ids=["c1", "c2"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "B", "c3": "F"})

        result = policy.summarize(request, er, {})

        # Worst of c1=T and c2=B is B
        assert result.summary_truth == "B"


# ===================================================================
# SeverityMaxPolicy
# ===================================================================


class TestSeverityMaxPolicy:
    def test_severity_max_all_true(self):
        """All T truths, returns T."""
        policy = SeverityMaxPolicy()
        request = SummaryRequest(
            policy_id="severity_max",
            scope="claim_collection",
            target_ids=["c1", "c2"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "T"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "T"

    def test_severity_max_mixed(self):
        """Mix of T, F, N, returns F (worst)."""
        policy = SeverityMaxPolicy()
        request = SummaryRequest(
            policy_id="severity_max",
            scope="claim_collection",
            target_ids=["c1", "c2", "c3"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "F", "c3": "N"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "F"

    def test_severity_max_with_both(self):
        """Includes B, verify B < F ordering."""
        policy = SeverityMaxPolicy()
        request = SummaryRequest(
            policy_id="severity_max",
            scope="claim_collection",
            target_ids=["c1", "c2", "c3"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "B", "c3": "N"})

        result = policy.summarize(request, er, {})

        # B is worse than N and T but better than F
        assert result.summary_truth == "B"


# ===================================================================
# MajorityVotePolicy
# ===================================================================


class TestMajorityVotePolicy:
    def test_majority_vote_clear_winner(self):
        """3 T, 1 F, returns T."""
        policy = MajorityVotePolicy()
        request = SummaryRequest(
            policy_id="majority_vote",
            scope="claim_collection",
            target_ids=["c1", "c2", "c3", "c4"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "T", "c3": "T", "c4": "F"})

        result = policy.summarize(request, er, {})

        assert result.summary_truth == "T"

    def test_majority_vote_tie_breaking(self):
        """2 T, 2 F, tie broken by severity -> F."""
        policy = MajorityVotePolicy()
        request = SummaryRequest(
            policy_id="majority_vote",
            scope="claim_collection",
            target_ids=["c1", "c2", "c3", "c4"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "T", "c3": "F", "c4": "F"})

        result = policy.summarize(request, er, {})

        # Tie: T=2, F=2, severity breaks tie -> F wins
        assert result.summary_truth == "F"

    def test_majority_vote_detail_includes_counts(self):
        """Verify detail dict has vote counts."""
        policy = MajorityVotePolicy()
        request = SummaryRequest(
            policy_id="majority_vote",
            scope="claim_collection",
            target_ids=["c1", "c2"],
        )
        er = _eval_results(per_claim={"c1": "T", "c2": "F"})

        result = policy.summarize(request, er, {})

        assert "votes" in result.detail
        votes = result.detail["votes"]
        assert votes["T"] == 1
        assert votes["F"] == 1


# ===================================================================
# execute_summary / run_summaries
# ===================================================================


class TestSummaryExecution:
    def test_execute_summary_missing_policy(self):
        """Missing policy, verify diagnostic."""
        request = SummaryRequest(
            policy_id="nonexistent",
            scope="block",
        )
        er = _eval_results(per_block={"blk1": "T"})
        policies = get_builtin_summary_policies()

        result = execute_summary(request, er, {}, policies)

        assert len(result.diagnostics) == 1
        assert result.diagnostics[0]["code"] == "summary_policy_not_found"

    def test_run_summaries_batch(self):
        """Multiple requests, verify batch execution."""
        requests = [
            SummaryRequest(policy_id="severity_max", scope="bundle"),
            SummaryRequest(
                policy_id="majority_vote",
                scope="claim_collection",
                target_ids=["c1"],
            ),
        ]
        er = _eval_results(
            per_claim={"c1": "T"},
            per_block={"blk1": "F"},
        )

        results = run_summaries(requests, er, {})

        assert len(results) == 2
        assert all(isinstance(r, SummaryResult) for r in results)

    def test_summary_normative_false(self):
        """All results have normative=False."""
        requests = [
            SummaryRequest(policy_id="passthrough_normative", scope="bundle"),
            SummaryRequest(policy_id="severity_max", scope="bundle"),
            SummaryRequest(policy_id="majority_vote", scope="bundle"),
        ]
        er = _eval_results(per_block={"blk1": "T"})

        results = run_summaries(requests, er, {})

        for r in results:
            assert r.normative is False

    def test_summary_does_not_mutate_eval_results(self):
        """Verify eval_results unchanged after summary."""
        er = _eval_results(
            per_claim={"c1": "T", "c2": "F"},
            per_block={"blk1": "T"},
        )
        original = copy.deepcopy(er)

        requests = [
            SummaryRequest(policy_id="severity_max", scope="bundle"),
        ]
        run_summaries(requests, er, {})

        # per_block_aggregates should be unchanged
        for bid in original.get("per_block_aggregates", {}):
            assert er["per_block_aggregates"][bid].truth == original["per_block_aggregates"][bid].truth

    def test_get_builtin_summary_policies(self):
        """Registry returns all 3 policies."""
        policies = get_builtin_summary_policies()

        assert "passthrough_normative" in policies
        assert "severity_max" in policies
        assert "majority_vote" in policies
        assert len(policies) == 3
