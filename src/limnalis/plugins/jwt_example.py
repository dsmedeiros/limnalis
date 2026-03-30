"""JWT/auth domain example plugin pack for Limnalis.

Demonstrates how to implement evaluator bindings for a JWT gateway
authorization domain. Sufficient to run the B2 fixture case.

Shows:
- JudgedExpr handling with policy-bound criterion binding
- Evidence policy override for support synthesis
- Anchor adequacy with task-specific licensing
- Distinction between claim truth (all T) and license result (revocation F)

This is an example implementation -- not production-ready.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Evaluator binding handlers
# ---------------------------------------------------------------------------


def jwt_predicate_handler(
    expr: Any, claim: Any, step_ctx: Any, machine_state: Any
) -> Any:
    """Evaluate JWT predicate expressions.

    For the B2 case, all predicates evaluate to T:
    - sig_valid(tok_A) -> T
    - token_not_expired(tok_A) -> T
    - revocation_immediate(tok_A) -> T
    """
    from limnalis.api.results import TruthCore

    return TruthCore(
        truth="T",
        reason="jwt_check_passed",
        confidence=1.0,
        provenance=["jwt_gateway_v1"],
    )


def jwt_judged_handler(
    expr: Any, claim: Any, step_ctx: Any, machine_state: Any
) -> Any:
    """Evaluate JWT judged expressions (policy-bound criterion).

    For the B2 case:
    - access_allowed(tok_A) judged_by auth_access_v3 -> T
    """
    from limnalis.api.results import TruthCore

    return TruthCore(
        truth="T",
        reason="policy_satisfied",
        confidence=1.0,
        provenance=["jwt_gateway_v1", "auth_access_v3"],
    )


# ---------------------------------------------------------------------------
# Support policy handler
# ---------------------------------------------------------------------------


def jwt_support_policy(
    claim: Any,
    truth_core: Any,
    evidence_view: Any,
    evaluator_id: str,
    step_ctx: Any,
    machine_state: Any,
) -> Any:
    """JWT domain support synthesis per evidence policy.

    Maps evidence quality to support levels:
    - Declaration -> inapplicable
    - All evidence complete (>=0.95) and low conflict -> supported
    - Any evidence incomplete or has conflict -> partial
    - No evidence -> absent
    """
    from limnalis.api.results import SupportResult

    # Declarations get inapplicable support
    claim_kind = getattr(claim, "kind", "")
    if claim_kind == "declaration":
        return SupportResult(support="inapplicable", provenance=[evaluator_id])

    refs = getattr(claim, "refs", None) or []
    if not refs:
        return SupportResult(support="absent", provenance=[evaluator_id])

    # Check evidence quality from the evidence view
    if evidence_view is not None:
        cross_conflict = getattr(evidence_view, "cross_conflict_score", None)
        if cross_conflict is not None and cross_conflict > 0.05:
            return SupportResult(
                support="partial",
                provenance=[evaluator_id, "evidence_conflict"],
            )

        completeness = getattr(evidence_view, "completeness_summary", None)
        if isinstance(completeness, dict):
            min_c = min(completeness.values()) if completeness else 1.0
            if min_c < 0.95:
                return SupportResult(
                    support="partial",
                    provenance=[evaluator_id, "incomplete_evidence"],
                )
        elif isinstance(completeness, (int, float)):
            if completeness < 0.95:
                return SupportResult(
                    support="partial",
                    provenance=[evaluator_id, "incomplete_evidence"],
                )

    return SupportResult(support="supported", provenance=[evaluator_id])


# ---------------------------------------------------------------------------
# Adequacy handler
# ---------------------------------------------------------------------------


def jwt_adequacy_check(assessment: Any) -> float:
    """JWT adequacy method: returns the assessment's declared score."""
    if hasattr(assessment, "score") and assessment.score is not None:
        score = assessment.score
        # score may be the literal "N" for not-applicable
        if isinstance(score, str):
            return 0.0
        return float(score)
    return 0.0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_jwt_plugins(registry: Any) -> None:
    """Register all JWT domain plugins into the given registry.

    Registers:
    - Evaluator bindings for ev_gateway (predicate, judged)
    - JWT support policy
    - JWT adequacy check methods
    """
    from limnalis.plugins import ADEQUACY_METHOD, EVALUATOR_BINDING, EVIDENCE_POLICY

    # Evaluator bindings
    registry.register(
        EVALUATOR_BINDING,
        "ev_gateway::predicate",
        jwt_predicate_handler,
        description="JWT predicate evaluation (sig_valid, token_not_expired, etc.)",
    )
    registry.register(
        EVALUATOR_BINDING,
        "ev_gateway::judged",
        jwt_judged_handler,
        description="JWT judged expression evaluation (policy-bound criterion)",
    )

    # Support policy
    registry.register(
        EVIDENCE_POLICY,
        "test://policy/jwt_support_v1",
        jwt_support_policy,
        description="JWT evidence-based support synthesis policy",
    )

    # Adequacy methods
    for method_uri in [
        "test://method/stateless_access",
        "test://method/stateless_revocation",
        "test://method/clock_access",
        "test://method/jwt_joint_access",
    ]:
        registry.register(
            ADEQUACY_METHOD,
            method_uri,
            jwt_adequacy_check,
            description=f"JWT adequacy check: {method_uri}",
        )
