from __future__ import annotations

import ast as py_ast
import re
from dataclasses import dataclass, field
from typing import Any

from lark import Token, Tree

from .models.ast import (
    BaselineRefTermNode,
    BooleanTermNode,
    BundleNode,
    ClaimBlockNode,
    ClaimNode,
    EvaluatorNode,
    FacetValueMap,
    FrameNode,
    FramePatternNode,
    JudgedExprNode,
    LogicalExprNode,
    NoteExprNode,
    NullTermNode,
    NumberTermNode,
    PredicateExprNode,
    ResolutionPolicyNode,
    StringTermNode,
    SymbolTermNode,
    UriTermNode,
)


@dataclass(slots=True)
class NormalizationResult:
    canonical_ast: BundleNode | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class NormalizationError(ValueError):
    """Raised when a parsed surface tree cannot be normalized into the canonical AST."""


class Normalizer:
    """Canonical AST normalizer (Milestone 2 core subset)."""

    _CLAIM_BLOCK_STRATA = {"local", "systemic", "meta"}
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
    _UNSUPPORTED_CLAIM_KEYWORDS = {
        "annotations",
        "requires",
        "refs",
        "semantic_requirements",
        "uses",
    }
    _UNSUPPORTED_EXPR_MARKERS = {"-->", "EMRG", "declare", "when", "while", "until"}
    _LOGICAL_OPERATORS = {
        "AND": "and",
        "IFF": "iff",
        "IMPLIES": "implies",
        "OR": "or",
    }
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
        resolution_policy: ResolutionPolicyNode | None = None
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
                evaluators.append(self._normalize_evaluator(head_tokens, block_tree))
            elif head == "resolution_policy":
                self._ensure_not_set(resolution_policy, "resolution_policy")
                resolution_policy = self._normalize_resolution_policy(head_tokens, block_tree)
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

        if resolution_policy is None:
            if len(evaluators) != 1:
                raise NormalizationError(
                    "bundle without resolution_policy must have exactly one evaluator"
                )
            evaluator_id = evaluators[0].id
            resolution_policy = ResolutionPolicyNode(
                node="ResolutionPolicy",
                id="rp0",
                kind="single",
                members=[evaluator_id],
            )
            diagnostics.append(
                {
                    "severity": "info",
                    "phase": "normalize",
                    "subject": bundle_id,
                    "code": "resolution_policy_defaulted",
                    "message": (
                        "Synthesized ResolutionPolicy(id='rp0', kind='single') from the "
                        f"lone evaluator '{evaluator_id}'."
                    ),
                }
            )

        return BundleNode(
            node="Bundle",
            id=bundle_id,
            frame=frame,
            evaluators=evaluators,
            resolutionPolicy=resolution_policy,
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
        return FramePatternNode(
            node="FramePattern",
            facets=FacetValueMap(system=system, namespace=namespace, regime=regime),
        )

    def _normalize_frame_block(self, block_tree: Tree[Any]) -> FrameNode:
        payload = self._collect_block_fields(block_tree, self._FRAME_FIELD_MAP, "frame")
        return FrameNode(node="Frame", **payload)

    def _normalize_evaluator(self, head_tokens: list[str], block_tree: Tree[Any]) -> EvaluatorNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "evaluator blocks must be declared as 'evaluator <id> { ... }'"
            )
        payload = self._collect_block_fields(block_tree, self._EVALUATOR_FIELD_MAP, "evaluator")
        return EvaluatorNode(node="Evaluator", id=head_tokens[1], **payload)

    def _normalize_resolution_policy(
        self, head_tokens: list[str], block_tree: Tree[Any]
    ) -> ResolutionPolicyNode:
        if len(head_tokens) != 2:
            raise NormalizationError(
                "resolution_policy blocks must be declared as 'resolution_policy <id> { ... }'"
            )
        payload = self._collect_block_fields(
            block_tree, self._RESOLUTION_FIELD_MAP, "resolution_policy"
        )
        return ResolutionPolicyNode(node="ResolutionPolicy", id=head_tokens[1], **payload)

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
        expr_tokens = tokens[1:]
        expr = self._normalize_claim_expr(expr_tokens)
        kind = self._claim_kind_for_expr(expr)
        return ClaimNode(node="Claim", id=claim_id, kind=kind, expr=expr)

    def _normalize_claim_expr(self, tokens: list[str]) -> Any:
        if not tokens:
            raise NormalizationError("claim expression is empty")
        if any(token in self._UNSUPPORTED_CLAIM_KEYWORDS for token in tokens):
            raise NormalizationError(
                "claim metadata modifiers (refs/uses/requires/annotations/etc.) are not "
                "supported in the Milestone 2 core normalizer"
            )
        if any(
            token in self._UNSUPPORTED_EXPR_MARKERS or token.startswith("=>[") for token in tokens
        ):
            raise NormalizationError(
                "declaration, causal, dynamic, and emergence authored forms are not supported in "
                "the Milestone 2 core normalizer"
            )

        if tokens[0] == "note":
            note_text = self._join_tokens(tokens[1:]).strip()
            if not note_text:
                raise NormalizationError("note expressions require text")
            return NoteExprNode(node="NoteExpr", text=self._parse_string_literal(note_text))

        if "judged_by" in tokens:
            index = tokens.index("judged_by")
            if index == 0 or index == len(tokens) - 1:
                raise NormalizationError(
                    "judged_by expressions require both an inner expression and a criterion"
                )
            inner = self._parse_expr_text(self._join_tokens(tokens[:index]))
            criterion_ref = self._join_tokens(tokens[index + 1 :]).strip()
            if not criterion_ref:
                raise NormalizationError("judged_by expressions require a criterion reference")
            return JudgedExprNode(node="JudgedExpr", expr=inner, criterionRef=criterion_ref)

        return self._parse_expr_text(self._join_tokens(tokens))

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
        if text.startswith("|") and text.endswith("|"):
            inner = text[1:-1]
            ref_id = inner.split(":", 1)[-1].strip()
            if not ref_id:
                raise NormalizationError(f"invalid baseline reference '{text}'")
            return BaselineRefTermNode(node="BaselineRefTerm", id=ref_id)
        if text.startswith(('"', "'")):
            return StringTermNode(node="StringTerm", value=self._parse_string_literal(text))
        lowered = text.lower()
        if lowered == "true":
            return BooleanTermNode(node="BooleanTerm", value=True)
        if lowered == "false":
            return BooleanTermNode(node="BooleanTerm", value=False)
        if lowered == "null":
            return NullTermNode(node="NullTerm")
        if self._NUMBER_RE.fullmatch(text):
            return NumberTermNode(node="NumberTerm", value=float(text))
        if "://" in text:
            return UriTermNode(node="UriTerm", value=text)
        return SymbolTermNode(node="SymbolTerm", value=text)

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
        if not text.startswith("[") or not text.endswith("]"):
            raise NormalizationError(f"expected list syntax '[...]'; got '{text}'")
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [part.strip() for part in inner.split(",") if part.strip()]

    def _parse_string_literal(self, text: str) -> str:
        try:
            value = py_ast.literal_eval(text)
        except (SyntaxError, ValueError) as exc:
            raise NormalizationError(f"invalid string literal '{text}'") from exc
        if not isinstance(value, str):
            raise NormalizationError(f"expected a string literal; got '{text}'")
        return value

    def _claim_kind_for_expr(self, expr: Any) -> str:
        if isinstance(expr, JudgedExprNode):
            return "judgment"
        if isinstance(expr, LogicalExprNode):
            return "logical"
        if isinstance(expr, NoteExprNode):
            return "note"
        if isinstance(expr, PredicateExprNode):
            return "atomic"
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
        depth = 0
        index = 0
        while index < len(text):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and text.startswith(delimiter, index):
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
        for index, char in enumerate(text):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
        return depth == 0

    def _ensure_not_set(self, value: Any, label: str) -> None:
        if value is not None:
            raise NormalizationError(f"bundle may only define one {label} declaration")

    def _ensure_field_absent(
        self, payload: dict[str, Any], field_name: str, block_name: str, source_key: str
    ) -> None:
        if field_name in payload:
            raise NormalizationError(
                f"duplicate field '{source_key}' in {block_name} block is not allowed"
            )
