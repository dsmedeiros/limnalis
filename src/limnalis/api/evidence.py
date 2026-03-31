"""Stable public API for Limnalis evidence inference layer.

Re-exports evidence inference protocols, built-in policies, and view
builders from the runtime layer, plus the AST model types for inferred
evidence relations and policy nodes.
"""

from __future__ import annotations

from ..runtime import (
    EvidenceInferencePolicyProtocol,
    TransitivityInferencePolicy,
    build_evidence_view_with_inference,
    get_evidence_view_combined,
    get_builtin_inference_policies,
)
from ..models.ast import InferredEvidenceRelation, EvidenceInferencePolicyNode

__all__ = [
    # Protocol
    "EvidenceInferencePolicyProtocol",
    # Built-in policies
    "TransitivityInferencePolicy",
    # View builders
    "build_evidence_view_with_inference",
    "get_evidence_view_combined",
    "get_builtin_inference_policies",
    # AST model types
    "InferredEvidenceRelation",
    "EvidenceInferencePolicyNode",
]
