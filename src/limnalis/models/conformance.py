from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

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
