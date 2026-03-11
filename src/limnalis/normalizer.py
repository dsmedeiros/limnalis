from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NormalizationResult:
    canonical_ast: Any | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


class Normalizer:
    """Canonical AST normalizer stub.

    Planned work:
    - operator alias normalization
    - frame shorthand -> FramePatternNode
    - judged_by -> JudgedExprNode
    - fictional_anchor sugar
    - synthetic block ids
    - backward-compatibility rewrites for single-evaluator bundles
    """

    def normalize(self, raw_tree: Any) -> NormalizationResult:
        raise NotImplementedError("Normalizer implementation is the next milestone.")
