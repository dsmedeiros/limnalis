"""Runtime models for the Limnalis abstract machine."""

from __future__ import annotations

from typing import Any, Literal

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
from ..models.conformance import EvalSnapshot, SupportValue, TruthValue


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
# License result (placeholder for future use)
# ---------------------------------------------------------------------------


class LicenseResult(BaseModel):
    """Result of license composition for a claim."""

    claim_id: str
    licensed: bool
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


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
    evidence_views: dict[str, ClaimEvidenceView] = Field(default_factory=dict)
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
