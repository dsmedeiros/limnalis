"""Protocol definitions for the 13 Limnalis primitive operations.

Each primitive follows the uniform shape:
    op(inputs, step_ctx, machine_state, services) -> (output, machine_state, diagnostics)

where practical.  Some primitives deviate slightly for ergonomic reasons.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import (
    ClaimClassification,
    ClaimEvidenceView,
    EvalNode,
    LicenseResult,
    MachineState,
    StepContext,
    TruthCore,
    SupportResult,
)


Diagnostics = list[dict[str, Any]]


# ---------------------------------------------------------------------------
# 1. resolve_ref
# ---------------------------------------------------------------------------


@runtime_checkable
class ResolveRef(Protocol):
    def __call__(
        self,
        ref: str,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[Any, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 2. build_step_context
# ---------------------------------------------------------------------------


@runtime_checkable
class BuildStepContext(Protocol):
    def __call__(
        self,
        bundle: Any,
        session: Any,
        step: Any,
        env: Any,
    ) -> StepContext: ...


# ---------------------------------------------------------------------------
# 3. resolve_baseline
# ---------------------------------------------------------------------------


@runtime_checkable
class ResolveBaseline(Protocol):
    def __call__(
        self,
        baseline_id: str,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[Any, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 4. evaluate_adequacy_set
# ---------------------------------------------------------------------------


@runtime_checkable
class EvaluateAdequacySet(Protocol):
    def __call__(
        self,
        anchor_ids: list[str],
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[dict[str, Any], MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 5. compose_license
# ---------------------------------------------------------------------------


@runtime_checkable
class ComposeLicense(Protocol):
    def __call__(
        self,
        claim_id: str,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[LicenseResult, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 6. build_evidence_view
# ---------------------------------------------------------------------------


@runtime_checkable
class BuildEvidenceView(Protocol):
    def __call__(
        self,
        claim: Any,
        bundle: Any,
        step_ctx: StepContext,
        machine_state: MachineState,
    ) -> tuple[ClaimEvidenceView, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 7. classify_claim
# ---------------------------------------------------------------------------


@runtime_checkable
class ClassifyClaim(Protocol):
    def __call__(
        self,
        claim: Any,
    ) -> ClaimClassification: ...


# ---------------------------------------------------------------------------
# 8. eval_expr
# ---------------------------------------------------------------------------


@runtime_checkable
class EvalExpr(Protocol):
    def __call__(
        self,
        claim: Any,
        evaluator_id: str,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[TruthCore, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 9. synthesize_support
# ---------------------------------------------------------------------------


@runtime_checkable
class SynthesizeSupport(Protocol):
    def __call__(
        self,
        claim: Any,
        truth_core: TruthCore,
        evidence_view: ClaimEvidenceView,
        evaluator_id: str,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[SupportResult, MachineState, Diagnostics]: ...


# ---------------------------------------------------------------------------
# 10. assemble_eval
# ---------------------------------------------------------------------------


@runtime_checkable
class AssembleEval(Protocol):
    def __call__(
        self,
        truth_core: TruthCore,
        support_result: SupportResult,
        evaluator_id: str,
    ) -> EvalNode: ...


# ---------------------------------------------------------------------------
# 11. apply_resolution_policy
# ---------------------------------------------------------------------------


@runtime_checkable
class ApplyResolutionPolicy(Protocol):
    def __call__(
        self,
        per_evaluator: dict[str, EvalNode],
        policy: Any,
        adjudicator: Any | None,
    ) -> EvalNode: ...


# ---------------------------------------------------------------------------
# 12. fold_block
# ---------------------------------------------------------------------------


@runtime_checkable
class FoldBlock(Protocol):
    def __call__(
        self,
        block: Any,
        per_claim_aggregates: dict[str, EvalNode],
        per_claim_per_evaluator: dict[str, dict[str, EvalNode]],
        claim_classifications: dict[str, ClaimClassification],
        policy: Any,
        adjudicator: Any | None,
    ) -> tuple[dict[str, EvalNode], EvalNode]: ...


# ---------------------------------------------------------------------------
# 13. execute_transport
# ---------------------------------------------------------------------------


@runtime_checkable
class ExecuteTransport(Protocol):
    def __call__(
        self,
        bridge: Any,
        step_ctx: StepContext,
        machine_state: MachineState,
        services: dict[str, Any],
    ) -> tuple[Any, MachineState, Diagnostics]: ...
