"""Grid domain example plugin pack for Limnalis.

Demonstrates how to implement evaluator bindings for a power grid
contingency analysis domain. Sufficient to run the B1 fixture case.

This is an example implementation -- not production-ready.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Evaluator binding handlers
# ---------------------------------------------------------------------------


def grid_predicate_handler(
    expr: Any, claim: Any, step_ctx: Any, machine_state: Any
) -> Any:
    """Evaluate grid predicate expressions.

    For the B1 case:
    - overload(line_B) -> T (line B is overloaded)
    """
    from limnalis.api.results import TruthCore

    return TruthCore(
        truth="T",
        reason="grid_predicate_match",
        confidence=1.0,
        provenance=["grid_v1"],
    )


def grid_causal_handler(
    expr: Any, claim: Any, step_ctx: Any, machine_state: Any
) -> Any:
    """Evaluate grid causal expressions.

    For the B1 case:
    - overload(line_B) =>[obs] voltage_drop(bus_7) -> B[source_conflict]
      Evidence conflict between SCADA and PMU measurements.
    """
    from limnalis.api.results import TruthCore

    return TruthCore(
        truth="B",
        reason="source_conflict",
        confidence=0.72,
        provenance=["grid_v1", "scada_pmu_conflict"],
    )


def grid_emergence_handler(
    expr: Any, claim: Any, step_ctx: Any, machine_state: Any
) -> Any:
    """Evaluate grid emergence expressions.

    For the B1 case:
    - voltage_instability EMRG... -> T (emergence detected)
    """
    from limnalis.api.results import TruthCore

    return TruthCore(
        truth="T",
        reason="emergence_detected",
        confidence=0.85,
        provenance=["grid_v1", "margin_analysis"],
    )


# ---------------------------------------------------------------------------
# Support policy handler
# ---------------------------------------------------------------------------


def grid_support_policy(
    claim: Any,
    truth_core: Any,
    evidence_view: Any,
    evaluator_id: str,
    step_ctx: Any,
    machine_state: Any,
) -> Any:
    """Grid domain support synthesis.

    Maps evidence completeness and conflict to support levels:
    - No evidence refs -> absent
    - Evidence conflict > 0.5 -> conflicted
    - Incomplete evidence -> partial
    - Complete evidence -> supported
    """
    from limnalis.api.results import SupportResult

    refs = getattr(claim, "refs", None) or []
    if not refs:
        return SupportResult(support="absent", provenance=[evaluator_id])

    if (
        evidence_view
        and evidence_view.cross_conflict_score is not None
        and evidence_view.cross_conflict_score > 0.5
    ):
        return SupportResult(
            support="conflicted", provenance=[evaluator_id, "evidence_conflict"]
        )

    completeness = (
        evidence_view.completeness_summary if evidence_view else None
    )
    if completeness is not None and completeness < 0.95:
        return SupportResult(support="partial", provenance=[evaluator_id])

    return SupportResult(support="supported", provenance=[evaluator_id])


# ---------------------------------------------------------------------------
# Adequacy handler
# ---------------------------------------------------------------------------


def grid_adequacy_check(assessment: Any) -> float:
    """Grid adequacy method: returns the assessment's declared score."""
    if hasattr(assessment, "score") and assessment.score is not None:
        return float(assessment.score)
    return 0.0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_grid_plugins(registry: Any) -> None:
    """Register all grid domain plugins into the given registry.

    Registers:
    - Evaluator bindings for ev_grid (predicate, causal, emergence)
    - Grid support policy
    - Grid adequacy check methods
    """
    from limnalis.plugins import ADEQUACY_METHOD, EVALUATOR_BINDING, EVIDENCE_POLICY

    # Evaluator bindings: "evaluator_id::expr_type" format
    registry.register(
        EVALUATOR_BINDING,
        "ev_grid::predicate",
        grid_predicate_handler,
        description="Grid predicate evaluation (overload, voltage, etc.)",
    )
    registry.register(
        EVALUATOR_BINDING,
        "ev_grid::causal",
        grid_causal_handler,
        description="Grid causal evaluation (observational mode)",
    )
    registry.register(
        EVALUATOR_BINDING,
        "ev_grid::emergence",
        grid_emergence_handler,
        description="Grid emergence evaluation (voltage instability)",
    )

    # Support policy
    registry.register(
        EVIDENCE_POLICY,
        "test://eval/grid_v1",
        grid_support_policy,
        description="Grid evidence-based support synthesis",
    )

    # Adequacy methods
    for method_uri in [
        "sim://checks/n1_pred",
        "sim://checks/n1_ctrl",
        "audit://postmortem/n1_expl",
    ]:
        registry.register(
            ADEQUACY_METHOD,
            method_uri,
            grid_adequacy_check,
            description=f"Grid adequacy check: {method_uri}",
        )
