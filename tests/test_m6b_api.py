"""Tests for M6B API re-exports."""

from __future__ import annotations

import pytest


class TestAPISummaryImports:
    def test_api_summary_imports(self):
        """All symbols importable from limnalis.api.summary."""
        from limnalis.api.summary import (
            MajorityVotePolicy,
            PassthroughNormativePolicy,
            SeverityMaxPolicy,
            SummaryPolicyProtocol,
            SummaryRequest,
            SummaryResult,
            execute_summary,
            get_builtin_summary_policies,
            run_summaries,
        )

        # Verify they are not None
        assert SummaryPolicyProtocol is not None
        assert PassthroughNormativePolicy is not None
        assert SeverityMaxPolicy is not None
        assert MajorityVotePolicy is not None
        assert execute_summary is not None
        assert run_summaries is not None
        assert get_builtin_summary_policies is not None
        assert SummaryRequest is not None
        assert SummaryResult is not None


class TestAPIEvidenceImports:
    def test_api_evidence_imports(self):
        """All symbols importable from limnalis.api.evidence."""
        from limnalis.api.evidence import (
            EvidenceInferencePolicyNode,
            EvidenceInferencePolicyProtocol,
            InferredEvidenceRelation,
            TransitivityInferencePolicy,
            build_evidence_view_with_inference,
            get_builtin_inference_policies,
            get_evidence_view_combined,
        )

        assert EvidenceInferencePolicyProtocol is not None
        assert TransitivityInferencePolicy is not None
        assert build_evidence_view_with_inference is not None
        assert get_evidence_view_combined is not None
        assert get_builtin_inference_policies is not None
        assert InferredEvidenceRelation is not None
        assert EvidenceInferencePolicyNode is not None


class TestAPIAdequacyImports:
    def test_api_adequacy_imports(self):
        """All symbols importable from limnalis.api.adequacy."""
        from limnalis.api.adequacy import (
            AdequacyExecutionTrace,
            BasisResolutionEntry,
            aggregate_contested_adequacy,
            detect_basis_circularity,
            execute_adequacy_with_basis,
        )

        assert execute_adequacy_with_basis is not None
        assert aggregate_contested_adequacy is not None
        assert detect_basis_circularity is not None
        assert BasisResolutionEntry is not None
        assert AdequacyExecutionTrace is not None


class TestAPITransportImports:
    def test_api_transport_imports(self):
        """All symbols importable from limnalis.api.transport."""
        from limnalis.api.transport import (
            DegradationPolicyNode,
            DestinationCompletionPolicy,
            TransportChainResult,
            TransportHop,
            TransportPlan,
            TransportTrace,
            apply_destination_completion_policy,
            execute_transport_chain,
            execute_transport_with_degradation_policy,
            validate_claim_map_result,
        )

        assert execute_transport_chain is not None
        assert execute_transport_with_degradation_policy is not None
        assert validate_claim_map_result is not None
        assert apply_destination_completion_policy is not None
        assert TransportChainResult is not None
        assert TransportHop is not None
        assert TransportPlan is not None
        assert DegradationPolicyNode is not None
        assert DestinationCompletionPolicy is not None
        assert TransportTrace is not None


class TestAPIModulesInInit:
    def test_api_modules_in_init(self):
        """summary, evidence, adequacy, transport in api.__all__."""
        import limnalis.api as api

        assert "summary" in api.__all__
        assert "evidence" in api.__all__
        assert "adequacy" in api.__all__
        assert "transport" in api.__all__
