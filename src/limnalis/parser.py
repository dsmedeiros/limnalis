from __future__ import annotations

from pathlib import Path
from typing import Any

from lark import Lark

from .schema import _read_resource_text


class LimnalisParser:
    """Surface-language parser (Milestone 1).

    This milestone returns a permissive raw parse tree from the authored
    surface language. Semantic interpretation and canonical AST normalization
    are intentionally deferred to later milestones.
    """

    def __init__(self) -> None:
        grammar = _read_resource_text("grammar", "limnalis.lark")
        self._lark = Lark(grammar, start="start", parser="earley")

    def parse_text(self, source: str) -> Any:
        return self._lark.parse(source)

    def parse_file(self, path: str | Path) -> Any:
        return self.parse_text(Path(path).read_text(encoding="utf-8"))
