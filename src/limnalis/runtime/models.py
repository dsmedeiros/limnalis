"""Runtime models for the Limnalis abstract machine."""

from __future__ import annotations

from typing import Any, Callable, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ..models.ast import (
    BundleNode,
    ClaimNode,
    EvidenceNode,
    EvidenceRelationNode,
    FrameNode,
    FrameOrPatternNode,
    FramePatternNode,
    TimeCtxNode,
)
from ..models.conformance import EvalSnapshot, SupportValue, TransportStatus, TruthValue


# ---------------------------------------------------------------------------
# Evaluation environment (injected context for a run)
# ---------------------------------------------------------------------------


class EvaluationEnvironment(BaseModel):
    """External environment provided to the runner at invocation time."""

    clock: str | None = None
    history: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Session / step configuration (what to evaluate)
# ---------------------------------------------------------------------------


class StepConfig(BaseModel):
    """Configuration for a single evaluation step."""

    id: str
    frame_override: FrameOrPatternNode | None = None
    time: TimeCtxNode | None = None
    history_binding: str | None = None


class SessionConfig(BaseModel):
    """Configuration for an evaluation session."""

    id: str
    base_frame: FrameOrPatternNode | None = None
    base_time: TimeCtxNode | None = None
    steps: list[StepConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# StepContext: effective context for a step
# ---------------------------------------------------------------------------


class StepContext(BaseModel):
    """Effective evaluation context for a single step, produced by build_step_context."""

    effective_frame: FrameOrPatternNode
    effective_time: TimeCtxNode | None = None
    effective_history: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Truth / support / eval result models
# ---------------------------------------------------------------------------


class TruthCore(BaseModel):
    """Core truth evaluation result from an evaluator."""

    truth: TruthValue
    reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: list[str] = Field(default_factory=list)


class SupportResult(BaseModel):
    """Support assessment from an evaluator."""

    support: SupportValue
    provenance: list[str] = Field(default_factory=list)


class EvalNode(BaseModel):
    """Assembled evaluation result for a single claim from a single evaluator."""

    truth: TruthValue
    reason: str | None = None
    support: SupportValue | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Claim classification result
# ---------------------------------------------------------------------------


class ClaimClassification(BaseModel):
    """Result of classify_claim: whether a claim is evaluable."""

    claim_id: str
    evaluable: bool
    expr_kind: str
    reason: str | None = None


# ---------------------------------------------------------------------------
# Evidence view
# ---------------------------------------------------------------------------


class ClaimEvidenceView(BaseModel):
    """Per-claim evidence view constructed by build_evidence_view."""

    claim_id: str
    explicit_evidence: list[EvidenceNode] = Field(default_factory=list)
    related_evidence: list[EvidenceNode] = Field(default_factory=list)
    relations: list[EvidenceRelationNode] = Field(default_factory=list)
    cross_conflict_score: float | None = None
    completeness_summary: float | None = None


# ---------------------------------------------------------------------------
# Adequacy result models
# ---------------------------------------------------------------------------


class AdequacyResult(BaseModel):
    """Result of evaluating a single adequacy assessment."""

    assessment_id: str
    task: str
    producer: str
    adequate: bool
    truth: TruthValue
    reason: str | None = None
    score: float | None = None
    threshold: float | None = None
    provenance: list[str] = Field(default_factory=list)


class AnchorAdequacyResult(BaseModel):
    """Aggregated adequacy result for an anchor, scoped by task."""

    anchor_id: str
    task: str
    truth: TruthValue
    reason: str | None = None
    per_assessment: list[AdequacyResult] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class JointAdequacyResult(BaseModel):
    """Result of evaluating a joint adequacy group."""

    joint_id: str
    anchors: list[str]
    truth: TruthValue
    reason: str | None = None
    per_assessment: list[AdequacyResult] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# License result (placeholder for future use)
# ---------------------------------------------------------------------------


class AnchorLicenseEntry(BaseModel):
    """Per-anchor adequacy result within a license evaluation."""

    anchor_id: str
    task: str
    truth: TruthValue
    reason: str | None = None


class JointLicenseEntry(BaseModel):
    """Per-joint-group adequacy result within a license evaluation."""

    joint_id: str
    anchors: list[str]
    truth: TruthValue
    reason: str | None = None


class LicenseOverall(BaseModel):
    """Overall license truth and reason."""

    truth: TruthValue
    reason: str | None = None


class LicenseResult(BaseModel):
    """Result of license composition for a claim."""

    claim_id: str
    overall: LicenseOverall
    individual: list[AnchorLicenseEntry] = Field(default_factory=list)
    joint: list[JointLicenseEntry] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Transport result
# ---------------------------------------------------------------------------


class TransportResult(BaseModel):
    """Result of executing a transport query for a bridge."""

    status: TransportStatus
    srcAggregate: EvalNode | None = None
    dstAggregate: EvalNode | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    mappedClaim: str | None = None
    per_evaluator: dict[str, EvalNode] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    degradation_policy_used: str | None = None
    completion_actions: list[str] = Field(default_factory=list)


class TransportChainResult(BaseModel):
    """Result of executing a chained transport plan across multiple bridges."""

    plan_id: str
    status: TransportStatus
    per_hop: list[TransportResult] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Claim result (per-claim structured output)
# ---------------------------------------------------------------------------


class ClaimResult(BaseModel):
    """Structured per-claim evaluation result."""

    claim_id: str
    classification: ClaimClassification | None = None
    per_evaluator: dict[str, EvalNode] = Field(default_factory=dict)
    aggregate: EvalNode | None = None
    license: LicenseResult | None = None
    is_evaluable: bool = True


# ---------------------------------------------------------------------------
# Block result (per-block structured output)
# ---------------------------------------------------------------------------


class BlockResult(BaseModel):
    """Structured per-block evaluation result."""

    block_id: str
    per_evaluator: dict[str, EvalNode] = Field(default_factory=dict)
    aggregate: EvalNode | None = None
    claims: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Baseline state
# ---------------------------------------------------------------------------


class BaselineState(BaseModel):
    """Runtime state of a baseline."""

    baseline_id: str
    status: Literal["ready", "deferred", "unresolved"] = "unresolved"
    value: Any = None


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class ResolutionStore(BaseModel):
    """Accumulated resolution results keyed by claim id."""

    results: dict[str, EvalNode] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Machine state
# ---------------------------------------------------------------------------


class MachineState(BaseModel):
    """Top-level abstract machine state threaded through primitive operations."""

    resolution_store: ResolutionStore = Field(default_factory=ResolutionStore)
    baseline_store: dict[str, BaselineState] = Field(default_factory=dict)
    adequacy_store: dict[str, Any] = Field(default_factory=dict)
    license_store: dict[str, Any] = Field(default_factory=dict)
    evidence_views: dict[str, ClaimEvidenceView] = Field(default_factory=dict)
    transport_store: dict[str, TransportResult] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Primitive trace event (for debugging / testing phase order)
# ---------------------------------------------------------------------------


class PrimitiveTraceEvent(BaseModel):
    """Records invocation of a primitive for tracing/debugging."""

    phase: int
    primitive: str
    inputs_summary: str = ""
    result_summary: str = ""


# ---------------------------------------------------------------------------
# Diagnostics sorting helper
# ---------------------------------------------------------------------------


def sort_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort diagnostics deterministically by (phase, code, subject).

    Missing keys sort as empty string to ensure stable ordering.
    """
    # Phase ordering: numeric phases sort naturally, string phases sort after.
    # We normalise to (type_rank, comparable_value) so int and str never compare directly.
    def _phase_key(phase: Any) -> tuple[int, Any]:
        if isinstance(phase, int):
            return (0, phase)
        if isinstance(phase, str) and phase.isdigit():
            return (0, int(phase))
        return (1, str(phase) if phase is not None else "")

    return sorted(
        diagnostics,
        key=lambda d: (
            _phase_key(d.get("phase", "")),
            str(d.get("code", "") or ""),
            str(
                d.get("subject", d.get("claim_id", d.get("block_id", d.get("primitive", ""))))
                or ""
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Evaluator bindings protocol for eval_expr dispatch
# ---------------------------------------------------------------------------

# Handler signature: (expr, claim, step_ctx, machine_state) -> TruthCore
ExprHandler = Callable[[Any, Any, "StepContext", "MachineState"], "TruthCore"]


@runtime_checkable
class EvaluatorBindings(Protocol):
    """Protocol for looking up expression evaluation handlers by evaluator_id.

    The bindings registry maps evaluator_id -> expr_type -> handler.
    The handler signature is: handler(expr, claim, step_ctx, machine_state) -> TruthCore
    """

    def get_handler(self, evaluator_id: str, expr_type: str) -> ExprHandler | None:
        """Return a handler for the given evaluator and expression type, or None."""
        ...
