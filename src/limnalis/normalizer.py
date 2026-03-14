from __future__ import annotations

import ast as py_ast
import json
import re
from dataclasses import dataclass, field
from typing import Any

from lark import Token, Tree
from pydantic import ValidationError

from .diagnostics import Diagnostic, SourcePosition, SourceSpan
from .models.ast import (
    AdequacyAssessmentNode,
    AnchorNode,
    AnchorTermClaimNode,
    AnchorTermExprNode,
    AnchorTermSymbolNode,
    BaselineNode,
    BaselineRefTermNode,
    BooleanTermNode,
    BridgeNode,
    BundleNode,
    CausalExprNode,
    ClaimBlockNode,
    ClaimNode,
    CriterionExprNode,
    CriterionRefNode,
    DeclarationExprNode,
    DynamicExprNode,
    EmergenceExprNode,
    EvaluatorNode,
    EvidenceNode,
    EvidenceRelationNode,
    FacetValueMap,
    FrameNode,
    FramePatternNode,
    JointAdequacyNode,
    JudgedExprNode,
    ListTermNode,
    LogicalExprNode,
    NoteExprNode,
    NullTermNode,
    NumberTermNode,
    PredicateExprNode,
    ResolutionPolicyNode,
    StringTermNode,
    SymbolTermNode,
    TransportNode,
    UriTermNode,
)


@dataclass(slots=True)
class NormalizationResult:
    canonical_ast: BundleNode | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class NormalizationError(ValueError):
    """Raised when a parsed surface tree cannot be normalized into the canonical AST."""


