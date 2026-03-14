"""Conformance runner: execute fixture cases through the evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..loader import normalize_surface_text
from ..models.ast import BundleNode
from ..runtime.models import (
    EvalNode,
    EvaluationEnvironment,
    MachineState,
    SessionConfig,
    StepConfig,
    StepContext,
    TruthCore,
)
from ..runtime.runner import BundleResult, PrimitiveSet, run_bundle
from .fixtures import FixtureCase, FixtureCorpus


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class CaseRunResult:
    """Result of running a single fixture case."""

    case_id: str
    bundle_result: BundleResult | None = None
    bundle: BundleNode | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Fake evaluator bindings from fixture expectations
# ---------------------------------------------------------------------------


def _build_truth_map_from_expected(
    case: FixtureCase,
) -> dict[str, dict[str, TruthCore]]:
    """Extract per-claim, per-evaluator truth values from fixture expectations.

    Returns: {claim_id: {evaluator_id: TruthCore}}
    """
    truth_map: dict[str, dict[str, TruthCore]] = {}

    for session_exp in case.expected_sessions():
        for step_exp in session_exp.get("steps", []):
            claims = step_exp.get("claims", {})
            for claim_id, claim_exp in claims.items():
                per_ev = claim_exp.get("per_evaluator", {})
                if not per_ev:
                    continue
                truth_map[claim_id] = {}
                for ev_id, ev_exp in per_ev.items():
                    if isinstance(ev_exp, dict):
                        truth_map[claim_id][ev_id] = TruthCore(
                            truth=ev_exp.get("truth", "N"),
                            reason=ev_exp.get("reason"),
                        )
                    elif isinstance(ev_exp, str):
                        # Simple truth value string
                        truth_map[claim_id][ev_id] = TruthCore(truth=ev_exp)

    return truth_map


def _build_fixture_eval_expr(
    truth_map: dict[str, dict[str, TruthCore]],
) -> Any:
    """Build a fixture-backed eval_expr function.

    Returns a callable with the signature:
        (claim, ev_id, step_ctx, machine, services) -> (TruthCore, MachineState, list)
    """

    def fixture_eval_expr(
        claim: Any,
        ev_id: str,
        step_ctx: StepContext | None,
        machine: MachineState,
        services: dict[str, Any] | None = None,
    ) -> tuple[TruthCore, MachineState, list[dict[str, Any]]]:
        claim_id = claim.id if hasattr(claim, "id") else str(claim)
        ev_truths = truth_map.get(claim_id, {})
        if ev_id in ev_truths:
            return ev_truths[ev_id], machine, []
        # Default: return N for unknown claim/evaluator combinations
        return TruthCore(truth="N", reason="fixture_not_specified"), machine, []

    return fixture_eval_expr


# ---------------------------------------------------------------------------
# Build default sessions from fixture
# ---------------------------------------------------------------------------


def _build_sessions_from_expected(case: FixtureCase) -> list[SessionConfig]:
    """Build SessionConfig objects from fixture expectations."""
    sessions: list[SessionConfig] = []
    expected_sessions = case.expected_sessions()

    if not expected_sessions:
        # No sessions expected: return a single default session to trigger
        # the runner (which may produce diagnostics)
        return [SessionConfig(id="default", steps=[StepConfig(id="step0")])]

    for sess_exp in expected_sessions:
        steps = []
        for step_exp in sess_exp.get("steps", []):
            steps.append(StepConfig(id=step_exp.get("id", "step0")))
        if not steps:
            steps = [StepConfig(id="step0")]
        sessions.append(SessionConfig(id=sess_exp.get("id", "default"), steps=steps))

    return sessions


# ---------------------------------------------------------------------------
# Run a single case
# ---------------------------------------------------------------------------


def run_case(case: FixtureCase, corpus: FixtureCorpus | None = None) -> CaseRunResult:
    """Run a single fixture case through the evaluator pipeline.

    Parses the fixture source into a BundleNode, builds fixture-backed
    eval_expr bindings from expected results, and runs the evaluator.
    """
    # Parse the surface source into an AST bundle
    try:
        norm_result = normalize_surface_text(case.source, validate_schema=True)
    except Exception as exc:
        return CaseRunResult(case_id=case.id, error=f"Parse/normalize error: {exc}")

    if norm_result.canonical_ast is None:
        return CaseRunResult(
            case_id=case.id, error="Normalization produced no canonical AST"
        )

    bundle = norm_result.canonical_ast

    # Build fixture-backed eval_expr from expected per_evaluator results
    truth_map = _build_truth_map_from_expected(case)
    fixture_eval_expr = _build_fixture_eval_expr(truth_map)

    # Build PrimitiveSet with fixture eval_expr
    primitives = PrimitiveSet(eval_expr=fixture_eval_expr)

    # Build sessions from expected structure
    sessions = _build_sessions_from_expected(case)

    # Build evaluation environment
    env = EvaluationEnvironment()

    # Run the bundle
    try:
        result = run_bundle(bundle, sessions, env, primitives=primitives)
    except Exception as exc:
        return CaseRunResult(
            case_id=case.id,
            bundle=bundle,
            error=f"Runner error: {exc}",
        )

    return CaseRunResult(
        case_id=case.id,
        bundle_result=result,
        bundle=bundle,
    )
