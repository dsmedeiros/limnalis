"""Stable public API for Limnalis transport chain extensions.

Re-exports transport execution helpers, degradation/completion policy
executors from the runtime layer, plus AST model types for transport
plans and policies, and the transport trace type from conformance.
"""

from __future__ import annotations

from ..runtime.builtins import (
    execute_transport_chain,
    execute_transport_with_degradation_policy,
    validate_claim_map_result,
    apply_destination_completion_policy,
)
from ..runtime.models import TransportChainResult
from ..models.ast import (
    TransportHop,
    TransportPlan,
    DegradationPolicyNode,
    DestinationCompletionPolicy,
)
from ..models.conformance import TransportTrace

__all__ = [
    # Execution helpers
    "execute_transport_chain",
    "execute_transport_with_degradation_policy",
    "validate_claim_map_result",
    "apply_destination_completion_policy",
    # Result types
    "TransportChainResult",
    # AST model types
    "TransportHop",
    "TransportPlan",
    "DegradationPolicyNode",
    "DestinationCompletionPolicy",
    # Trace types
    "TransportTrace",
]
