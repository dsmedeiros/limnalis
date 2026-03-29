"""Minimal phase-ordered step runner for the Limnalis abstract machine.

Executes the normative 13-phase evaluation order at step scope, recording
a PrimitiveTraceEvent for each phase.  Non-evaluable NoteExpr claims bypass
eval_expr and support synthesis.

The runner accepts injected primitive implementations via a PrimitiveSet
dataclass.  Stubbed phases that raise NotImplementedError are caught and
recorded as diagnostics rather than crashing the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from ..models.ast import (
    BridgeNode,
    BundleNode,
    ClaimBlockNode,
    ClaimNode,
    EvaluatorNode,
    ResolutionPolicyNode,
)
from .builtins import (
    apply_resolution_policy as _apply_resolution_policy,
    build_evidence_view as _build_evidence_view,
    build_step_context as _build_step_context,
    classify_claim as _classify_claim,
    compose_license as _compose_license,
    eval_expr as _eval_expr,
    evaluate_adequacy_set as _evaluate_adequacy_set,
    execute_transport as _execute_transport,
    fold_block as _fold_block,
    assemble_eval as _assemble_eval,
    resolve_baseline as _resolve_baseline,
    resolve_ref as _resolve_ref,
    synthesize_support as _synthesize_support,
)
from .models import (
    BlockResult,
    ClaimClassification,
    ClaimEvidenceView,
    ClaimResult,
    EvalNode,
    EvaluationEnvironment,
    LicenseResult,
    MachineState,
    PrimitiveTraceEvent,
    SessionConfig,
    StepConfig,
    StepContext,
    SupportResult,
    TransportResult,
    TruthCore,
    sort_diagnostics,
)

Diagnostics = list[dict[str, Any]]


# ---------------------------------------------------------------------------
# PrimitiveSet: injectable primitive implementations
# ---------------------------------------------------------------------------


@dataclass
class PrimitiveSet:
    """Holds the 13 primitive callables with defaults pointing to builtins.

    Stubbed primitives raise NotImplementedError by default; the runner
    catches these and records diagnostics instead of crashing.
    """

    resolve_ref: Callable[..., Any] = _resolve_ref
    build_step_context: Callable[..., StepContext] = _build_step_context
    resolve_baseline: Callable[..., Any] = _resolve_baseline
    evaluate_adequacy_set: Callable[..., Any] = _evaluate_adequacy_set
    compose_license: Callable[..., Any] = _compose_license
    build_evidence_view: Callable[..., Any] = _build_evidence_view
    classify_claim: Callable[..., ClaimClassification] = _classify_claim
    eval_expr: Callable[..., Any] = _eval_expr
    synthesize_support: Callable[..., Any] = _synthesize_support
    assemble_eval: Callable[..., EvalNode] = _assemble_eval
    apply_resolution_policy: Callable[..., EvalNode] = _apply_resolution_policy
    fold_block: Callable[..., Any] = _fold_block
    execute_transport: Callable[..., Any] = _execute_transport


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------


class StepResult(BaseModel):
    """Complete result of executing a single evaluation step."""

    step_id: str
    step_context: StepContext | None = None
    machine_state: MachineState = Field(default_factory=MachineState)
    per_claim_classifications: dict[str, ClaimClassification] = Field(
        default_factory=dict
    )
    per_claim_per_evaluator: dict[str, dict[str, EvalNode]] = Field(
        default_factory=dict
    )
    per_claim_aggregates: dict[str, EvalNode] = Field(default_factory=dict)
    per_claim_licenses: dict[str, LicenseResult] = Field(default_factory=dict)
    per_block_per_evaluator: dict[str, dict[str, EvalNode]] = Field(
        default_factory=dict
    )
    per_block_aggregates: dict[str, EvalNode] = Field(default_factory=dict)
    claim_results: list[ClaimResult] = Field(default_factory=list)
    block_results: list[BlockResult] = Field(default_factory=list)
    transport_results: dict[str, TransportResult] = Field(default_factory=dict)
    trace: list[PrimitiveTraceEvent] = Field(default_factory=list)
    diagnostics: Diagnostics = Field(default_factory=list)


class SessionResult(BaseModel):
    """Result of executing all steps in a session.

    Contains session-level state artifacts (baselines, adequacy store) aggregated
    from the final step's machine state.
    """

    session_id: str
    step_results: list[StepResult] = Field(default_factory=list)
    baseline_states: dict[str, Any] = Field(default_factory=dict)
    adequacy_store: dict[str, Any] = Field(default_factory=dict)
    diagnostics: Diagnostics = Field(default_factory=list)


class BundleResult(BaseModel):
    """Result of executing all sessions against a bundle."""

    bundle_id: str
    session_results: list[SessionResult] = Field(default_factory=list)
    diagnostics: Diagnostics = Field(default_factory=list)


# Alias: EvaluationResult is the top-level result type
EvaluationResult = BundleResult


# ---------------------------------------------------------------------------
# Trace helper
# ---------------------------------------------------------------------------


def _trace(
    phase: int,
    primitive: str,
    inputs_summary: str = "",
    result_summary: str = "",
) -> PrimitiveTraceEvent:
    return PrimitiveTraceEvent(
        phase=phase,
        primitive=primitive,
        inputs_summary=inputs_summary,
        result_summary=result_summary,
    )


def _stubbed_diag(phase: int, primitive: str, err: NotImplementedError) -> dict[str, Any]:
    return {
        "severity": "info",
        "code": "stubbed_primitive",
        "phase": phase,
        "primitive": primitive,
        "message": str(err) or f"{primitive} is not implemented",
    }


# ---------------------------------------------------------------------------
# run_step: the main entry point
# ---------------------------------------------------------------------------


def run_step(
    bundle: BundleNode,
    session: SessionConfig,
    step: StepConfig,
    env: EvaluationEnvironment,
    primitives: PrimitiveSet | None = None,
    services: dict[str, Any] | None = None,
    adjudicator: Callable[[dict[str, Any]], Any] | None = None,
) -> StepResult:
    """Execute the normative 13-phase evaluation order for a single step.

    Phases:
        1. build step context
        2. resolve refs/policies
        3. baseline service init/reuse (stubbed)
        4. adequacy evaluation (stubbed)
        5. compose license (per-claim)
        6. evidence view construction
        7. claim classification
        8. per-evaluator expr evaluation (stubbed)
        9. support synthesis (stubbed)
       10. assemble per-evaluator evals
       11. apply resolution policy
       12. fold blocks
       13. execute transport queries (stubbed)
    """
    if primitives is None:
        primitives = PrimitiveSet()
    if services is None:
        services = {}
    active_adjudicator = adjudicator or services.get("adjudicator")

    # Inject bundle into services for primitives that need it (e.g. evaluate_adequacy_set)
    services["__bundle__"] = bundle

    # Monotonic run-step index across a bundle run; conformance fixture-backed
    # primitives use this to pick per-step expectations even when a step has
    # no evaluable claims (and therefore emits no eval callbacks).
    current_step_index = int(services.get("__fixture_step_counter__", 0))
    services["__fixture_step_index__"] = current_step_index
    services["__fixture_step_counter__"] = current_step_index + 1

    trace: list[PrimitiveTraceEvent] = []
    diags: Diagnostics = []
    machine = MachineState()
    machine.adequacy_store["__fixture_step_index__"] = current_step_index
    step_ctx: StepContext | None = None

    # Collect all claims across blocks
    all_claims: list[ClaimNode] = []
    for block in bundle.claimBlocks:
        all_claims.extend(block.claims)

    evaluators: list[EvaluatorNode] = bundle.evaluators
    evaluator_ids = [e.id for e in evaluators]
    policy: ResolutionPolicyNode = bundle.resolutionPolicy

    # ------------------------------------------------------------------
    # Phase 1: build step context
    # ------------------------------------------------------------------
    phase = 1
    try:
        step_ctx = primitives.build_step_context(bundle, session, step, env)
        diags.extend(step_ctx.diagnostics)
        trace.append(_trace(
            phase, "build_step_context",
            inputs_summary=f"step={step.id}",
            result_summary="ok",
        ))
    except NotImplementedError as exc:
        diags.append(_stubbed_diag(phase, "build_step_context", exc))
        trace.append(_trace(phase, "build_step_context", result_summary="stubbed"))
    except Exception as exc:
        diags.append({
            "severity": "error",
            "code": "phase_error",
            "phase": phase,
            "primitive": "build_step_context",
            "message": str(exc),
        })
        trace.append(_trace(phase, "build_step_context", result_summary=f"error: {exc}"))

    # ------------------------------------------------------------------
    # Phase 2: resolve refs/policies
    # ------------------------------------------------------------------
    phase = 2
    try:
        # Resolve each claim ref and each baseline ref
        refs_to_resolve: list[str] = []
        for claim in all_claims:
            refs_to_resolve.extend(claim.refs)
        for baseline in bundle.baselines:
            refs_to_resolve.append(baseline.id)

        resolved_count = 0
        for ref in refs_to_resolve:
            try:
                _, machine, ref_diags = primitives.resolve_ref(
                    ref, step_ctx, machine, services
                )
                diags.extend(ref_diags)
                resolved_count += 1
            except NotImplementedError as exc:
                diags.append(_stubbed_diag(phase, "resolve_ref", exc))
                break  # all will fail, stop trying

        trace.append(_trace(
            phase, "resolve_ref",
            inputs_summary=f"refs={len(refs_to_resolve)}",
            result_summary=f"resolved={resolved_count}",
        ))
    except Exception as exc:
        diags.append({
            "severity": "error",
            "code": "phase_error",
            "phase": phase,
            "primitive": "resolve_ref",
            "message": str(exc),
        })
        trace.append(_trace(phase, "resolve_ref", result_summary=f"error: {exc}"))

    # ------------------------------------------------------------------
    # Phase 3: baseline service init/reuse (stubbed)
    # ------------------------------------------------------------------
    phase = 3
    try:
        for baseline in bundle.baselines:
            _, machine, bl_diags = primitives.resolve_baseline(
                baseline.id, step_ctx, machine, services
            )
            diags.extend(bl_diags)
        trace.append(_trace(
            phase, "resolve_baseline",
            inputs_summary=f"baselines={len(bundle.baselines)}",
            result_summary="ok",
        ))
    except NotImplementedError as exc:
        diags.append(_stubbed_diag(phase, "resolve_baseline", exc))
        trace.append(_trace(phase, "resolve_baseline", result_summary="stubbed"))
    except Exception as exc:
        diags.append({
            "severity": "error",
            "code": "phase_error",
            "phase": phase,
            "primitive": "resolve_baseline",
            "message": str(exc),
        })
        trace.append(_trace(phase, "resolve_baseline", result_summary=f"error: {exc}"))

    # ------------------------------------------------------------------
    # Phase 4: adequacy evaluation (stubbed)
    # ------------------------------------------------------------------
    phase = 4
    try:
        anchor_ids = [a.id for a in bundle.anchors]
        if anchor_ids:
            adequacy_results, machine, adeq_diags = primitives.evaluate_adequacy_set(
                anchor_ids, step_ctx, machine, services
            )
            diags.extend(adeq_diags)
        trace.append(_trace(
            phase, "evaluate_adequacy_set",
            inputs_summary=f"anchors={len(anchor_ids)}",
            result_summary="ok",
        ))
    except NotImplementedError as exc:
        diags.append(_stubbed_diag(phase, "evaluate_adequacy_set", exc))
        trace.append(_trace(phase, "evaluate_adequacy_set", result_summary="stubbed"))
    except Exception as exc:
        diags.append({
            "severity": "error",
            "code": "phase_error",
            "phase": phase,
            "primitive": "evaluate_adequacy_set",
            "message": str(exc),
        })
        trace.append(_trace(phase, "evaluate_adequacy_set", result_summary=f"error: {exc}"))

    # ------------------------------------------------------------------
    # Phase 5: compose license (per-claim)
    # ------------------------------------------------------------------
    phase = 5
    per_claim_licenses: dict[str, LicenseResult] = {}
    for claim in all_claims:
        try:
            license_result, machine, lic_diags = primitives.compose_license(
                claim.id, step_ctx, machine, services
            )
            per_claim_licenses[claim.id] = license_result
            # Store in machine state license_store
            machine.license_store[claim.id] = license_result.model_dump()
            diags.extend(lic_diags)
        except NotImplementedError as exc:
            diags.append(_stubbed_diag(phase, "compose_license", exc))
            break
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "compose_license",
                "claim_id": claim.id,
                "message": str(exc),
            })
    trace.append(_trace(
        phase, "compose_license",
        inputs_summary=f"claims={len(all_claims)}",
        result_summary=f"licensed={len(per_claim_licenses)}",
    ))

    # ------------------------------------------------------------------
    # Phase 6: evidence view construction
    # ------------------------------------------------------------------
    phase = 6
    evidence_views: dict[str, ClaimEvidenceView] = {}
    for claim in all_claims:
        try:
            view, machine, ev_diags = primitives.build_evidence_view(
                claim, bundle, step_ctx, machine
            )
            evidence_views[claim.id] = view
            diags.extend(ev_diags)
        except NotImplementedError as exc:
            diags.append(_stubbed_diag(phase, "build_evidence_view", exc))
            break
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "build_evidence_view",
                "claim_id": claim.id,
                "message": str(exc),
            })
    trace.append(_trace(
        phase, "build_evidence_view",
        inputs_summary=f"claims={len(all_claims)}",
        result_summary=f"views={len(evidence_views)}",
    ))

    # ------------------------------------------------------------------
    # Phase 7: claim classification
    # ------------------------------------------------------------------
    phase = 7
    classifications: dict[str, ClaimClassification] = {}
    for claim in all_claims:
        try:
            cc = primitives.classify_claim(claim)
            classifications[claim.id] = cc
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "classify_claim",
                "claim_id": claim.id,
                "message": str(exc),
            })
    trace.append(_trace(
        phase, "classify_claim",
        inputs_summary=f"claims={len(all_claims)}",
        result_summary=f"evaluable={sum(1 for c in classifications.values() if c.evaluable)}",
    ))

    # ------------------------------------------------------------------
    # Phase 8: per-evaluator expr evaluation (stubbed)
    # ------------------------------------------------------------------
    phase = 8
    per_claim_truth: dict[str, dict[str, TruthCore]] = {}
    eval_expr_ok = True
    for claim in all_claims:
        cc = classifications.get(claim.id)
        # Non-evaluable NoteExpr claims bypass eval_expr
        if cc is not None and not cc.evaluable:
            continue
        per_claim_truth[claim.id] = {}
        for ev_id in evaluator_ids:
            try:
                truth_core, machine, ee_diags = primitives.eval_expr(
                    claim, ev_id, step_ctx, machine, services
                )
                per_claim_truth[claim.id][ev_id] = truth_core
                diags.extend(ee_diags)
            except NotImplementedError as exc:
                if eval_expr_ok:
                    diags.append(_stubbed_diag(phase, "eval_expr", exc))
                    eval_expr_ok = False
                # Provide a default N truth for stubbed evaluators
                per_claim_truth[claim.id][ev_id] = TruthCore(
                    truth="N", reason="eval_expr_not_implemented"
                )
            except Exception as exc:
                diags.append({
                    "severity": "error",
                    "code": "phase_error",
                    "phase": phase,
                    "primitive": "eval_expr",
                    "claim_id": claim.id,
                    "evaluator_id": ev_id,
                    "message": str(exc),
                })
                # Provide a default N truth for failed evaluators
                per_claim_truth[claim.id][ev_id] = TruthCore(
                    truth="N", reason=f"eval_expr_error: {exc}"
                )
    trace.append(_trace(
        phase, "eval_expr",
        inputs_summary=f"evaluable_claims={len(per_claim_truth)}, evaluators={len(evaluator_ids)}",
        result_summary="ok" if eval_expr_ok else "stubbed",
    ))

    # ------------------------------------------------------------------
    # Phase 9: support synthesis (stubbed)
    # ------------------------------------------------------------------
    phase = 9
    per_claim_support: dict[str, dict[str, SupportResult]] = {}
    synth_ok = True
    for claim in all_claims:
        cc = classifications.get(claim.id)
        # Non-evaluable NoteExpr claims bypass support synthesis
        if cc is not None and not cc.evaluable:
            continue
        per_claim_support[claim.id] = {}
        ev_view = evidence_views.get(claim.id)
        for ev_id in evaluator_ids:
            truth_core = per_claim_truth.get(claim.id, {}).get(ev_id)
            if truth_core is None:
                continue
            if ev_view is None:
                ev_view = ClaimEvidenceView(claim_id=claim.id)
            try:
                support, machine, sp_diags = primitives.synthesize_support(
                    claim, truth_core, ev_view, ev_id, step_ctx, machine, services
                )
                per_claim_support[claim.id][ev_id] = support
                diags.extend(sp_diags)
            except NotImplementedError as exc:
                if synth_ok:
                    diags.append(_stubbed_diag(phase, "synthesize_support", exc))
                    synth_ok = False
                # Default absent support for stubbed implementations
                per_claim_support[claim.id][ev_id] = SupportResult(support="absent")
            except Exception as exc:
                diags.append({
                    "severity": "error",
                    "code": "phase_error",
                    "phase": phase,
                    "primitive": "synthesize_support",
                    "claim_id": claim.id,
                    "evaluator_id": ev_id,
                    "message": str(exc),
                })
                # Default absent support for failed implementations
                per_claim_support[claim.id][ev_id] = SupportResult(support="absent")
    trace.append(_trace(
        phase, "synthesize_support",
        inputs_summary=f"claims={len(per_claim_support)}",
        result_summary="ok" if synth_ok else "stubbed",
    ))

    # ------------------------------------------------------------------
    # Phase 10: assemble per-evaluator evals
    # ------------------------------------------------------------------
    phase = 10
    per_claim_per_evaluator: dict[str, dict[str, EvalNode]] = {}
    for claim in all_claims:
        cc = classifications.get(claim.id)
        if cc is not None and not cc.evaluable:
            # Non-evaluable claims get N with note reason
            per_claim_per_evaluator[claim.id] = {
                ev_id: EvalNode(
                    truth="N",
                    reason="non_evaluable_note",
                    support="inapplicable",
                    provenance=[ev_id, claim.id],
                )
                for ev_id in evaluator_ids
            }
            continue
        per_claim_per_evaluator[claim.id] = {}
        for ev_id in evaluator_ids:
            truth_core = per_claim_truth.get(claim.id, {}).get(ev_id)
            support = per_claim_support.get(claim.id, {}).get(ev_id)
            if truth_core is None:
                continue
            if support is None:
                support = SupportResult(support="absent")
            try:
                eval_node = primitives.assemble_eval(truth_core, support, ev_id)
                per_claim_per_evaluator[claim.id][ev_id] = eval_node
            except Exception as exc:
                diags.append({
                    "severity": "error",
                    "code": "phase_error",
                    "phase": phase,
                    "primitive": "assemble_eval",
                    "claim_id": claim.id,
                    "evaluator_id": ev_id,
                    "message": str(exc),
                })
    trace.append(_trace(
        phase, "assemble_eval",
        inputs_summary=f"claims={len(per_claim_per_evaluator)}",
        result_summary="ok",
    ))

    # ------------------------------------------------------------------
    # Phase 11: apply resolution policy
    # ------------------------------------------------------------------
    phase = 11
    per_claim_aggregates: dict[str, EvalNode] = {}
    for claim_id, evals_by_ev in per_claim_per_evaluator.items():
        try:
            agg = primitives.apply_resolution_policy(evals_by_ev, policy, active_adjudicator)
            per_claim_aggregates[claim_id] = agg
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "apply_resolution_policy",
                "claim_id": claim_id,
                "message": str(exc),
            })
            per_claim_aggregates[claim_id] = EvalNode(
                truth="N", reason=f"resolution_error: {exc}"
            )
    trace.append(_trace(
        phase, "apply_resolution_policy",
        inputs_summary=f"claims={len(per_claim_aggregates)}",
        result_summary="ok",
    ))

    # ------------------------------------------------------------------
    # Phase 12: fold blocks
    # ------------------------------------------------------------------
    phase = 12
    per_block_per_evaluator: dict[str, dict[str, EvalNode]] = {}
    per_block_aggregates: dict[str, EvalNode] = {}
    for block in bundle.claimBlocks:
        try:
            block_ev_evals, block_agg = primitives.fold_block(
                block,
                per_claim_aggregates,
                per_claim_per_evaluator,
                classifications,
                policy,
                active_adjudicator,
            )
            per_block_per_evaluator[block.id] = block_ev_evals
            per_block_aggregates[block.id] = block_agg
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "fold_block",
                "block_id": block.id,
                "message": str(exc),
            })
            per_block_aggregates[block.id] = EvalNode(
                truth="N", reason=f"fold_error: {exc}"
            )
            per_block_per_evaluator[block.id] = {}
    trace.append(_trace(
        phase, "fold_block",
        inputs_summary=f"blocks={len(bundle.claimBlocks)}",
        result_summary=f"folded={len(per_block_aggregates)}",
    ))

    # ------------------------------------------------------------------
    # Phase 13: execute transport queries
    # ------------------------------------------------------------------
    phase = 13
    # Inject per-claim aggregates into services so execute_transport can access them
    services["__per_claim_aggregates__"] = per_claim_aggregates
    transport_results: dict[str, TransportResult] = {}
    stubbed_transport = False
    def _normalize_transport_result(value: Any) -> TransportResult:
        if isinstance(value, TransportResult):
            return value
        if isinstance(value, dict):
            return TransportResult.model_validate(value)
        raise TypeError(f"unsupported transport result type: {type(value).__name__}")

    for bridge in bundle.bridges:
        try:
            tr_result, machine, tr_diags = primitives.execute_transport(
                bridge, step_ctx, machine, services
            )
            diags.extend(tr_diags)
            # Store transport result keyed by bridge id (normalize dict outputs
            # from injected/test-double primitives).
            transport_results[bridge.id] = _normalize_transport_result(tr_result)
        except NotImplementedError as exc:
            stubbed_diag = _stubbed_diag(phase, "execute_transport", exc)
            stubbed_diag["bridge_id"] = bridge.id
            diags.append(stubbed_diag)
            stubbed_transport = True
        except Exception as exc:
            diags.append({
                "severity": "error",
                "code": "phase_error",
                "phase": phase,
                "primitive": "execute_transport",
                "bridge_id": bridge.id,
                "message": str(exc),
            })

    # Also gather any query-keyed results from machine state
    for key, tr in machine.transport_store.items():
        if key not in transport_results:
            transport_results[key] = _normalize_transport_result(tr)

    result_summary = f"ok, results={len(transport_results)}"
    if stubbed_transport:
        result_summary = f"partial_stubbed, results={len(transport_results)}"
    trace.append(_trace(
        phase, "execute_transport",
        inputs_summary=f"bridges={len(bundle.bridges)}",
        result_summary=result_summary,
    ))

    # ------------------------------------------------------------------
    # Assemble structured ClaimResult objects (deterministic claim order)
    # ------------------------------------------------------------------
    claim_results: list[ClaimResult] = []
    for claim in all_claims:
        cc = classifications.get(claim.id)
        claim_results.append(ClaimResult(
            claim_id=claim.id,
            classification=cc,
            per_evaluator=per_claim_per_evaluator.get(claim.id, {}),
            aggregate=per_claim_aggregates.get(claim.id),
            license=per_claim_licenses.get(claim.id),
            is_evaluable=cc.evaluable if cc is not None else True,
        ))

    # ------------------------------------------------------------------
    # Assemble structured BlockResult objects (deterministic block order)
    # ------------------------------------------------------------------
    block_results: list[BlockResult] = []
    for block in bundle.claimBlocks:
        block_results.append(BlockResult(
            block_id=block.id,
            per_evaluator=per_block_per_evaluator.get(block.id, {}),
            aggregate=per_block_aggregates.get(block.id),
            claims=[c.id for c in block.claims],
        ))

    # ------------------------------------------------------------------
    # Sort diagnostics deterministically and assemble final result
    # ------------------------------------------------------------------
    sorted_diags = sort_diagnostics(diags)

    return StepResult(
        step_id=step.id,
        step_context=step_ctx,
        machine_state=machine,
        per_claim_classifications=classifications,
        per_claim_per_evaluator=per_claim_per_evaluator,
        per_claim_aggregates=per_claim_aggregates,
        per_claim_licenses=per_claim_licenses,
        per_block_per_evaluator=per_block_per_evaluator,
        per_block_aggregates=per_block_aggregates,
        claim_results=claim_results,
        block_results=block_results,
        transport_results=transport_results,
        trace=trace,
        diagnostics=sorted_diags,
    )


# ---------------------------------------------------------------------------
# Convenience: run_session / run_bundle
# ---------------------------------------------------------------------------


def run_session(
    bundle: BundleNode,
    session: SessionConfig,
    env: EvaluationEnvironment,
    primitives: PrimitiveSet | None = None,
    services: dict[str, Any] | None = None,
    adjudicator: Callable[[dict[str, Any]], Any] | None = None,
) -> SessionResult:
    """Execute all steps in a session sequentially."""
    if primitives is None:
        primitives = PrimitiveSet()
    if services is None:
        services = {}

    step_results: list[StepResult] = []
    diags: Diagnostics = []

    if not session.steps:
        diags.append({
            "severity": "warning",
            "code": "empty_session",
            "session_id": session.id,
            "message": "Session has no steps configured",
        })

    for step in session.steps:
        result = run_step(bundle, session, step, env, primitives, services, adjudicator)
        step_results.append(result)

    baseline_states: dict[str, Any] = {}
    adequacy_store: dict[str, Any] = {}
    for step_result in step_results:
        machine = step_result.machine_state

        for bid, bs in machine.baseline_store.items():
            if hasattr(bs, "model_dump"):
                baseline_states[bid] = bs.model_dump()
            elif isinstance(bs, dict):
                baseline_states[bid] = dict(bs)
            else:
                baseline_states[bid] = bs

        for key, value in machine.adequacy_store.items():
            if str(key).startswith("__fixture_"):
                continue
            if key in {"per_assessment", "per_anchor_task", "joint"} and isinstance(value, dict):
                target = adequacy_store.setdefault(key, {})
                if isinstance(target, dict):
                    target.update(value)
                else:
                    adequacy_store[key] = dict(value)
            else:
                adequacy_store[key] = value

    return SessionResult(
        session_id=session.id,
        step_results=step_results,
        baseline_states=baseline_states,
        adequacy_store=adequacy_store,
        diagnostics=sort_diagnostics(diags),
    )


def run_bundle(
    bundle: BundleNode,
    sessions: list[SessionConfig],
    env: EvaluationEnvironment,
    primitives: PrimitiveSet | None = None,
    services: dict[str, Any] | None = None,
    adjudicator: Callable[[dict[str, Any]], Any] | None = None,
) -> BundleResult:
    """Execute all sessions against a bundle sequentially."""
    if primitives is None:
        primitives = PrimitiveSet()
    if services is None:
        services = {}

    session_results: list[SessionResult] = []
    diags: Diagnostics = []

    if not sessions:
        diags.append({
            "severity": "warning",
            "code": "no_sessions",
            "bundle_id": bundle.id,
            "message": "No sessions provided for bundle evaluation",
        })

    for session in sessions:
        result = run_session(bundle, session, env, primitives, services, adjudicator)
        session_results.append(result)

    return BundleResult(
        bundle_id=bundle.id,
        session_results=session_results,
        diagnostics=sort_diagnostics(diags),
    )
