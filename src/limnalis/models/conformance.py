from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .ast import SummaryScope
from .base import LimnalisModel

TruthValue = Literal["T", "F", "B", "N"]
SupportValue = Literal["supported", "partial", "conflicted", "absent", "inapplicable"]
Severity = Literal["info", "warning", "error"]
TransportStatus = Literal[
    "metadata_only",
    "preserved",
    "degraded",
    "transported",
    "blocked",
    "unresolved",
    "pattern_only",
]


class EvalSnapshot(LimnalisModel):
    truth: TruthValue
    reason: str | None = None
    support: SupportValue | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: list[str] = Field(default_factory=list)


class ClaimLicenseExpectation(LimnalisModel):
    overall: EvalSnapshot | None = None
    individual: dict[str, EvalSnapshot] = Field(default_factory=dict)
    joint: EvalSnapshot | None = None


class ClaimExpectation(LimnalisModel):
    per_evaluator: dict[str, EvalSnapshot] | None = None
    aggregate: EvalSnapshot | None = None
    license: ClaimLicenseExpectation | None = None

    @field_validator("per_evaluator")
    @classmethod
    def _non_empty_per_evaluator(cls, value: dict[str, EvalSnapshot] | None) -> dict[str, EvalSnapshot] | None:
        if value is not None and not value:
            raise ValueError("per_evaluator must not be empty when provided")
        return value


class BlockExpectation(LimnalisModel):
    per_evaluator: dict[str, TruthValue]
    aggregate: TruthValue
    claimIds: list[str] = Field(default_factory=list)


class TransportExpectation(LimnalisModel):
    status: TransportStatus
    sourceAggregate: EvalSnapshot | None = None
    dstAggregate: EvalSnapshot | None = None
    per_evaluator: dict[str, EvalSnapshot] | None = None


class StepExpectation(LimnalisModel):
    id: str
    claims: dict[str, ClaimExpectation] = Field(default_factory=dict)
    blocks: dict[str, BlockExpectation] = Field(default_factory=dict)
    transports: dict[str, TransportExpectation] = Field(default_factory=dict)


class SessionExpectation(LimnalisModel):
    id: str
    steps: list[StepExpectation]

    @field_validator("steps")
    @classmethod
    def _non_empty_steps(cls, value: list[StepExpectation]) -> list[StepExpectation]:
        if not value:
            raise ValueError("steps must not be empty")
        return value


class DiagnosticExpectation(LimnalisModel):
    severity: Severity
    code: str
    subject: str | None = None
    message: str | None = None


class AdequacyExpectation(LimnalisModel):
    truth: TruthValue
    reason: str | None = None


class ExpectedResult(LimnalisModel):
    baseline_states: dict[str, Literal["ready", "deferred", "unresolved"]] = Field(default_factory=dict)
    sessions: list[SessionExpectation]
    adequacy_expectations: dict[str, AdequacyExpectation] = Field(default_factory=dict)
    diagnostics: list[DiagnosticExpectation]

    @field_validator("sessions")
    @classmethod
    def _non_empty_sessions(cls, value: list[SessionExpectation]) -> list[SessionExpectation]:
        if not value:
            raise ValueError("sessions must not be empty")
        return value


# ---------------------------------------------------------------------------
# Milestone 6B: Summary runtime types
# ---------------------------------------------------------------------------


class SummaryRequest(BaseModel):
    """Runtime request for a summary evaluation."""

    policy_id: str
    scope: SummaryScope
    target_ids: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class SummaryResult(BaseModel):
    """Runtime result of a summary evaluation."""

    policy_id: str
    scope: SummaryScope
    normative: bool = False
    summary_truth: str | None = None
    summary_support: float | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Milestone 6B: Transport trace runtime type
# ---------------------------------------------------------------------------


class TransportTrace(BaseModel):
    """Richer transport trace/proof record."""

    hops: list[dict[str, Any]] = Field(default_factory=list)
    precondition_outcomes: dict[str, bool] = Field(default_factory=dict)
    semantic_requirements: list[dict[str, Any]] = Field(default_factory=list)
    mapping_steps: list[str] = Field(default_factory=list)
    per_hop_evals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    total_loss: list[str] = Field(default_factory=list)
    total_gain: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Milestone 6B: Adequacy execution runtime types
# ---------------------------------------------------------------------------


class BasisResolutionEntry(BaseModel):
    """One resolved basis item."""

    basis_id: str
    resolved: bool
    truth: str | None = None
    source: Literal["claim", "evidence", "anchor", "external"]
    provenance: list[str] = Field(default_factory=list)


class AdequacyExecutionTrace(BaseModel):
    """Richer adequacy execution trace."""

    assessment_id: str
    method: str
    basis_resolution: list[BasisResolutionEntry] = Field(default_factory=list)
    computed_score: float | None = None
    declared_score: float | None = None
    score_divergence: float | None = None
    threshold: float | None = None
    adequate: bool | None = None
    failure_kind: Literal[
        "threshold",
        "method_conflict",
        "basis_failure",
        "policy_failure",
        "circular_basis",
    ] | None = None
    provenance: list[str] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
