"""Limnalis runtime execution scaffolding and step runner."""

from .builtins import (  # noqa: F401 — public summary API
    SummaryPolicyProtocol,
    PassthroughNormativePolicy,
    SeverityMaxPolicy,
    MajorityVotePolicy,
    execute_summary,
    get_builtin_summary_policies,
    run_summaries,
)
