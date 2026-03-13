from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator

from .base import LimnalisModel

FacetName = Literal["system", "namespace", "scale", "task", "regime", "observer", "version"]
ResolutionPolicyKind = Literal["single", "paraconsistent_union", "priority_order", "adjudicated"]
TransportMode = Literal["metadata_only", "preserve", "degrade", "remap_recompute"]
EvaluatorKind = Literal["model", "human", "agent", "institution", "ensemble", "process"]
EvaluatorRole = Literal["primary", "adversarial", "audit", "auxiliary"]
BindingKind = Literal["equation", "dataset", "code", "model", "document", "policy", "ontology"]
AssumptionStatus = Literal["active", "suspended", "counterfactual"]
BaselineKind = Literal["point", "set", "manifold", "moving"]
BaselineMode = Literal["fixed", "on_reference", "tracked"]
EvidenceKind = Literal["measurement", "dataset", "testimony", "simulation", "audit", "derived"]
EvidenceRelationKind = Literal["corroborates", "conflicts", "depends_on", "duplicate_of"]
AnchorSubtype = Literal["idealization", "placeholder", "proxy", "aggregate"]
AnchorStatus = Literal["active", "inactive", "counterfactual"]
Stratum = Literal["local", "systemic", "meta"]
ClaimKind = Literal[
    "atomic",
    "causal",
    "dynamic",
    "emergence",
    "declaration",
    "judgment",
    "note",
    "logical",
]
LogicalOp = Literal["not", "and", "or", "implies", "iff"]
CausalMode = Literal["obs", "do"]
DynamicOp = Literal["approaches", "diverges", "oscillates", "cycles", "transforms", "crosses"]
TimeKind = Literal["point", "interval", "window"]
TruthValue = Literal["T", "F", "B", "N"]


class FacetValueMap(LimnalisModel):
    system: str | None = None
    namespace: str | None = None
    scale: str | None = None
    task: str | None = None
    regime: str | None = None
    observer: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def _at_least_one_facet(self) -> "FacetValueMap":
        if not any(getattr(self, field) is not None for field in type(self).model_fields):
            raise ValueError("FacetValueMap must include at least one facet")
        return self


class FrameNode(LimnalisModel):
    node: Literal["Frame"] = "Frame"
    system: str
    namespace: str
    scale: str
    task: str
    regime: str
    observer: str | None = None
    version: str | None = None
    facetPolicy: str | None = None


class FramePatternNode(LimnalisModel):
    node: Literal["FramePattern"] = "FramePattern"
    facets: FacetValueMap
    facetPolicy: str | None = None


FrameOrPatternNode = Annotated[FrameNode | FramePatternNode, Field(discriminator="node")]


