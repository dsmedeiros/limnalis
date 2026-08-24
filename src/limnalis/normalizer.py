from __future__ import annotations

import ast as py_ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from lark import Token, Tree
from pydantic import BaseModel, ValidationError

from . import SPEC_VERSION
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
    # Logical operator levels per the recovered EBNF (spec/Limnalis-v0.2.2-reconstructed.md,
    # A.9 "Expression Grammar"):
    #
    #   LogicalExpr ::= IffExpr ;
    #   IffExpr     ::= ImplExpr { IffOp ImplExpr } ;
    #   ImplExpr    ::= OrExpr  { ImplOp OrExpr } ;
    #   OrExpr      ::= AndExpr { OrOp  AndExpr } ;
    #   AndExpr     ::= UnaryExpr { AndOp UnaryExpr } ;
    #   UnaryExpr   ::= [ NotOp ] CoreExpr ;
    #
    # so binding tightest -> loosest is NOT > AND > OR > IMPLIES > IFF. The
    # splitter is first-match-SPLITS: the first level found at the top level of
    # the text becomes the ROOT of the tree and therefore binds LOOSEST, so this
    # table must be ordered loosest-first: IFF, IMPLIES, OR, AND.
    #
    # Spellings: the spec's operator kernel is NotOp "¬"|"NOT",
    # AndOp "∧"|"AND", OrOp "∨"|"OR", ImplOp "→"|"->", and
    # IffOp "↔"|"<=>" (lines 1240-1244). The word forms IMPLIES and IFF are
    # legacy spellings (not part of the spec kernel) retained for backward
    # compatibility with the vendored corpus and examples.
    # Each entry: (canonical op, word spellings, symbol spellings).
    _LOGICAL_PRECEDENCE: list[
        tuple[Literal["iff", "implies", "or", "and"], tuple[str, ...], tuple[str, ...]]
    ] = [
        ("iff", ("IFF",), ("<=>", "↔")),
        ("implies", ("IMPLIES",), ("->", "→")),
        ("or", ("OR",), ("∨",)),
        ("and", ("AND",), ("∧",)),
    ]
    # Operators whose repeated occurrences must NOT flatten into one n-ary
    # node. AND/OR are associative in the spec §4 pair algebra, so grouping
    # cannot change their value and the EBNF repetition maps to a flat args
    # list. IMPLIES/IFF are non-associative ((a->b)->c != a->(b->c) in §4),
    # so their chains keep the grouping the EBNF dictates: `ImplExpr ::=
    # OrExpr { ImplOp OrExpr }` (A.9 line 1236) and `IffExpr ::= ImplExpr
    # { IffOp ImplExpr }` (line 1235) iterate left-to-right — each repetition
    # extends the expression already read — so repeated operators associate
    # LEFT and `a -> b -> c` builds implies(implies(a, b), c). Flattening
    # these levels was m7 red-team CRITICAL-1 (.armature/reviews/m7-redteam.md):
    # the runtime evaluated only the first two operands of the n-ary node.
    _NON_ASSOCIATIVE_OPS = frozenset({"implies", "iff"})
    _NOT_SYMBOL = "¬"
    # Word spellings of every logical operator level (including the prefix
    # NotOp, line 1240). Used to diagnose boundary-malformed inputs such as
    # `AND b` / `a AND`: a word operator at the very start or end of a
    # (sub)expression has no operand on that side, which no EBNF A.9
    # production derives, so the text survives as a predicate name whose
    # boundary retains the operator token (see
    # `_warn_boundary_operator_predicates`).
    _WORD_OPERATOR_TOKENS = ("NOT", "AND", "OR", "IMPLIES", "IFF")
    _JUDGED_KEYWORD = "judged_by"
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
                    self._normalize_claim_block(head, block_counts[head], block_tree, diagnostics)
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
                        f"AST kind 'process' because schema {SPEC_VERSION} does not admit "
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
        self,
        stratum: str,
        index: int,
        block_tree: Tree[Any],
        diagnostics: list[dict[str, Any]],
    ) -> ClaimBlockNode:
        claims = [
            self._normalize_claim(self._expect_tree(item, "statement"), diagnostics)
            for item in block_tree.children
        ]
        return ClaimBlockNode(
            node="ClaimBlock",
            id=f"{stratum}#{index}",
            stratum=stratum,
            claims=claims,
        )

    def _normalize_claim(
        self, statement_tree: Tree[Any], diagnostics: list[dict[str, Any]]
    ) -> ClaimNode:
        tokens = self._statement_tokens(statement_tree)
        if len(tokens) < 2:
            raise NormalizationError("claim statements must include an id and an expression")
        if not tokens[0].endswith(":"):
            raise NormalizationError(f"claim statement must start with '<id>:'; got '{tokens[0]}'")

        claim_id = tokens[0][:-1]
        expr_tokens, metadata = self._split_claim_tokens(claim_id, tokens[1:])
        expr = self._normalize_claim_expr(expr_tokens)
        self._warn_boundary_operator_predicates(
            claim_id, expr, diagnostics, source_tree=statement_tree
        )
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
        # ALL authored forms (judged_by, logical connectives, causal markers,
        # EMRG, dynamics, note, declare, predicates) are handled by the
        # expression text parser, which enforces the EBNF A.9 nesting order —
        # in particular Expr ::= JudgedExpr (line 1232), so a trailing
        # `judged_by` wraps causal/emergence/note/declaration expressions
        # instead of being swallowed into their right-hand side. `note` and
        # `declare` are CoreExprs (lines 1246-1247, 1258-1263) dispatched by
        # `_parse_core_expr_text` AFTER the judged_by/logical splits; the
        # former top-level early-exits to `_parse_note`/`_parse_declaration`
        # bypassed those splits, crashing on `note "x" judged_by k` and
        # leaking `judged_by`/operator text into DeclarationExpr.declaredAs
        # (fixed per review advisory 1,
        # .armature/reviews/m7-t2-normalizer-precedence.md).
        return self._parse_expr_text(self._join_tokens(tokens))

    def _warn_boundary_operator_predicates(
        self,
        claim_id: str,
        expr: Any,
        diagnostics: list[dict[str, Any]],
        *,
        source_tree: Tree[Any],
    ) -> None:
        """Warn when a claim expression retains a word operator at a boundary.

        A word operator at the very start or end of a (sub)expression —
        `AND b`, `a AND` — has no operand on that side, which no EBNF A.9
        production derives (AndExpr ::= UnaryExpr { AndOp UnaryExpr }, line
        1238, and likewise lines 1235-1237; the prefix NotOp, line 1239-1240,
        requires a following CoreExpr). The permissive pipeline keeps such
        text as an atomic predicate name rather than hard-failing, so this
        walk inspects the normalized claim expression for PredicateExpr names
        that begin or end with an operator token and emits an
        `expr_malformed_operator` warning for each (NORM-002; review
        advisory 2, .armature/reviews/m7-t2-normalizer-precedence.md).

        Only multi-word names are flagged: a bare single-word name equal to an
        operator spelling (e.g. a predicate literally named `AND`) is still a
        lexically valid Ident (line 1013) and carries no swallowed operand.
        Symbol spellings never reach a boundary silently — an empty operand
        beside them already raises a missing-operand error in
        `_parse_expr_text`.
        """
        for predicate in self._iter_predicate_nodes(expr):
            token = self._boundary_operator_token(predicate.name)
            if token is None:
                continue
            self._append_diagnostic(
                diagnostics,
                severity="warning",
                subject=claim_id,
                code="expr_malformed_operator",
                message=(
                    f"Claim '{claim_id}' expression retains the bare word operator "
                    f"'{token}' at a boundary of predicate name {predicate.name!r}; "
                    "word operators require an operand on each side (EBNF A.9 "
                    "lines 1235-1240), so the text was kept verbatim as an atomic "
                    "predicate name."
                ),
                source_node=source_tree,
            )

    def _iter_predicate_nodes(self, node: Any) -> list[PredicateExprNode]:
        """Collect every PredicateExprNode in an expression tree, depth-first.

        Traversal order is deterministic (model field declaration order, list
        order), preserving NORM-001 for the diagnostics this feeds.
        """
        found: list[PredicateExprNode] = []
        self._collect_predicate_nodes(node, found)
        return found

    def _collect_predicate_nodes(self, value: Any, found: list[PredicateExprNode]) -> None:
        if isinstance(value, BaseModel):
            if isinstance(value, PredicateExprNode):
                found.append(value)
            for field_name in type(value).model_fields:
                self._collect_predicate_nodes(getattr(value, field_name), found)
        elif isinstance(value, list):
            for item in value:
                self._collect_predicate_nodes(item, found)

    def _boundary_operator_token(self, name: str) -> str | None:
        """Return the word operator sitting at a boundary of `name`, else None."""
        for word in self._WORD_OPERATOR_TOKENS:
            if name.startswith(f"{word} ") or name.endswith(f" {word}"):
                return word
        return None

    def _parse_note(self, tokens: list[str]) -> NoteExprNode:
        note_text = self._join_tokens(tokens[1:]).strip()
        if not note_text:
            raise NormalizationError("note expressions require text")
        return self._build_model(
            NoteExprNode,
            "note expression",
            node="NoteExpr",
            text=self._parse_string_literal(note_text),
        )

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

    def _parse_causal(self, lhs_text: str, marker: str, rhs_text: str) -> CausalExprNode:
        """Build a CausalExpr per EBNF A.9 line 1249 from a top-level split.

        `CausalExpr ::= SimpleExpr CausalOp SimpleExpr [ InterventionClause ]`
        with `CausalOp ::= "⇒[obs]" | "=>[obs]" | "⇒[do]" | "=>[do]"`
        (line 1250). The split arrives from `_find_causal_split`, which is
        whitespace-independent, so both `x =>[obs] y` and `x=>[obs]y`
        reach this builder (review advisory 3,
        .armature/reviews/m7-t2-normalizer-precedence.md).
        """
        match = self._CAUSAL_RE.fullmatch(marker)
        if match is None:
            raise NormalizationError(f"invalid causal marker '{marker}'")
        if not lhs_text or not rhs_text:
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
            lhs=self._parse_expr_text(lhs_text),
            rhs=self._parse_expr_text(rhs_text),
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
            onset=self._parse_dynamic(self._join_tokens(onset_tokens)),
            persistsWhile=persists_while,
            dissolvesWhen=dissolves_when,
        )

    def _parse_dynamic(self, text: str) -> DynamicExprNode | Any:
        """Parse text that MAY carry a top-level `-->` DynamicOp (EBNF line 1266).

        Used for emergence onset clauses, which are Exprs when no dynamic
        marker is present. Marker detection is whitespace-independent (see
        `_find_dynamic_split`).
        """
        split = self._find_dynamic_split(text)
        if split is None:
            return self._parse_expr_text(text)
        return self._build_dynamic(*split)

    def _build_dynamic(self, subject_text: str, target_text: str) -> DynamicExprNode:
        """Build a DynamicExpr per EBNF A.9 line 1265:
        `DynamicExpr ::= Term DynamicOp [ TermOrExpr ]` with the `-->`
        spelling of DynamicOp (line 1266) normalized to op="approaches"."""
        if not subject_text or not target_text:
            raise NormalizationError("dynamic authored forms require both a subject and target")
        return self._build_model(
            DynamicExprNode,
            "dynamic expression",
            node="DynamicExpr",
            op="approaches",
            subject=self._parse_term_text(subject_text),
            target=self._parse_arg_text(target_text),
        )

    def _parse_expr_text(self, text: str) -> Any:
        """Parse expression text per EBNF A.9 (spec/Limnalis-v0.2.2-reconstructed.md).

        Nesting order, outermost first::

            Expr        ::= JudgedExpr ;
            JudgedExpr  ::= LogicalExpr [ "judged_by" Ref ] ;
            LogicalExpr ::= IffExpr ;             (levels: IFF, IMPLIES, OR, AND)
            UnaryExpr   ::= [ NotOp ] CoreExpr ;

        Each stage splits the text at top-level occurrences of its operator
        (parentheses, brackets, braces, and string quotes shield inner
        occurrences) and recurses on the remainders, so unparenthesized
        operands always receive logical structure and never collapse into
        atomic predicate names.
        """
        text = text.strip()
        if not text:
            raise NormalizationError("expression text is empty")

        # Expr ::= JudgedExpr ; JudgedExpr ::= LogicalExpr [ "judged_by" Ref ]
        # judged_by is the OUTERMOST construct: it wraps whatever expression
        # precedes it (including causal and emergence forms).
        judged_parts = self._split_at_top_level_operators(text, self._match_judged_by)
        if len(judged_parts) > 2:
            raise NormalizationError(
                "expressions may contain at most one 'judged_by' per nesting level"
            )
        if len(judged_parts) == 2:
            inner_text, criterion_text = judged_parts
            if not inner_text or not criterion_text:
                raise NormalizationError(
                    "judged_by expressions require both an inner expression and a criterion"
                )
            criterion_ref = self._parse_scalar_text(criterion_text)
            if not criterion_ref:
                raise NormalizationError("judged_by expressions require a criterion reference")
            return self._build_model(
                JudgedExprNode,
                "judged expression",
                node="JudgedExpr",
                expr=self._parse_expr_text(inner_text),
                criterionRef=criterion_ref,
            )

        # Binary levels, loosest first: the first level that splits becomes the
        # root, so IFF binds loosest and AND binds tightest of the binary ops.
        # Tree shape depends on associativity (see _NON_ASSOCIATIVE_OPS):
        # - AND/OR (associative, spec §4): the EBNF's `{ Op ... }` repetition
        #   maps to a flat n-ary args list, so `a AND b AND c` -> and(a, b, c).
        # - IMPLIES/IFF (non-associative): the repetitions `ImplExpr ::=
        #   OrExpr { ImplOp OrExpr }` (A.9 line 1236) and `IffExpr ::=
        #   ImplExpr { IffOp ImplExpr }` (line 1235) read left-to-right, so
        #   repeated operators associate LEFT into a binary chain:
        #   `a -> b -> c` -> implies(implies(a, b), c). Never n-ary — the
        #   flat shape erased the grouping and the runtime silently dropped
        #   operands past the second (m7 red-team CRITICAL-1).
        for op_name, word_ops, symbol_ops in self._LOGICAL_PRECEDENCE:
            parts = self._split_logical_level(text, word_ops, symbol_ops)
            if len(parts) > 1:
                if any(not part for part in parts):
                    raise NormalizationError(
                        f"logical '{op_name}' expression is missing an operand in '{text}'"
                    )
                operands = [self._parse_expr_text(part) for part in parts]
                if op_name in self._NON_ASSOCIATIVE_OPS:
                    chain = operands[0]
                    for operand in operands[1:]:
                        chain = LogicalExprNode(
                            node="LogicalExpr",
                            op=op_name,
                            args=[chain, operand],
                        )
                    return chain
                return LogicalExprNode(
                    node="LogicalExpr",
                    op=op_name,
                    args=operands,
                )

        # UnaryExpr ::= [ NotOp ] CoreExpr — checked after the binary splits so
        # NOT binds tighter than every binary operator: `NOT a AND b` splits on
        # AND first and yields and(not(a), b).
        not_operand = self._strip_not_prefix(text)
        if not_operand is not None:
            return LogicalExprNode(
                node="LogicalExpr",
                op="not",
                args=[self._parse_expr_text(not_operand)],
            )

        return self._parse_core_expr_text(text)

    def _parse_core_expr_text(self, text: str) -> Any:
        """Parse a CoreExpr per EBNF A.9 (lines 1246-1247)::

            CoreExpr ::= CausalExpr | EmergenceExpr | DeclarationExpr
                       | NoteExpr | DynamicExpr | PredicateExpr | "(" Expr ")" ;

        The text reaching this stage has no top-level judged_by/logical
        operators. Keyword-led forms (`note`, `declare`, EMRG) are dispatched
        from the top-level surface words; the causal `=>[obs]`/`=>[do]`
        (CausalOp, line 1250) and dynamic `-->` (DynamicOp, line 1266) markers
        are located by whitespace-independent top-level text scans, so
        `x=>[obs]y` and `a-->|0:b|` parse identically to their spaced
        spellings (review advisory 3,
        .armature/reviews/m7-t2-normalizer-precedence.md). The scans cannot
        collide with grammar-valid predicate names: `Ident ::= Letter
        { Letter | Digit | "_" | "-" }` (line 1013) admits `-` but never `>`
        or `=`, so neither marker can occur inside a valid Ident. Reference
        ids carry no such charset guarantee, so `|0:...|`/`|inf:...|`/`|∞:...|`
        spans are additionally shielded from every top-level scanner — the
        operator/marker scan `_scan_top_level_matches` (m7-t2b review
        Finding 1), plus the argument/list splitter `_split_top_level`, the
        surface-word splitter `_split_words`, and the wrapped-group check
        `_is_wrapped_expression` (m7 red-team MEDIUM-3) — all via the shared
        `_pipe_span_opens` span rule.
        """
        if self._is_wrapped_expression(text):
            return self._parse_expr_text(text[1:-1].strip())

        words = self._split_words(text)
        if len(words) > 1:
            if words[0] == "note":
                return self._parse_note(words)
            if words[0] == "declare":
                return self._parse_declaration(words)
            if "EMRG" in words:
                return self._parse_emergence(words)

        causal_split = self._find_causal_split(text)
        if causal_split is not None:
            return self._parse_causal(*causal_split)
        dynamic_split = self._find_dynamic_split(text)
        if dynamic_split is not None:
            return self._build_dynamic(*dynamic_split)

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

    def _strip_not_prefix(self, text: str) -> str | None:
        """Return the NotOp operand when text is `("¬" | "NOT") CoreExpr`, else None.

        The word form requires trailing whitespace (matched case-insensitively,
        preserving the normalizer's historical acceptance of `not`); the symbol
        form `¬` may abut its operand.
        """
        if text.startswith(self._NOT_SYMBOL):
            rest = text[len(self._NOT_SYMBOL) :].strip()
            if rest:
                return rest
        if len(text) > 4 and text[:4].upper() == "NOT ":
            rest = text[4:].strip()
            if rest:
                return rest
        return None

    def _split_logical_level(
        self, text: str, word_ops: tuple[str, ...], symbol_ops: tuple[str, ...]
    ) -> list[str]:
        def matcher(candidate: str, index: int) -> int:
            return self._match_logical_operator(candidate, index, word_ops, symbol_ops)

        return self._split_at_top_level_operators(text, matcher)

    def _match_logical_operator(
        self, text: str, index: int, word_ops: tuple[str, ...], symbol_ops: tuple[str, ...]
    ) -> int:
        """Return the matched operator length at `index`, or 0.

        Word spellings (AND, OR, IMPLIES, IFF) require whitespace on both sides
        so symbol names such as TARIFF or BRAND are never split. Symbol
        spellings may abut their operands; `->` refuses to match inside the
        dynamic operator `-->` (and `->>`/`<->`-like neighborhoods), keeping
        `a --> |0:b|` a DynamicExpr.
        """
        for word in word_ops:
            end = index + len(word)
            if (
                text.startswith(word, index)
                and index > 0
                and text[index - 1].isspace()
                and end < len(text)
                and text[end].isspace()
            ):
                return len(word)
        for symbol in symbol_ops:
            if not text.startswith(symbol, index):
                continue
            before = text[index - 1] if index > 0 else ""
            after_index = index + len(symbol)
            after = text[after_index] if after_index < len(text) else ""
            if symbol == "->" and (before in {"-", "<"} or after == ">"):
                continue
            if symbol == "<=>" and (before == "<" or after == ">"):
                continue
            return len(symbol)
        return 0

    def _match_judged_by(self, text: str, index: int) -> int:
        keyword = self._JUDGED_KEYWORD
        if not text.startswith(keyword, index):
            return 0
        end = index + len(keyword)
        before_ok = index == 0 or text[index - 1].isspace()
        after_ok = end == len(text) or text[end].isspace()
        return len(keyword) if before_ok and after_ok else 0

    def _split_at_top_level_operators(self, text: str, matcher: Any) -> list[str]:
        """Split text at every top-level operator occurrence reported by `matcher`.

        `matcher(text, index)` returns the number of characters the operator
        occupies at `index` (0 for no match). Occurrences inside parentheses,
        brackets, braces, or string quotes never split. Parts are stripped but
        NOT filtered: callers decide how to treat empty operands.
        """
        parts: list[str] = []
        start = 0
        for index, length in self._scan_top_level_matches(text, matcher):
            parts.append(text[start:index].strip())
            start = index + length
        parts.append(text[start:].strip())
        return parts

    @staticmethod
    def _pipe_span_opens(text: str, index: int) -> bool:
        """True when `text[index]` is a `|` that opens a reference span.

        A span opens only at a `|` immediately followed by one of the
        reference sigils `0:`, `inf:`, or `∞:` (`BaselineRef ::= "|0:" Ident
        "|"`, `UnboundRef ::= "|∞:" Ident "|" | "|inf:" Ident "|"`, EBNF A.9
        lines 1279-1280) and closes at the next `|`. Shared by every
        top-level scanner — `_scan_top_level_matches`, `_split_top_level`,
        `_split_words`, and `_is_wrapped_expression` — so all four treat span
        content as opaque (m7-t2b review Finding 1; extended to the last
        three scanners for m7 red-team MEDIUM-3).
        """
        return text[index] == "|" and (
            text.startswith("0:", index + 1)
            or text.startswith("inf:", index + 1)
            or text.startswith("∞:", index + 1)
        )

    def _scan_top_level_matches(self, text: str, matcher: Any) -> list[tuple[int, int]]:
        """Return every top-level `(index, length)` match reported by `matcher`.

        `matcher(text, index)` returns the number of characters the match
        occupies at `index` (0 for no match). Occurrences inside parentheses,
        brackets, braces, string quotes, or `|...|` reference spans are never
        reported, and scanning resumes after each match so matches never
        overlap. Shared by the operator splitter and the whitespace-independent
        causal/dynamic marker finders so all top-level scans use one shielding
        state machine.

        Pipe-span rule (m7-t2b review Finding 1,
        .armature/reviews/m7-t2b-claim-forms.md): baseline and unbound
        reference terms — `BaselineRef ::= "|0:" Ident "|"`, `UnboundRef ::=
        "|∞:" Ident "|" | "|inf:" Ident "|"` (EBNF A.9 lines 1279-1280) — are
        consumed verbatim as single terms by `_parse_arg_text`, and this
        normalizer imposes no charset restriction on the reference id, so
        marker/operator-shaped substrings inside them (e.g.
        `|0:some=>[obs]weird|`, `|0:a AND b|`) must never split. `|` is its
        own closer, so a span is tracked as a boolean: it OPENS only at a `|`
        immediately followed by `0:`, `inf:`, or `∞:` (the only reference
        sigils, per the EBNF above) and CLOSES at the next `|`. Restricting
        the opening to plausible reference sigils keeps a stray `|` elsewhere
        in the text (e.g. a lone `|` or `||` token) from swallowing the rest
        of the scan. Span content is treated as fully opaque — nested
        delimiters inside it do not touch the depth counters, mirroring how
        `_parse_arg_text` consumes the span without interpreting it.
        """
        matches: list[tuple[int, int]] = []
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        quote: str | None = None
        escape = False
        pipe_span = False
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

            if pipe_span:
                if char == "|":
                    pipe_span = False
                index += 1
                continue
            if self._pipe_span_opens(text, index):
                pipe_span = True
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

            if paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                matched = matcher(text, index)
                if matched:
                    matches.append((index, matched))
                    index += matched
                    continue
            index += 1

        return matches

    def _split_words(self, text: str) -> list[str]:
        """Split expression text into top-level surface words.

        Whitespace inside parentheses, brackets, braces, string quotes, or
        `|...|` reference spans (see `_pipe_span_opens`; m7 red-team
        MEDIUM-3) does not split, so a word list mirrors the parser's
        statement atoms for the same source (e.g. `p(x) =>[obs] q(y)` ->
        [`p(x)`, `=>[obs]`, `q(y)`], and `declare |0:x'y| as fiction` ->
        [`declare`, `|0:x'y|`, `as`, `fiction`]).
        """
        words: list[str] = []
        start: int | None = None
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        quote: str | None = None
        escape = False
        pipe_span = False

        for index, char in enumerate(text):
            if quote is not None:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue

            if pipe_span:
                if char == "|":
                    pipe_span = False
                if start is None:
                    start = index
                continue
            if self._pipe_span_opens(text, index):
                pipe_span = True
                if start is None:
                    start = index
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
            elif char.isspace() and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0:
                if start is not None:
                    words.append(text[start:index])
                    start = None
                continue

            if start is None:
                start = index

        if start is not None:
            words.append(text[start:])
        return words

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

    def _find_causal_split(self, text: str) -> tuple[str, str, str] | None:
        """Locate a top-level CausalOp marker; return (lhs, marker, rhs) or None.

        `CausalOp ::= "⇒[obs]" | "=>[obs]" | "⇒[do]" | "=>[do]"` (EBNF A.9
        line 1250; this normalizer supports the ASCII spellings). The scan is
        whitespace-independent — `x=>[obs]y` splits the same as
        `x =>[obs] y` — and cannot be ambiguous: the `=>[` lead-in shares no
        prefix with ImplOp `->` (line 1243), and `Ident` (line 1013) admits
        neither `=` nor `>`, so no grammar-valid predicate name contains it
        (review advisory 3, .armature/reviews/m7-t2-normalizer-precedence.md).
        Baseline/unbound reference spans (`|0:...|` etc., lines 1279-1280),
        whose ids are NOT charset-restricted, are shielded by
        `_scan_top_level_matches` so a marker-shaped substring inside one can
        never split (m7-t2b review Finding 1).
        """
        matches = self._scan_top_level_matches(text, self._match_causal_marker)
        if not matches:
            return None
        if len(matches) > 1:
            raise NormalizationError("causal expressions may only contain one causal operator")
        index, length = matches[0]
        return (
            text[:index].strip(),
            text[index : index + length],
            text[index + length :].strip(),
        )

    def _match_causal_marker(self, text: str, index: int) -> int:
        """Return the length of the CausalOp marker starting at `index`, or 0.

        A marker starts with `=>[` and runs to the bracket-matched `]`
        (interventions may nest brackets or quote strings); the whole span
        must match `_CAUSAL_RE` (`=>[obs]`, `=>[do]`, `=>[do:<intervention>]`).
        """
        if not text.startswith("=>[", index):
            return 0
        depth = 0
        quote: str | None = None
        escape = False
        for pos in range(index + 2, len(text)):
            char = text[pos]
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
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    candidate = text[index : pos + 1]
                    return len(candidate) if self._CAUSAL_RE.fullmatch(candidate) else 0
        return 0

    def _find_dynamic_split(self, text: str) -> tuple[str, str] | None:
        """Locate the first top-level `-->` DynamicOp; return (subject, target) or None.

        `DynamicOp ::= "⟶" | "-->" | ...` (EBNF A.9 line 1266; this
        normalizer supports the ASCII `-->` spelling, normalized to
        op="approaches"). The scan is whitespace-independent — `a-->|0:b|`
        splits the same as `a --> |0:b|` — and is guarded against the two
        neighboring token families (review advisory 3,
        .armature/reviews/m7-t2-normalizer-precedence.md):

        - ImplOp `->` (line 1243) is a shorter, distinct token: it cannot
          contain `-->`, and `_match_logical_operator` already refuses `->`
          when adjacent to another `-`/`<`/`>`, so `a->b` stays IMPLIES and
          `a-->b` reaches this scan un-split.
        - Predicate names may contain `-` (`Ident ::= Letter { Letter | Digit
          | "_" | "-" }`, line 1013) but never `>`, so no grammar-valid name
          contains `-->`; hyphenated names such as `well-formed` are
          unaffected. Longer dash-arrow runs (`a--->b`, `<-->`, `-->>`) are
          not derivable from the EBNF and are deliberately NOT treated as
          DynamicOps: the match refuses a preceding `-`/`<` and a following
          `>`, so such text stays an opaque predicate name.
        - Reference-span content (`|0:...|` etc., lines 1279-1280) is shielded
          by `_scan_top_level_matches` (m7-t2b review Finding 1).
        """
        matches = self._scan_top_level_matches(text, self._match_dynamic_marker)
        if not matches:
            return None
        index, length = matches[0]
        return text[:index].strip(), text[index + length :].strip()

    def _match_dynamic_marker(self, text: str, index: int) -> int:
        """Return 3 when exactly `-->` (not a longer arrow run) starts at `index`."""
        if not text.startswith("-->", index):
            return 0
        before = text[index - 1] if index > 0 else ""
        after_index = index + 3
        after = text[after_index] if after_index < len(text) else ""
        if before in {"-", "<"} or after == ">":
            return 0
        return 3

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
        """Split `text` at top-level occurrences of `delimiter`.

        Occurrences inside parentheses, brackets, braces, string quotes, or
        `|...|` reference spans (see `_pipe_span_opens`) never split, so an
        argument such as `|0:a,b|` survives `_split_args` as one part
        (m7 red-team MEDIUM-3). Empty parts are dropped.
        """
        parts: list[str] = []
        start = 0
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        quote: str | None = None
        escape = False
        pipe_span = False
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

            if pipe_span:
                if char == "|":
                    pipe_span = False
                index += 1
                continue
            if self._pipe_span_opens(text, index):
                pipe_span = True
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
        """True when `text` is one parenthesized group wrapping the whole text.

        Parentheses and quotes inside string quotes or `|...|` reference
        spans (see `_pipe_span_opens`) are span content and never affect the
        balance, so `(a AND |0:x(y|)` and `(a AND |0:x'y|)` are wrapped
        expressions (m7 red-team MEDIUM-3).
        """
        if len(text) < 2 or text[0] != "(" or text[-1] != ")":
            return False
        depth = 0
        quote: str | None = None
        escape = False
        pipe_span = False
        for index, char in enumerate(text):
            if quote is not None:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == quote:
                    quote = None
                continue
            if pipe_span:
                if char == "|":
                    pipe_span = False
                continue
            if self._pipe_span_opens(text, index):
                pipe_span = True
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
        return depth == 0 and quote is None and not pipe_span

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
