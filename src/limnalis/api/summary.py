"""Stable public API for Limnalis summary policy framework.

Re-exports summary policy protocols, built-in policies, and execution
helpers from the runtime layer, plus the request/result types from the
conformance model.
"""

from __future__ import annotations

from ..runtime import (
    SummaryPolicyProtocol,
    PassthroughNormativePolicy,
    SeverityMaxPolicy,
    MajorityVotePolicy,
    execute_summary,
    run_summaries,
    get_builtin_summary_policies,
)
from ..models.conformance import SummaryRequest, SummaryResult

__all__ = [
    # Protocol
    "SummaryPolicyProtocol",
    # Built-in policies
    "PassthroughNormativePolicy",
    "SeverityMaxPolicy",
    "MajorityVotePolicy",
    # Execution helpers
    "execute_summary",
    "run_summaries",
    "get_builtin_summary_policies",
    # Request/result types
    "SummaryRequest",
    "SummaryResult",
]
