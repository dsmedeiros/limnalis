"""Limnalis runtime execution scaffolding and step runner."""

from .builtins import (  # noqa: F401 — public summary API
    SummaryPolicyProtocol,
    PassthroughNormativePolicy,
    SeverityMaxPolicy,
    MajorityVotePolicy,
    execute_summary,
    get_builtin_summary_policies,
    run_summaries,
    # T4: Evidence inference layer
    EvidenceInferencePolicyProtocol,
    TransitivityInferencePolicy,
    build_evidence_view_with_inference,
    get_evidence_view_combined,
    get_builtin_inference_policies,
    # T4: Stronger adequacy execution
    execute_adequacy_with_basis,
    aggregate_contested_adequacy,
    detect_basis_circularity,
)
