from __future__ import annotations

from pathlib import Path
from typing import Any

from lark import Lark

from .schema import _read_resource_text


class LimnalisParser:
    """Surface-language parser stub.

    The next implementation pass should:
    - expand the grammar in `grammar/limnalis.lark`
    - return a raw parse tree or raw AST preserving spans
    - feed the normalizer into canonical Pydantic AST models
    """

    def __init__(self) -> None:
        grammar = _read_resource_text("grammar", "limnalis.lark")
        self._lark = Lark(grammar, start="start", parser="earley")

    def parse_text(self, source: str) -> Any:
        return self._lark.parse(source)

    def parse_file(self, path: str | Path) -> Any:
        return self.parse_text(Path(path).read_text(encoding="utf-8"))