class Normalizer:
    """Canonical AST normalizer for the current authored surface subset."""

    _CLAIM_BLOCK_STRATA = {"local", "systemic", "meta"}
    _CLAIM_METADATA_KEYWORDS = {
        "annotations",
        "refs",
        "requires",
        "semantic_requirements",
        "uses",
    }
    _FRAME_FIELD_MAP = {
        "system": "system",
        "namespace": "namespace",
        "scale": "scale",
        "task": "task",
        "regime": "regime",
        "observer": "observer",
        "version": "version",
        "facet_policy": "facetPolicy",
    }
    _EVALUATOR_FIELD_MAP = {
        "kind": "kind",
        "binding": "binding",
        "role": "role",
        "evidence_policy": "evidencePolicy",
        "inference_policy": "inferencePolicy",
        "provenance_policy": "provenancePolicy",
    }
    _RESOLUTION_FIELD_MAP = {
        "kind": "kind",
        "members": "members",
        "order": "order",
        "binding": "binding",
    }
    _LOGICAL_OPERATORS = {
        "AND": "and",
        "IFF": "iff",
        "IMPLIES": "implies",
        "OR": "or",
    }
    _CAUSAL_RE = re.compile(r"^=>\[(?P<mode>obs|do)(?::(?P<intervention>.+))?\]$")
    _NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

    def normalize(self, raw_tree: Any) -> NormalizationResult:
        start = self._expect_tree(raw_tree, "start")
        if len(start.children) != 1:
            raise NormalizationError("expected a single bundle at the parse root")

        diagnostics: list[dict[str, Any]] = []
        bundle = self._normalize_bundle(self._expect_tree(start.children[0], "bundle"), diagnostics)
        return NormalizationResult(canonical_ast=bundle, diagnostics=diagnostics)

    def _normalize_bundle(
        self, bundle_tree: Tree[Any], diagnostics: list[dict[str, Any]]
    ) -> BundleNode:
        if len(bundle_tree.children) != 2:
            raise NormalizationError("bundle node must contain an id and a body block")

        bundle_id = self._as_text(bundle_tree.children[0])
        body = self._expect_tree(bundle_tree.children[1], "block")

        frame: FrameNode | FramePatternNode | None = None
        evaluators: list[EvaluatorNode] = []
        resolution_policies: list[tuple[ResolutionPolicyNode, Tree[Any]]] = []
        baselines: list[BaselineNode] = []
        evidence: list[EvidenceNode] = []
        evidence_relations: list[EvidenceRelationNode] = []
        anchors: list[AnchorNode] = []
        joint_adequacies: list[JointAdequacyNode] = []
        bridges: list[BridgeNode] = []
        claim_blocks: list[ClaimBlockNode] = []
        block_counts = {stratum: 0 for stratum in self._CLAIM_BLOCK_STRATA}

        for item in body.children:
            tree_item = self._expect_tree(item)
            if tree_item.data == "statement":
                frame = self._normalize_top_level_statement(tree_item, frame)
                continue

            if tree_item.data != "nested_block":
                raise NormalizationError(f"unsupported top-level item '{tree_item.data}'")

            head_tokens, block_tree = self._split_nested_block(tree_item)
            head = head_tokens[0]

            if head == "frame":
                self._ensure_not_set(frame, "frame")
                frame = self._normalize_frame_block(block_tree)
            elif head == "evaluator":
                evaluators.append(
                    self._normalize_evaluator(
                        head_tokens,
                        block_tree,
                        diagnostics,
                        source_tree=tree_item,
                    )
                )
            elif head == "resolution_policy":
                resolution_policies.append(
                    (self._normalize_resolution_policy(head_tokens, block_tree), tree_item)
                )
            elif head == "baseline":
                baselines.append(self._normalize_baseline(head_tokens, block_tree))
            elif head == "evidence":
                evidence.append(self._normalize_evidence(head_tokens, block_tree))
            elif head == "evidence_relation":
                evidence_relations.append(
                    self._normalize_evidence_relation(head_tokens, block_tree)
                )
            elif head in {"anchor", "fictional_anchor"}:
                anchors.append(self._normalize_anchor(head_tokens, block_tree, diagnostics))
            elif head == "joint_adequacy":
                joint_adequacies.append(
                    self._normalize_joint_adequacy(head_tokens, block_tree, diagnostics)
                )
            elif head == "bridge":
                bridges.append(
                    self._normalize_bridge(
                        head_tokens,
                        block_tree,
                        diagnostics,
                        source_tree=tree_item,
                    )
                )
            elif head in self._CLAIM_BLOCK_STRATA:
                block_counts[head] += 1
                claim_blocks.append(
                    self._normalize_claim_block(head, block_counts[head], block_tree)
                )
            else:
                raise NormalizationError(
                    f"normalization for top-level block '{head}' is not implemented yet"
                )

        if frame is None:
            raise NormalizationError("bundle is missing a frame declaration")
        if not evaluators:
            raise NormalizationError("bundle must define at least one evaluator")
        if not claim_blocks:
            raise NormalizationError("bundle must define at least one claim block")

        resolution_policy = self._select_bundle_resolution_policy(
            bundle_id,
            bundle_tree,
            resolution_policies,
            evaluators,
            diagnostics,
        )

        return self._build_model(
            BundleNode,
            f"bundle '{bundle_id}'",
            node="Bundle",
            id=bundle_id,
            frame=frame,
            evaluators=evaluators,
            resolutionPolicy=resolution_policy,
            baselines=baselines,
            evidence=evidence,
            evidenceRelations=evidence_relations,
            anchors=anchors,
            jointAdequacies=joint_adequacies,
            bridges=bridges,
            claimBlocks=claim_blocks,
        )

    def _normalize_top_level_statement(
        self, statement_tree: Tree[Any], frame: FrameNode | FramePatternNode | None
    ) -> FrameNode | FramePatternNode:
        tokens = self._statement_tokens(statement_tree)
        if not tokens:
            raise NormalizationError("empty top-level statement")
        if tokens[0] != "frame":
            raise NormalizationError(
                f"unsupported top-level statement '{self._join_tokens(tokens)}'"
            )
        self._ensure_not_set(frame, "frame")
        if len(tokens) != 2:
            raise NormalizationError("frame shorthand statements must contain exactly one value")
        return self._normalize_frame_shorthand(tokens[1])

    def _normalize_frame_shorthand(self, token: str) -> FramePatternNode:
        if not token.startswith("@") or "::" not in token or ":" not in token:
            raise NormalizationError(f"invalid frame shorthand '{token}'")
        body = token[1:]
        system, tail = body.split(":", 1)
        namespace, regime = tail.split("::", 1)
        if not system or not namespace or not regime:
            raise NormalizationError(f"invalid frame shorthand '{token}'")
        facets = self._build_model(
            FacetValueMap,
            f"frame shorthand '{token}'",
            system=system,
            namespace=namespace,
            regime=regime,
        )
        return self._build_model(
            FramePatternNode,
            f"frame shorthand '{token}'",
            node="FramePattern",
            facets=facets,
        )

    def _normalize_frame_block(self, block_tree: Tree[Any]) -> FrameNode:
        fields = self._collect_flat_fields(block_tree, "frame", self._FRAME_FIELD_MAP)
        payload = {
            self._FRAME_FIELD_MAP[key]: self._parse_scalar_tokens(value_tokens)
            for key, value_tokens in fields.items()
        }
        return self._build_model(FrameNode, "frame block", node="Frame", **payload)

    def _normalize_evaluator(
        self,
        head_tokens: list[str],
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
        *,
        source_tree: Tree[Any],
    ) -> EvaluatorNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "evaluator blocks must be declared as 'evaluator <id> { ... }'"
            )
        evaluator_id = head_tokens[1]
        fields = self._collect_flat_fields(block_tree, "evaluator", self._EVALUATOR_FIELD_MAP)
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            value = self._parse_scalar_tokens(value_tokens)
            target = self._EVALUATOR_FIELD_MAP[key]
            if key == "kind" and value == "audit":
                value = "process"
                self._append_diagnostic(
                    diagnostics,
                    severity="warning",
                    subject=evaluator_id,
                    code="evaluator_kind_canonicalized",
                    message=(
                        "Canonicalized authored evaluator kind 'audit' to canonical "
                        "AST kind 'process' because schema v0.2.2 does not admit "
                        "'audit' as an Evaluator.kind value."
                    ),
                    source_node=source_tree,
                )
            payload[target] = value
        return self._build_model(
            EvaluatorNode,
            f"evaluator '{evaluator_id}'",
            node="Evaluator",
            id=evaluator_id,
            **payload,
        )

    def _normalize_resolution_policy(
        self, head_tokens: list[str], block_tree: Tree[Any]
    ) -> ResolutionPolicyNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "resolution_policy blocks must be declared as 'resolution_policy <id> { ... }'"
            )
        policy_id = head_tokens[1]
        fields = self._collect_flat_fields(
            block_tree,
            "resolution_policy",
            self._RESOLUTION_FIELD_MAP,
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            target = self._RESOLUTION_FIELD_MAP[key]
            if key in {"members", "order"}:
                payload[target] = self._parse_list(self._join_tokens(value_tokens))
            else:
                payload[target] = self._parse_scalar_tokens(value_tokens)
        return self._build_model(
            ResolutionPolicyNode,
            f"resolution_policy '{policy_id}'",
            node="ResolutionPolicy",
            id=policy_id,
            **payload,
        )

    def _normalize_baseline(self, head_tokens: list[str], block_tree: Tree[Any]) -> BaselineNode:
        if len(head_tokens) != 2:
            raise NormalizationError("baseline blocks must be declared as 'baseline <id> { ... }'")
        baseline_id = head_tokens[1]
        fields = self._collect_flat_fields(
            block_tree,
            "baseline",
            {
                "kind": "kind",
                "criterion": "criterion",
                "frame": "frame",
                "evaluation_mode": "evaluationMode",
            },
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            if key == "criterion":
                payload["criterion"] = self._parse_criterion(value_tokens)
            elif key == "frame":
                payload["frame"] = self._parse_frame_or_pattern(self._join_tokens(value_tokens))
            elif key == "evaluation_mode":
                payload["evaluationMode"] = self._parse_scalar_tokens(value_tokens)
            else:
                payload["kind"] = self._parse_scalar_tokens(value_tokens)
        return self._build_model(
            BaselineNode,
            f"baseline '{baseline_id}'",
            node="Baseline",
            id=baseline_id,
            **payload,
        )

    def _normalize_evidence(self, head_tokens: list[str], block_tree: Tree[Any]) -> EvidenceNode:
        if len(head_tokens) != 2:
            raise NormalizationError("evidence blocks must be declared as 'evidence <id> { ... }'")
        evidence_id = head_tokens[1]
        fields = self._collect_flat_fields(
            block_tree,
            "evidence",
            {
                "kind": "kind",
                "binding": "binding",
                "observer": "observer",
                "completeness": "completeness",
                "internal_conflict": "internalConflict",
            },
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            target = {
                "kind": "kind",
                "binding": "binding",
                "observer": "observer",
                "completeness": "completeness",
                "internal_conflict": "internalConflict",
            }[key]
            if key in {"completeness", "internal_conflict"}:
                payload[target] = self._parse_float(self._join_tokens(value_tokens), key)
            else:
                payload[target] = self._parse_scalar_tokens(value_tokens)
        return self._build_model(
            EvidenceNode,
            f"evidence '{evidence_id}'",
            node="Evidence",
            id=evidence_id,
            **payload,
        )

    def _normalize_evidence_relation(
        self, head_tokens: list[str], block_tree: Tree[Any]
    ) -> EvidenceRelationNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "evidence_relation blocks must be declared as 'evidence_relation <id> { ... }'"
            )
        relation_id = head_tokens[1]
        fields = self._collect_flat_fields(
            block_tree,
            "evidence_relation",
            {"lhs": "lhs", "rhs": "rhs", "kind": "kind", "score": "score", "refs": "refs"},
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            if key == "score":
                payload["score"] = self._parse_float(self._join_tokens(value_tokens), "score")
            elif key == "refs":
                payload["refs"] = self._parse_list(self._join_tokens(value_tokens))
            else:
                payload[key] = self._parse_scalar_tokens(value_tokens)
        return self._build_model(
            EvidenceRelationNode,
            f"evidence_relation '{relation_id}'",
            node="EvidenceRelation",
            id=relation_id,
            **payload,
        )

    def _normalize_anchor(
        self,
        head_tokens: list[str],
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
    ) -> AnchorNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "anchor blocks must be declared as 'anchor <id> { ... }' or "
                "'fictional_anchor <id> { ... }'"
            )
        anchor_kind = head_tokens[0]
        anchor_id = head_tokens[1]
        payload: dict[str, Any] = {}
        adequacy: list[AdequacyAssessmentNode] = []

        for child in block_tree.children:
            tree = self._expect_tree(child)
            if tree.data == "statement":
                key, value_tokens = self._split_key_value(tree, "anchor")
                if key == "term":
                    self._ensure_field_absent(payload, "term", "anchor", key)
                    payload["term"] = self._parse_anchor_term(value_tokens)
                elif key == "subtype":
                    self._ensure_field_absent(payload, "subtype", "anchor", key)
                    payload["subtype"] = self._parse_scalar_tokens(value_tokens)
                elif key == "status":
                    self._ensure_field_absent(payload, "status", "anchor", key)
                    payload["status"] = self._parse_scalar_tokens(value_tokens)
                elif key == "adequacy_policy":
                    self._ensure_field_absent(payload, "adequacyPolicy", "anchor", key)
                    payload["adequacyPolicy"] = self._parse_scalar_tokens(value_tokens)
                elif key == "requires_joint_with":
                    self._ensure_field_absent(payload, "requiresJointWith", "anchor", key)
                    payload["requiresJointWith"] = self._parse_list(self._join_tokens(value_tokens))
                else:
                    raise NormalizationError(
                        f"normalization for '{key}' inside anchor blocks is not implemented yet"
                    )
                continue

            head, nested_block = self._split_nested_block(tree)
            block_head = head[0]
            if block_head not in {"adequacy", "assessment"}:
                raise NormalizationError(
                    "normalization for nested block "
                    f"'{self._join_tokens(head)}' inside anchor blocks is not implemented yet"
                )
            adequacy.append(
                self._normalize_adequacy_assessment(
                    parent_kind="anchor",
                    parent_id=anchor_id,
                    block_label="adequacy",
                    index=len(adequacy) + 1,
                    block_tree=nested_block,
                    diagnostics=diagnostics,
                    source_tree=tree,
                    inline_id=self._extract_nested_block_id(head, block_head, "anchor"),
                )
            )

        if anchor_kind == "fictional_anchor" and "subtype" not in payload:
            payload["subtype"] = "idealization"
            self._append_diagnostic(
                diagnostics,
                severity="info",
                subject=anchor_id,
                code="fictional_anchor_subtype_defaulted",
                message=(
                    f"Defaulted fictional_anchor '{anchor_id}' subtype to 'idealization' "
                    "because the authored block omitted an explicit subtype."
                ),
                source_node=None,
            )

        return self._build_model(
            AnchorNode,
            f"{anchor_kind} '{anchor_id}'",
            node="Anchor",
            id=anchor_id,
            adequacy=adequacy,
            **payload,
        )

    def _normalize_joint_adequacy(
        self,
        head_tokens: list[str],
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
    ) -> JointAdequacyNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "joint_adequacy blocks must be declared as 'joint_adequacy <id> { ... }'"
            )
        joint_id = head_tokens[1]
        payload: dict[str, Any] = {}
        assessments: list[AdequacyAssessmentNode] = []

        for child in block_tree.children:
            tree = self._expect_tree(child)
            if tree.data == "statement":
                key, value_tokens = self._split_key_value(tree, "joint_adequacy")
                if key == "anchors":
                    self._ensure_field_absent(payload, "anchors", "joint_adequacy", key)
                    payload["anchors"] = self._parse_list(self._join_tokens(value_tokens))
                elif key == "adequacy_policy":
                    self._ensure_field_absent(payload, "adequacyPolicy", "joint_adequacy", key)
                    payload["adequacyPolicy"] = self._parse_scalar_tokens(value_tokens)
                else:
                    raise NormalizationError(
                        "normalization for "
                        f"'{key}' inside joint_adequacy blocks is not implemented yet"
                    )
                continue

            head, nested_block = self._split_nested_block(tree)
            if head != ["assessment"]:
                raise NormalizationError(
                    "normalization for nested block "
                    f"'{self._join_tokens(head)}' inside joint_adequacy blocks "
                    "is not implemented yet"
                )
            assessments.append(
                self._normalize_adequacy_assessment(
                    parent_kind="joint_adequacy",
                    parent_id=joint_id,
                    block_label="assessment",
                    index=len(assessments) + 1,
                    block_tree=nested_block,
                    diagnostics=diagnostics,
                    source_tree=tree,
                )
            )

        return self._build_model(
            JointAdequacyNode,
            f"joint_adequacy '{joint_id}'",
            node="JointAdequacy",
            id=joint_id,
            assessments=assessments,
            **payload,
        )

    def _normalize_bridge(
        self,
        head_tokens: list[str],
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
        *,
        source_tree: Tree[Any],
    ) -> BridgeNode:
        if len(head_tokens) != 2:
            raise NormalizationError("bridge blocks must be declared as 'bridge <id> { ... }'")
        bridge_id = head_tokens[1]
        payload: dict[str, Any] = {}
        transport: TransportNode | None = None

        for child in block_tree.children:
            tree = self._expect_tree(child)
            if tree.data == "statement":
                key, value_tokens = self._split_key_value(tree, "bridge")
                value_text = self._join_tokens(value_tokens)
                if key == "from":
                    self._ensure_field_absent(payload, "from_", "bridge", key)
                    payload["from_"] = self._parse_frame_pattern(value_text)
                elif key == "to":
                    self._ensure_field_absent(payload, "to", "bridge", key)
                    payload["to"] = self._parse_frame_pattern(value_text)
                elif key == "via":
                    self._ensure_field_absent(payload, "via", "bridge", key)
                    payload["via"] = self._parse_scalar_tokens(value_tokens)
                elif key in {"preserve", "lose", "gain", "risk"}:
                    self._ensure_field_absent(payload, key, "bridge", key)
                    payload[key] = self._parse_list(value_text)
                else:
                    raise NormalizationError(
                        f"normalization for '{key}' inside bridge blocks is not implemented yet"
                    )
                continue

            head, nested_block = self._split_nested_block(tree)
            if head != ["transport"]:
                raise NormalizationError(
                    "normalization for nested block "
                    f"'{self._join_tokens(head)}' inside bridge blocks is not implemented yet"
                )
            if transport is not None:
                raise NormalizationError("bridge blocks may only contain one transport block")
            transport = self._normalize_transport(nested_block)

        if transport is None:
            transport = self._build_model(
                TransportNode,
                f"bridge '{bridge_id}' synthesized transport",
                node="Transport",
                mode="metadata_only",
            )
            self._append_diagnostic(
                diagnostics,
                severity="info",
                subject=bridge_id,
                code="bridge_transport_defaulted",
                message=(
                    "Synthesized Transport(mode='metadata_only') for bridge "
                    f"'{bridge_id}' because the authored bridge omitted a transport block."
                ),
                source_node=source_tree,
            )

        return self._build_model(
            BridgeNode,
            f"bridge '{bridge_id}'",
            node="Bridge",
            id=bridge_id,
            transport=transport,
            **payload,
        )

    def _normalize_transport(self, block_tree: Tree[Any]) -> TransportNode:
        fields = self._collect_flat_fields(
            block_tree,
            "transport",
            {
                "mode": "mode",
                "claim_map": "claimMap",
                "truth_policy": "truthPolicy",
                "preconditions": "preconditions",
                "dst_evaluators": "dstEvaluators",
                "dst_resolution_policy": "dstResolutionPolicy",
            },
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            target = {
                "mode": "mode",
                "claim_map": "claimMap",
                "truth_policy": "truthPolicy",
                "preconditions": "preconditions",
                "dst_evaluators": "dstEvaluators",
                "dst_resolution_policy": "dstResolutionPolicy",
            }[key]
            if key in {"preconditions", "dst_evaluators"}:
                payload[target] = self._parse_list(self._join_tokens(value_tokens))
            else:
                payload[target] = self._parse_scalar_tokens(value_tokens)
        return self._build_model(TransportNode, "transport block", node="Transport", **payload)

    def _normalize_adequacy_assessment(
        self,
        *,
        parent_kind: str,
        parent_id: str,
        block_label: str,
        index: int,
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
        source_tree: Tree[Any],
        inline_id: str | None = None,
    ) -> AdequacyAssessmentNode:
        fields = self._collect_flat_fields(
            block_tree,
            block_label,
            {
                "id": "id",
                "task": "task",
                "producer": "producer",
                "score": "score",
                "threshold": "threshold",
                "method": "method",
                "basis": "basis",
            },
        )
        payload: dict[str, Any] = {}
        for key, value_tokens in fields.items():
            value_text = self._join_tokens(value_tokens)
            if key in {"id", "task", "producer", "method"}:
                payload[key] = self._parse_scalar_tokens(value_tokens)
            elif key == "score":
                payload["score"] = self._parse_optional_score(value_text)
            elif key == "threshold":
                payload["threshold"] = self._parse_float(value_text, "threshold")
            elif key == "basis":
                payload["basis"] = self._parse_list(value_text)

        if inline_id is not None:
            if "id" in payload and payload["id"] != inline_id:
                raise NormalizationError(
                    f"{block_label} block for {parent_kind} '{parent_id}' defines "
                    f"conflicting ids '{inline_id}' and '{payload['id']}'"
                )
            payload["id"] = inline_id

        if "id" not in payload:
            synth_id = f"{parent_id}#{block_label}{index}"
            payload["id"] = synth_id
            self._append_diagnostic(
                diagnostics,
                severity="info",
                subject=parent_id,
                code=f"{block_label}_id_synthesized",
                message=(
                    f"Synthesized {block_label} id '{synth_id}' for {parent_kind} "
                    f"'{parent_id}' because the authored block omitted an explicit id."
                ),
                source_node=source_tree,
            )

        return self._build_model(
            AdequacyAssessmentNode,
            f"{parent_kind} '{parent_id}' {block_label} '{payload['id']}'",
            node="AdequacyAssessment",
            **payload,
        )

    def _normalize_claim_block(
        self, stratum: str, index: int, block_tree: Tree[Any]
    ) -> ClaimBlockNode:
        claims = [
            self._normalize_claim(self._expect_tree(item, "statement"))
            for item in block_tree.children
        ]
        return ClaimBlockNode(
            node="ClaimBlock",
            id=f"{stratum}#{index}",
            stratum=stratum,
            claims=claims,
        )

    def _normalize_claim(self, statement_tree: Tree[Any]) -> ClaimNode:
        tokens = self._statement_tokens(statement_tree)
        if len(tokens) < 2:
            raise NormalizationError("claim statements must include an id and an expression")
        if not tokens[0].endswith(":"):
            raise NormalizationError(f"claim statement must start with '<id>:'; got '{tokens[0]}'")

        claim_id = tokens[0][:-1]
        expr_tokens, metadata = self._split_claim_tokens(claim_id, tokens[1:])
        expr = self._normalize_claim_expr(expr_tokens)
        kind = self._claim_kind_for_expr(expr)
        return self._build_model(
            ClaimNode,
            f"claim '{claim_id}'",
            node="Claim",
            id=claim_id,
            kind=kind,
            expr=expr,
            usesAnchors=metadata["usesAnchors"],
            semanticRequirements=metadata["semanticRequirements"],
            refs=metadata["refs"],
            annotations=metadata["annotations"],
        )

    def _split_claim_tokens(
        self, claim_id: str, tokens: list[str]
    ) -> tuple[list[str], dict[str, Any]]:
        metadata_index = next(
            (index for index, token in enumerate(tokens) if token in self._CLAIM_METADATA_KEYWORDS),
            len(tokens),
        )
        expr_tokens = tokens[:metadata_index]
        metadata_tokens = tokens[metadata_index:]
        metadata = {
            "usesAnchors": [],
            "semanticRequirements": [],
            "refs": [],
            "annotations": {},
        }

        index = 0
        while index < len(metadata_tokens):
            keyword = metadata_tokens[index]
            if index + 1 >= len(metadata_tokens):
                raise NormalizationError(
                    f"claim metadata keyword '{keyword}' in claim '{claim_id}' is missing a value"
                )
            value_text = metadata_tokens[index + 1]
            if keyword == "refs":
                self._ensure_field_absent(metadata, "refs", f"claim '{claim_id}'", keyword)
                metadata["refs"] = self._parse_list(value_text)
            elif keyword == "uses":
                self._ensure_field_absent(
                    metadata,
                    "usesAnchors",
                    f"claim '{claim_id}'",
                    keyword,
                )
                metadata["usesAnchors"] = self._parse_list(value_text)
            elif keyword in {"requires", "semantic_requirements"}:
                self._ensure_field_absent(
                    metadata,
                    "semanticRequirements",
                    f"claim '{claim_id}'",
                    keyword,
                )
                metadata["semanticRequirements"] = self._parse_list(value_text)
            elif keyword == "annotations":
                self._ensure_field_absent(
                    metadata,
                    "annotations",
                    f"claim '{claim_id}'",
                    keyword,
                )
                metadata["annotations"] = self._parse_inline_object(value_text)
            else:
                raise NormalizationError(
                    f"unsupported trailing claim token '{keyword}' in claim '{claim_id}'"
                )
            index += 2

        return expr_tokens, metadata

    def _normalize_claim_expr(self, tokens: list[str]) -> Any:
        if not tokens:
            raise NormalizationError("claim expression is empty")
        if tokens[0] == "note":
            note_text = self._join_tokens(tokens[1:]).strip()
            if not note_text:
                raise NormalizationError("note expressions require text")
            return self._build_model(
                NoteExprNode,
                "note expression",
                node="NoteExpr",
                text=self._parse_string_literal(note_text),
            )
        if tokens[0] == "declare":
            return self._parse_declaration(tokens)
        if "EMRG" in tokens:
            return self._parse_emergence(tokens)

        causal_index = self._find_causal_index(tokens)
        if causal_index is not None:
            return self._parse_causal(tokens, causal_index)

        if "judged_by" in tokens:
            index = tokens.index("judged_by")
            if index == 0 or index == len(tokens) - 1:
                raise NormalizationError(
                    "judged_by expressions require both an inner expression and a criterion"
                )
            inner = self._parse_expr_text(self._join_tokens(tokens[:index]))
            criterion_ref = self._parse_scalar_text(self._join_tokens(tokens[index + 1 :]).strip())
            if not criterion_ref:
                raise NormalizationError("judged_by expressions require a criterion reference")
            return self._build_model(
                JudgedExprNode,
                "judged expression",
                node="JudgedExpr",
                expr=inner,
                criterionRef=criterion_ref,
            )

        return self._parse_expr_text(self._join_tokens(tokens))

    def _parse_declaration(self, tokens: list[str]) -> DeclarationExprNode:
        if "as" not in tokens:
            raise NormalizationError("declaration expressions must contain an 'as' clause")
        as_index = tokens.index("as")
        if as_index <= 1:
            raise NormalizationError("declaration expressions require a term before 'as'")
        within_index = tokens.index("within") if "within" in tokens else None
        declared_as_end = within_index if within_index is not None else len(tokens)
        declared_as_tokens = tokens[as_index + 1 : declared_as_end]
        if not declared_as_tokens:
            raise NormalizationError("declaration expressions require a declared kind after 'as'")

        within = None
        if within_index is not None:
            within_tokens = tokens[within_index + 1 :]
            if not within_tokens:
                raise NormalizationError("declaration expressions require a value after 'within'")
            within_text = self._join_tokens(within_tokens)
            if within_text.startswith("@"):
                within = self._parse_frame_pattern(within_text)
            else:
                within = self._parse_expr_text(within_text)

        return self._build_model(
            DeclarationExprNode,
            "declaration expression",
            node="DeclarationExpr",
            term=self._parse_term_text(self._join_tokens(tokens[1:as_index])),
            declaredAs=self._parse_scalar_text(self._join_tokens(declared_as_tokens)),
            within=within,
        )

    def _parse_causal(self, tokens: list[str], index: int) -> CausalExprNode:
        marker = tokens[index]
        match = self._CAUSAL_RE.fullmatch(marker)
        if match is None:
            raise NormalizationError(f"invalid causal marker '{marker}'")
        lhs_tokens = tokens[:index]
        rhs_tokens = tokens[index + 1 :]
        if not lhs_tokens or not rhs_tokens:
            raise NormalizationError("causal expressions require both lhs and rhs expressions")

        intervention = match.group("intervention")
        parsed_intervention: str | Any | None = None
        if intervention is not None:
            parsed_intervention = intervention.strip() or None
            if parsed_intervention and (
                self._looks_like_call(parsed_intervention)
                or self._is_wrapped_expression(parsed_intervention)
            ):
                parsed_intervention = self._parse_expr_text(parsed_intervention)

        return self._build_model(
            CausalExprNode,
            "causal expression",
            node="CausalExpr",
            mode=match.group("mode"),
            lhs=self._parse_expr_text(self._join_tokens(lhs_tokens)),
            rhs=self._parse_expr_text(self._join_tokens(rhs_tokens)),
            intervention=parsed_intervention,
        )

    def _parse_emergence(self, tokens: list[str]) -> EmergenceExprNode:
        emrg_index = tokens.index("EMRG")
        property_tokens = tokens[:emrg_index]
        if not property_tokens:
            raise NormalizationError("emergence expressions require a property before 'EMRG'")
        tail = tokens[emrg_index + 1 :]
        if not tail or tail[0] != "when":
            raise NormalizationError("emergence expressions must include 'when' after 'EMRG'")
        clauses = tail[1:]
        while_index = clauses.index("while") if "while" in clauses else None
        until_index = clauses.index("until") if "until" in clauses else None
        clause_starts = [index for index in [while_index, until_index] if index is not None]
        onset_end = min(clause_starts) if clause_starts else len(clauses)
        onset_tokens = clauses[:onset_end]
        if not onset_tokens:
            raise NormalizationError("emergence expressions require an onset clause")

        persists_while = None
        if while_index is not None:
            while_end = (
                until_index
                if until_index is not None and until_index > while_index
                else len(clauses)
            )
            while_tokens = clauses[while_index + 1 : while_end]
            if not while_tokens:
                raise NormalizationError("'while' clauses must include an expression")
            persists_while = self._parse_expr_text(self._join_tokens(while_tokens))

        dissolves_when = None
        if until_index is not None:
            until_tokens = clauses[until_index + 1 :]
            if not until_tokens:
                raise NormalizationError("'until' clauses must include an expression")
            dissolves_when = self._parse_expr_text(self._join_tokens(until_tokens))

        return self._build_model(
            EmergenceExprNode,
            "emergence expression",
            node="EmergenceExpr",
            property=self._parse_expr_text(self._join_tokens(property_tokens)),
            onset=self._parse_dynamic(onset_tokens),
            persistsWhile=persists_while,
            dissolvesWhen=dissolves_when,
        )

    def _parse_dynamic(self, tokens: list[str]) -> DynamicExprNode | Any:
        if "-->" not in tokens:
            return self._parse_expr_text(self._join_tokens(tokens))
        index = tokens.index("-->")
        subject_tokens = tokens[:index]
        target_tokens = tokens[index + 1 :]
        if not subject_tokens or not target_tokens:
            raise NormalizationError("dynamic authored forms require both a subject and target")
        return self._build_model(
            DynamicExprNode,
            "dynamic expression",
            node="DynamicExpr",
            op="approaches",
            subject=self._parse_term_text(self._join_tokens(subject_tokens)),
            target=self._parse_arg_text(self._join_tokens(target_tokens)),
        )

    def _parse_expr_text(self, text: str) -> Any:
        text = text.strip()
        if not text:
            raise NormalizationError("expression text is empty")

        if self._is_wrapped_expression(text):
            inner = text[1:-1].strip()
            if inner.upper().startswith("NOT "):
                return LogicalExprNode(
                    node="LogicalExpr",
                    op="not",
                    args=[self._parse_expr_text(inner[4:].strip())],
                )
            for token, op in self._LOGICAL_OPERATORS.items():
                parts = self._split_top_level(inner, f" {token} ")
                if len(parts) > 1:
                    return LogicalExprNode(
                        node="LogicalExpr",
                        op=op,
                        args=[self._parse_expr_text(part) for part in parts],
                    )
            return self._parse_expr_text(inner)

        if self._looks_like_call(text):
            name, args_text = text.split("(", 1)
            name = name.strip()
            inner = args_text[:-1].strip()
            args = (
                []
                if not inner
                else [self._parse_arg_text(part) for part in self._split_args(inner)]
            )
            return PredicateExprNode(node="PredicateExpr", name=name, args=args)

        return PredicateExprNode(node="PredicateExpr", name=text, args=[])

    def _parse_arg_text(self, text: str) -> Any:
        text = text.strip()
        if not text:
            raise NormalizationError("predicate arguments must not be empty")
        if self._is_wrapped_expression(text) or self._looks_like_call(text):
            return self._parse_expr_text(text)
        if text.startswith("[") and text.endswith("]"):
            return self._build_model(
                ListTermNode,
                "list term",
                node="ListTerm",
                items=[self._parse_arg_text(part) for part in self._parse_list(text)],
            )
        if text.startswith("|") and text.endswith("|"):
            inner = text[1:-1].strip()
            kind, ref_id = inner.split(":", 1) if ":" in inner else ("", inner)
            ref_id = ref_id.strip()
            if kind != "0" or not ref_id:
                raise NormalizationError(f"invalid baseline reference '{text}'")
            return self._build_model(
                BaselineRefTermNode,
                f"baseline reference '{text}'",
                node="BaselineRefTerm",
                id=ref_id,
            )
        if text.startswith(('"', "'")):
            return self._build_model(
                StringTermNode,
                "string term",
                node="StringTerm",
                value=self._parse_string_literal(text),
            )
        lowered = text.lower()
        if lowered == "true":
            return self._build_model(
                BooleanTermNode, "boolean term", node="BooleanTerm", value=True
            )
        if lowered == "false":
            return self._build_model(
                BooleanTermNode, "boolean term", node="BooleanTerm", value=False
            )
        if lowered == "null":
            return self._build_model(NullTermNode, "null term", node="NullTerm")
        if self._NUMBER_RE.fullmatch(text):
            return self._build_model(
                NumberTermNode,
                "number term",
                node="NumberTerm",
                value=float(text),
            )
        if "://" in text:
            return self._build_model(UriTermNode, "uri term", node="UriTerm", value=text)
        return self._build_model(SymbolTermNode, "symbol term", node="SymbolTerm", value=text)

    def _parse_term_text(self, text: str) -> Any:
        term = self._parse_arg_text(text)
        if term.node in {
            "PredicateExpr",
            "LogicalExpr",
            "CausalExpr",
            "DynamicExpr",
            "EmergenceExpr",
            "DeclarationExpr",
            "JudgedExpr",
            "NoteExpr",
        }:
            raise NormalizationError(f"expected a term; got expression '{text}'")
        return term

    def _parse_anchor_term(self, tokens: list[str]) -> Any:
        if len(tokens) < 2:
            raise NormalizationError("anchor term statements must specify a term kind and value")
        kind = tokens[0]
        value_tokens = tokens[1:]
        if kind == "symbol":
            return self._build_model(
                AnchorTermSymbolNode,
                "anchor term",
                kind="symbol",
                value=self._parse_scalar_text(self._join_tokens(value_tokens)),
            )
        if kind == "claim":
            return self._build_model(
                AnchorTermClaimNode,
                "anchor term",
                kind="claim",
                value=self._parse_scalar_text(self._join_tokens(value_tokens)),
            )
        if kind == "expr":
            return self._build_model(
                AnchorTermExprNode,
                "anchor term",
                kind="expr",
                expr=self._parse_expr_text(self._join_tokens(value_tokens)),
            )
        raise NormalizationError(f"unsupported anchor term kind '{kind}'")

    def _parse_criterion(self, tokens: list[str]) -> Any:
        if len(tokens) < 2:
            raise NormalizationError("criterion statements must include a kind and value")
        kind = tokens[0]
        value_tokens = tokens[1:]
        if kind == "ref":
            return self._build_model(
                CriterionRefNode,
                "criterion",
                kind="ref",
                ref=self._parse_scalar_text(self._join_tokens(value_tokens)),
            )
        if kind == "expr":
            return self._build_model(
                CriterionExprNode,
                "criterion",
                kind="expr",
                expr=self._parse_expr_text(self._join_tokens(value_tokens)),
            )
        raise NormalizationError(f"unsupported criterion kind '{kind}'")

    def _parse_frame_or_pattern(self, text: str) -> FrameNode | FramePatternNode:
        if text.startswith("@"):
            return self._parse_frame_pattern(text)
        raise NormalizationError(f"unsupported frame value '{text}'")

    def _parse_frame_pattern(self, text: str) -> FramePatternNode:
        text = text.strip()
        if text.startswith("@{") and text.endswith("}"):
            inner = text[2:-1].strip()
            facets_payload: dict[str, str] = {}
            facet_policy: str | None = None
            for part in self._split_top_level(inner, ","):
                if "=" not in part:
                    raise NormalizationError(f"invalid frame pattern entry '{part}'")
                key, value = part.split("=", 1)
                key = key.strip()
                parsed_value = self._parse_scalar_text(value.strip())
                if key == "facet_policy":
                    facet_policy = parsed_value
                elif key in self._FRAME_FIELD_MAP:
                    facets_payload[key] = parsed_value
                else:
                    raise NormalizationError(f"unsupported frame pattern facet '{key}'")
            facets = self._build_model(FacetValueMap, "frame pattern facets", **facets_payload)
            return self._build_model(
                FramePatternNode,
                f"frame pattern '{text}'",
                node="FramePattern",
                facets=facets,
                facetPolicy=facet_policy,
            )
        return self._normalize_frame_shorthand(text)

    def _parse_inline_object(self, text: str) -> dict[str, Any]:
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise NormalizationError(f"invalid inline object '{text}'") from exc
        if not isinstance(value, dict):
            raise NormalizationError(f"expected an inline object; got '{text}'")
        return value

    def _select_bundle_resolution_policy(
        self,
        bundle_id: str,
        bundle_tree: Tree[Any],
        policies: list[tuple[ResolutionPolicyNode, Tree[Any]]],
        evaluators: list[EvaluatorNode],
        diagnostics: list[dict[str, Any]],
    ) -> ResolutionPolicyNode:
        if not policies:
            if len(evaluators) != 1:
                raise NormalizationError(
                    "bundle without resolution_policy must have exactly one evaluator"
                )
            evaluator_id = evaluators[0].id
            self._append_diagnostic(
                diagnostics,
                severity="info",
                subject=bundle_id,
                code="resolution_policy_defaulted",
                message=(
                    "Synthesized ResolutionPolicy(id='rp0', kind='single') from the "
                    f"lone evaluator '{evaluator_id}'."
                ),
                source_node=bundle_tree,
            )
            return self._build_model(
                ResolutionPolicyNode,
                f"bundle '{bundle_id}' synthesized resolution policy",
                node="ResolutionPolicy",
                id="rp0",
                kind="single",
                members=[evaluator_id],
            )
        primary, _primary_tree = policies[0]
        if len(policies) > 1:
            omitted_ids = [policy.id for policy, _tree in policies[1:]]
            self._append_diagnostic(
                diagnostics,
                severity="warning",
                subject=bundle_id,
                code="extra_resolution_policy_omitted",
                message=(
                    "Canonical AST stores one bundle-level resolutionPolicy; "
                    f"kept '{primary.id}' "
                    f"and omitted additional authored resolution_policy blocks {omitted_ids}."
                ),
                source_node=policies[1][1],
            )
        return primary

    def _append_diagnostic(
        self,
        diagnostics: list[dict[str, Any]],
        *,
        severity: str,
        subject: str,
        code: str,
        message: str,
        source_node: Tree[Any] | Token | None = None,
    ) -> None:
        diagnostics.append(
            Diagnostic(
                severity=severity,
                phase="normalize",
                subject=subject,
                code=code,
                message=message,
                span=self._build_source_span(source_node),
            ).model_dump(mode="json", exclude_none=True)
        )

    def _build_source_span(self, source_node: Tree[Any] | Token | None) -> SourceSpan | None:
        if source_node is None:
            return None

        meta = source_node.meta if isinstance(source_node, Tree) else source_node
        line = getattr(meta, "line", None)
        column = getattr(meta, "column", None)
        end_line = getattr(meta, "end_line", None)
        end_column = getattr(meta, "end_column", None)
        start_pos = getattr(meta, "start_pos", None)
        end_pos = getattr(meta, "end_pos", None)

        if None in {line, column, end_line, end_column, start_pos, end_pos}:
            return None

        return SourceSpan(
            start=SourcePosition(line=line, column=column, offset=start_pos),
            end=SourcePosition(line=end_line, column=end_column, offset=end_pos),
        )

    def _extract_nested_block_id(
        self, head_tokens: list[str], block_kind: str, parent_label: str
    ) -> str | None:
        if len(head_tokens) == 1:
            return None
        if len(head_tokens) == 2:
            return head_tokens[1]
        raise NormalizationError(
            f"{block_kind} blocks inside {parent_label} blocks may specify at most one id"
        )

    def _collect_flat_fields(
        self,
        block_tree: Tree[Any],
        block_name: str,
        field_map: dict[str, str],
    ) -> dict[str, list[str]]:
        payload: dict[str, list[str]] = {}
        for child in block_tree.children:
            statement = self._expect_tree(child, "statement")
            key, value_tokens = self._split_key_value(statement, block_name)
            if key not in field_map:
                raise NormalizationError(
                    f"normalization for '{key}' inside {block_name} blocks is not implemented yet"
                )
            target = field_map[key]
            self._ensure_field_absent(payload, target, block_name, key)
            payload[key] = value_tokens
        return payload

    def _split_key_value(self, statement_tree: Tree[Any], block_name: str) -> tuple[str, list[str]]:
        tokens = self._statement_tokens(statement_tree)
        if len(tokens) < 2:
            rendered = self._join_tokens(tokens)
            raise NormalizationError(
                f"{block_name} statements must have a key and value: '{rendered}'"
            )
        return tokens[0], tokens[1:]

    def _find_causal_index(self, tokens: list[str]) -> int | None:
        matches = [index for index, token in enumerate(tokens) if self._CAUSAL_RE.fullmatch(token)]
        if len(matches) > 1:
            raise NormalizationError("causal expressions may only contain one causal operator")
        return matches[0] if matches else None

    def _parse_scalar_tokens(self, tokens: list[str]) -> str:
        return self._parse_scalar_text(self._join_tokens(tokens))

    def _parse_scalar_text(self, text: str) -> str:
        text = text.strip()
        if text.startswith(('"', "'")):
            return self._parse_string_literal(text)
        return text

    def _parse_float(self, text: str, field_name: str) -> float:
        try:
            return float(text)
        except ValueError as exc:
            raise NormalizationError(f"invalid numeric value for {field_name}: '{text}'") from exc

    def _parse_optional_score(self, text: str) -> float | str:
        text = text.strip()
        if text == "N":
            return text
        return self._parse_float(text, "score")

    def _collect_block_fields(
        self, block_tree: Tree[Any], field_map: dict[str, str], block_name: str
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for child in block_tree.children:
            statement = self._expect_tree(child, "statement")
            tokens = self._statement_tokens(statement)
            if len(tokens) < 2:
                raise NormalizationError(
                    f"{block_name} statements must have a key and value: "
                    f"''{self._join_tokens(tokens)}''"
                )
            key = tokens[0]
            if key not in field_map:
                raise NormalizationError(
                    f"normalization for '{key}' inside {block_name} blocks is not implemented yet"
                )
            target = field_map[key]
            self._ensure_field_absent(payload, target, block_name, key)
            value_text = self._join_tokens(tokens[1:]).strip()
            payload[target] = self._parse_field_value(target, value_text)
        return payload

    def _parse_field_value(self, field_name: str, value_text: str) -> Any:
        if field_name in {"members", "order"}:
            return self._parse_list(value_text)
        return value_text

    def _parse_list(self, text: str) -> list[str]:
        text = text.strip()
        if not text.startswith("[") or not text.endswith("]"):
            raise NormalizationError(f"expected list syntax '[...]'; got '{text}'")
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [self._parse_scalar_text(part) for part in self._split_top_level(inner, ",")]

    def _parse_string_literal(self, text: str) -> str:
        try:
            value = py_ast.literal_eval(text)
        except (SyntaxError, ValueError) as exc:
            raise NormalizationError(f"invalid string literal '{text}'") from exc
        if not isinstance(value, str):
            raise NormalizationError(f"expected a string literal; got '{text}'")
        return value

    def _claim_kind_for_expr(self, expr: Any) -> str:
        node = expr.node
        if node == "JudgedExpr":
            return "judgment"
        if node == "LogicalExpr":
            return "logical"
        if node == "NoteExpr":
            return "note"
        if node == "PredicateExpr":
            return "atomic"
        if node == "CausalExpr":
            return "causal"
        if node == "DynamicExpr":
            return "dynamic"
        if node == "EmergenceExpr":
            return "emergence"
        if node == "DeclarationExpr":
            return "declaration"
        raise NormalizationError(f"unsupported claim expression type '{type(expr).__name__}'")

    def _split_nested_block(self, tree: Tree[Any]) -> tuple[list[str], Tree[Any]]:
        if len(tree.children) < 2:
            raise NormalizationError("nested blocks must include a head and a body block")
        block = self._expect_tree(tree.children[-1], "block")
        head = [self._as_text(child) for child in tree.children[:-1]]
        if not head:
            raise NormalizationError("nested blocks must include head tokens")
        return head, block

    def _statement_tokens(self, tree: Tree[Any]) -> list[str]:
        return [self._as_text(child) for child in tree.children]

    def _expect_tree(self, node: Any, data: str | None = None) -> Tree[Any]:
        if not isinstance(node, Tree):
            raise NormalizationError(
                f"expected tree node '{data or 'tree'}'; got '{type(node).__name__}'"
            )
        if data is not None and node.data != data:
            raise NormalizationError(f"expected tree node '{data}'; got '{node.data}'")
        return node

    def _as_text(self, node: Any) -> str:
        if isinstance(node, Token):
            return node.value
        if isinstance(node, str):
            return node
        raise NormalizationError(f"expected token text; got '{type(node).__name__}'")

    def _join_tokens(self, tokens: list[str]) -> str:
        return " ".join(tokens)

    def _split_args(self, text: str) -> list[str]:
        return self._split_top_level(text, ",")

    def _split_top_level(self, text: str, delimiter: str) -> list[str]:
        parts: list[str] = []
        start = 0
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        quote: str | None = None
        escape = False
        index = 0

        while index < len(text):
            char = text[index]
            if quote is not None:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char in {'"', "'"}:
                quote = char
            elif char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth -= 1
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1

            if (
                paren_depth == 0
                and bracket_depth == 0
                and brace_depth == 0
                and text.startswith(delimiter, index)
            ):
                parts.append(text[start:index].strip())
                index += len(delimiter)
                start = index
                continue
            index += 1

        parts.append(text[start:].strip())
        return [part for part in parts if part]

    def _looks_like_call(self, text: str) -> bool:
        if not text.endswith(")") or "(" not in text:
            return False
        name, _rest = text.split("(", 1)
        return bool(name.strip()) and " " not in name.strip()

    def _is_wrapped_expression(self, text: str) -> bool:
        if len(text) < 2 or text[0] != "(" or text[-1] != ")":
            return False
        depth = 0
        quote: str | None = None
        escape = False
        for index, char in enumerate(text):
            if quote is not None:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue
            if char in {'"', "'"}:
                quote = char
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
        return depth == 0 and quote is None

    def _build_model(self, model_cls: Any, context: str, /, **payload: Any) -> Any:
        try:
            return model_cls(**payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            raise NormalizationError(f"invalid {context}: {first['msg']}") from exc

    def _ensure_not_set(self, value: Any, label: str) -> None:
        if value is not None:
            raise NormalizationError(f"bundle may only define one {label} declaration")

    def _ensure_field_absent(
        self, payload: dict[str, Any], field_name: str, block_name: str, source_key: str
    ) -> None:
        existing = payload.get(field_name)
        if existing not in (None, [], {}):
            raise NormalizationError(
                f"duplicate field '{source_key}' in {block_name} block is not allowed"
            )