class ResolutionPolicyNode(LimnalisModel):
    node: Literal["ResolutionPolicy"] = "ResolutionPolicy"
    id: str
    kind: ResolutionPolicyKind
    members: list[str] | None = None
    order: list[str] | None = None
    binding: str | None = None

    @field_validator("members", "order")
    @classmethod
    def _unique_lists(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("members/order values must be unique")
        return value

    @model_validator(mode="after")
    def _enforce_kind_rules(self) -> "ResolutionPolicyNode":
        if self.kind == "single":
            if not self.members or len(self.members) != 1:
                raise ValueError("single resolution policy requires exactly one member")
            if self.order is not None or self.binding is not None:
                raise ValueError("single resolution policy forbids order and binding")
        elif self.kind == "paraconsistent_union":
            if not self.members:
                raise ValueError("paraconsistent_union requires members")
            if self.order is not None or self.binding is not None:
                raise ValueError("paraconsistent_union forbids order and binding")
        elif self.kind == "priority_order":
            if not self.order:
                raise ValueError("priority_order requires order")
            if self.binding is not None:
                raise ValueError("priority_order forbids binding")
        elif self.kind == "adjudicated":
            if not self.members or not self.binding:
                raise ValueError("adjudicated requires members and binding")
            if self.order is not None:
                raise ValueError("adjudicated forbids order")
        return self


class TimeCtxNode(LimnalisModel):
    node: Literal["TimeCtx"] = "TimeCtx"
    kind: TimeKind
    t: str | None = None
    start: str | None = None
    end: str | None = None
    lag: str | None = None
    step: str | None = None

    @model_validator(mode="after")
    def _enforce_time_shape(self) -> "TimeCtxNode":
        if self.kind == "point" and self.t is None:
            raise ValueError("point time contexts require t")
        if self.kind in {"interval", "window"} and (self.start is None or self.end is None):
            raise ValueError("interval/window time contexts require start and end")
        return self


class EvaluatorNode(LimnalisModel):
    node: Literal["Evaluator"] = "Evaluator"
    id: str
    kind: EvaluatorKind
    binding: str
    role: EvaluatorRole | None = None
    evidencePolicy: str | None = None
    inferencePolicy: str | None = None
    provenancePolicy: str | None = None


class BindingNode(LimnalisModel):
    node: Literal["Binding"] = "Binding"
    id: str
    kind: BindingKind
    target: str
    version: str | None = None
    hash: str | None = None


class FrameFacetOrderNode(LimnalisModel):
    system: Literal["eq"] | str
    namespace: Literal["eq"] | str
    scale: Literal["eq"] | str
    task: Literal["eq"] | str
    regime: Literal["eq"] | str
    observer: Literal["eq"] | str
    version: Literal["eq"] | str


class FrameFacetPolicyNode(LimnalisModel):
    node: Literal["FrameFacetPolicy"] = "FrameFacetPolicy"
    id: str
    order: FrameFacetOrderNode
    independent: list[tuple[FacetName, FacetName]] | None = None
    dependsOn: list[tuple[FacetName, FacetName]] | None = None


class SymbolTermNode(LimnalisModel):
    node: Literal["SymbolTerm"] = "SymbolTerm"
    value: str


class NumberTermNode(LimnalisModel):
    node: Literal["NumberTerm"] = "NumberTerm"
    value: float


class StringTermNode(LimnalisModel):
    node: Literal["StringTerm"] = "StringTerm"
    value: str


class BooleanTermNode(LimnalisModel):
    node: Literal["BooleanTerm"] = "BooleanTerm"
    value: bool


class UriTermNode(LimnalisModel):
    node: Literal["UriTerm"] = "UriTerm"
    value: str


class BaselineRefTermNode(LimnalisModel):
    node: Literal["BaselineRefTerm"] = "BaselineRefTerm"
    id: str


class UnboundRefTermNode(LimnalisModel):
    node: Literal["UnboundRefTerm"] = "UnboundRefTerm"
    kind: str


class NullTermNode(LimnalisModel):
    node: Literal["NullTerm"] = "NullTerm"


# Forward-declared unions are rebuilt at the end of the module.
ExprNode: Any
ArgNode: Any
TermNode: Any
FramePatternOrExprNode: Any
AnchorTermNode: Any
CriterionSpecNode: Any


class ListTermNode(LimnalisModel):
    node: Literal["ListTerm"] = "ListTerm"
    items: list["ArgNode"]


class PredicateExprNode(LimnalisModel):
    node: Literal["PredicateExpr"] = "PredicateExpr"
    name: str
    args: list["ArgNode"] = Field(default_factory=list)


class LogicalExprNode(LimnalisModel):
    node: Literal["LogicalExpr"] = "LogicalExpr"
    op: LogicalOp
    args: list["ExprNode"]

    @model_validator(mode="after")
    def _enforce_arity(self) -> "LogicalExprNode":
        if self.op == "not" and len(self.args) != 1:
            raise ValueError("LogicalExpr not requires exactly one argument")
        if self.op in {"and", "or", "implies", "iff"} and len(self.args) < 2:
            raise ValueError(f"LogicalExpr {self.op} requires at least two arguments")
        return self


class CausalExprNode(LimnalisModel):
    node: Literal["CausalExpr"] = "CausalExpr"
    mode: CausalMode
    lhs: "ExprNode"
    rhs: "ExprNode"
    intervention: "str | ExprNode | None" = None


class DynamicExprNode(LimnalisModel):
    node: Literal["DynamicExpr"] = "DynamicExpr"
    op: DynamicOp
    subject: "TermNode"
    target: "ArgNode | None" = None
    qualifiers: dict[str, Any] | None = None


class EmergenceExprNode(LimnalisModel):
    node: Literal["EmergenceExpr"] = "EmergenceExpr"
    property: "ExprNode"
    onset: "ExprNode"
    persistsWhile: "ExprNode | None" = None
    dissolvesWhen: "ExprNode | None" = None
    hysteresis: "ExprNode | None" = None
    witness: list[str] = Field(default_factory=list)


class DeclarationExprNode(LimnalisModel):
    node: Literal["DeclarationExpr"] = "DeclarationExpr"
    term: "TermNode"
    declaredAs: str
    within: "FramePatternOrExprNode | None" = None


class JudgedExprNode(LimnalisModel):
    node: Literal["JudgedExpr"] = "JudgedExpr"
    expr: "ExprNode"
    criterionRef: str


class NoteExprNode(LimnalisModel):
    node: Literal["NoteExpr"] = "NoteExpr"
    text: str


TermNode = Annotated[
    SymbolTermNode
    | NumberTermNode
    | StringTermNode
    | BooleanTermNode
    | UriTermNode
    | ListTermNode
    | BaselineRefTermNode
    | UnboundRefTermNode
    | NullTermNode,
    Field(discriminator="node"),
]

ExprNode = Annotated[
    PredicateExprNode
    | LogicalExprNode
    | CausalExprNode
    | DynamicExprNode
    | EmergenceExprNode
    | DeclarationExprNode
    | JudgedExprNode
    | NoteExprNode,
    Field(discriminator="node"),
]

ArgNode = Annotated[
    SymbolTermNode
    | NumberTermNode
    | StringTermNode
    | BooleanTermNode
    | UriTermNode
    | ListTermNode
    | BaselineRefTermNode
    | UnboundRefTermNode
    | NullTermNode
    | PredicateExprNode
    | LogicalExprNode
    | CausalExprNode
    | DynamicExprNode
    | EmergenceExprNode
    | DeclarationExprNode
    | JudgedExprNode
    | NoteExprNode,
    Field(discriminator="node"),
]

FramePatternOrExprNode = Annotated[
    FramePatternNode
    | PredicateExprNode
    | LogicalExprNode
    | CausalExprNode
    | DynamicExprNode
    | EmergenceExprNode
    | DeclarationExprNode
    | JudgedExprNode
    | NoteExprNode,
    Field(discriminator="node"),
]


class AssumptionNode(LimnalisModel):
    node: Literal["Assumption"] = "Assumption"
    id: str
    expr: ExprNode
    status: AssumptionStatus
    refs: list[str] = Field(default_factory=list)


class CriterionExprNode(LimnalisModel):
    kind: Literal["expr"] = "expr"
    expr: ExprNode


class CriterionRefNode(LimnalisModel):
    kind: Literal["ref"] = "ref"
    ref: str


CriterionSpecNode = Annotated[CriterionExprNode | CriterionRefNode, Field(discriminator="kind")]


class BaselineNode(LimnalisModel):
    node: Literal["Baseline"] = "Baseline"
    id: str
    kind: BaselineKind
    criterion: CriterionSpecNode
    frame: FrameOrPatternNode
    evaluationMode: BaselineMode

    @model_validator(mode="after")
    def _moving_requires_tracked(self) -> "BaselineNode":
        if self.kind == "moving" and self.evaluationMode != "tracked":
            raise ValueError("moving baselines require evaluationMode='tracked'")
        return self


class EvidenceNode(LimnalisModel):
    node: Literal["Evidence"] = "Evidence"
    id: str
    kind: EvidenceKind
    binding: str
    observer: str | None = None
    time: TimeCtxNode | None = None
    completeness: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    internalConflict: Annotated[float, Field(ge=0.0, le=1.0)] | None = None


class EvidenceRelationNode(LimnalisModel):
    node: Literal["EvidenceRelation"] = "EvidenceRelation"
    id: str
    lhs: str
    rhs: str
    kind: EvidenceRelationKind
    score: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    refs: list[str] = Field(default_factory=list)


class AdequacyAssessmentNode(LimnalisModel):
    node: Literal["AdequacyAssessment"] = "AdequacyAssessment"
    id: str
    task: str
    producer: str
    score: Annotated[float, Field(ge=0.0, le=1.0)] | Literal["N"] | None = None
    threshold: Annotated[float, Field(ge=0.0, le=1.0)]
    method: str
    basis: list[str] = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    failureModes: list[str] = Field(default_factory=list)


class AnchorTermSymbolNode(LimnalisModel):
    kind: Literal["symbol"] = "symbol"
    value: str


class AnchorTermClaimNode(LimnalisModel):
    kind: Literal["claim"] = "claim"
    value: str


class AnchorTermExprNode(LimnalisModel):
    kind: Literal["expr"] = "expr"
    expr: ExprNode


AnchorTermNode = Annotated[
    AnchorTermSymbolNode | AnchorTermClaimNode | AnchorTermExprNode,
    Field(discriminator="kind"),
]


class AnchorNode(LimnalisModel):
    node: Literal["Anchor"] = "Anchor"
    id: str
    term: AnchorTermNode
    subtype: AnchorSubtype
    status: AnchorStatus
    adequacyPolicy: str | None = None
    adequacy: list[AdequacyAssessmentNode] = Field(default_factory=list)
    requiresJointWith: list[str] = Field(default_factory=list)

    @field_validator("requiresJointWith")
    @classmethod
    def _unique_requires(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("requiresJointWith must contain unique values")
        return value


class JointAdequacyNode(LimnalisModel):
    node: Literal["JointAdequacy"] = "JointAdequacy"
    id: str
    anchors: list[str]
    adequacyPolicy: str | None = None
    assessments: list[AdequacyAssessmentNode]

    @field_validator("anchors")
    @classmethod
    def _validate_anchors(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError("JointAdequacy anchors must contain at least two items")
        if len(value) != len(set(value)):
            raise ValueError("JointAdequacy anchors must be unique")
        return value

    @field_validator("assessments")
    @classmethod
    def _validate_assessments(
        cls, value: list[AdequacyAssessmentNode]
    ) -> list[AdequacyAssessmentNode]:
        if not value:
            raise ValueError("JointAdequacy assessments must contain at least one item")
        return value


class TransportNode(LimnalisModel):
    node: Literal["Transport"] = "Transport"
    mode: TransportMode
    claimMap: str | None = None
    truthPolicy: str | None = None
    preconditions: list[str] = Field(default_factory=list)
    dstEvaluators: list[str] | None = None
    dstResolutionPolicy: str | None = None

    @field_validator("dstEvaluators")
    @classmethod
    def _validate_dst_evaluators(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and not value:
            raise ValueError("dstEvaluators must contain at least one item when provided")
        return value

    @model_validator(mode="after")
    def _enforce_transport_shape(self) -> "TransportNode":
        if self.mode == "metadata_only":
            if any(
                value is not None
                for value in [
                    self.claimMap,
                    self.truthPolicy,
                    self.dstEvaluators,
                    self.dstResolutionPolicy,
                ]
            ):
                raise ValueError(
                    "metadata_only transport forbids claimMap, truthPolicy, "
                    "dstEvaluators, dstResolutionPolicy"
                )
        elif self.mode in {"preserve", "degrade"}:
            if (
                self.claimMap is not None
                or self.dstEvaluators is not None
                or self.dstResolutionPolicy is not None
            ):
                raise ValueError(
                    f"{self.mode} transport forbids claimMap, dstEvaluators, dstResolutionPolicy"
                )
        elif self.mode == "remap_recompute":
            if self.claimMap is None:
                raise ValueError("remap_recompute transport requires claimMap")
            if self.truthPolicy is not None:
                raise ValueError("remap_recompute transport forbids truthPolicy")
        return self


class BridgeNode(LimnalisModel):
    node: Literal["Bridge"] = "Bridge"
    id: str
    from_: FramePatternNode = Field(alias="from")
    to: FramePatternNode
    via: str
    preserve: list[str]
    lose: list[str]
    gain: list[str] = Field(default_factory=list)
    risk: list[Literal["aggregation_reversal", "aliasing", "temporal_smear", "observer_shift"]] = (
        Field(default_factory=list)
    )
    transport: TransportNode


class ClaimNode(LimnalisModel):
    node: Literal["Claim"] = "Claim"
    id: str
    kind: ClaimKind
    expr: ExprNode
    usesAnchors: list[str] = Field(default_factory=list)
    semanticRequirements: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    annotations: dict[str, Any] = Field(default_factory=dict)

    @field_validator("usesAnchors", "semanticRequirements")
    @classmethod
    def _unique_str_lists(cls, value: list[str], info: ValidationInfo) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError(f"{info.field_name} must contain unique values")
        return value


class ClaimBlockNode(LimnalisModel):
    node: Literal["ClaimBlock"] = "ClaimBlock"
    id: str
    stratum: Stratum
    claims: list[ClaimNode]

    @field_validator("claims")
    @classmethod
    def _min_claims(cls, value: list[ClaimNode]) -> list[ClaimNode]:
        if len(value) < 1:
            raise ValueError("ClaimBlock must contain at least one claim")
        return value


class BundleNode(LimnalisModel):
    node: Literal["Bundle"] = "Bundle"
    id: str
    frame: FrameOrPatternNode
    evaluators: list[EvaluatorNode]
    resolutionPolicy: ResolutionPolicyNode
    time: TimeCtxNode | None = None
    bindings: list[BindingNode] = Field(default_factory=list)
    facetPolicies: list[FrameFacetPolicyNode] = Field(default_factory=list)
    assumptions: list[AssumptionNode] = Field(default_factory=list)
    baselines: list[BaselineNode] = Field(default_factory=list)
    evidence: list[EvidenceNode] = Field(default_factory=list)
    evidenceRelations: list[EvidenceRelationNode] = Field(default_factory=list)
    anchors: list[AnchorNode] = Field(default_factory=list)
    jointAdequacies: list[JointAdequacyNode] = Field(default_factory=list)
    bridges: list[BridgeNode] = Field(default_factory=list)
    claimBlocks: list[ClaimBlockNode]

    @field_validator("evaluators", "claimBlocks")
    @classmethod
    def _non_empty_lists(cls, value: list[Any], info: ValidationInfo) -> list[Any]:
        if len(value) < 1:
            raise ValueError(f"{info.field_name} must contain at least one item")
        return value


# Resolve forward references
_types_namespace = {
    "ArgNode": ArgNode,
    "ExprNode": ExprNode,
    "TermNode": TermNode,
    "FramePatternOrExprNode": FramePatternOrExprNode,
    "FrameOrPatternNode": FrameOrPatternNode,
    "AnchorTermNode": AnchorTermNode,
    "CriterionSpecNode": CriterionSpecNode,
}
for _model in [
    ListTermNode,
    PredicateExprNode,
    LogicalExprNode,
    CausalExprNode,
    DynamicExprNode,
    EmergenceExprNode,
    DeclarationExprNode,
    JudgedExprNode,
    AssumptionNode,
    CriterionExprNode,
    BaselineNode,
    AnchorTermExprNode,
    AnchorNode,
    ClaimNode,
    ClaimBlockNode,
    BundleNode,
]:
    _model.model_rebuild(_types_namespace=_types_namespace)


__all__ = [
    "AdequacyAssessmentNode",
    "AnchorNode",
    "AnchorTermNode",
    "ArgNode",
    "AssumptionNode",
    "BaselineNode",
    "BaselineRefTermNode",
    "BindingNode",
    "BooleanTermNode",
    "BridgeNode",
    "BundleNode",
    "CausalExprNode",
    "ClaimBlockNode",
    "ClaimNode",
    "CriterionSpecNode",
    "DeclarationExprNode",
    "DynamicExprNode",
    "EmergenceExprNode",
    "EvaluatorNode",
    "EvidenceNode",
    "EvidenceRelationNode",
    "ExprNode",
    "FacetValueMap",
    "FrameFacetPolicyNode",
    "FrameNode",
    "FrameOrPatternNode",
    "FramePatternNode",
    "JointAdequacyNode",
    "JudgedExprNode",
    "ListTermNode",
    "LogicalExprNode",
    "NoteExprNode",
    "NullTermNode",
    "NumberTermNode",
    "PredicateExprNode",
    "ResolutionPolicyNode",
    "StringTermNode",
    "SymbolTermNode",
    "TermNode",
    "TimeCtxNode",
    "TransportNode",
    "UnboundRefTermNode",
    "UriTermNode",
]

