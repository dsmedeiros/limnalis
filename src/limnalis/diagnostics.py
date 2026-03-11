from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models.base import LimnalisModel


class SourcePosition(LimnalisModel):
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    offset: int = Field(ge=0)


class SourceSpan(LimnalisModel):
    start: SourcePosition
    end: SourcePosition


class Diagnostic(LimnalisModel):
    severity: Literal["info", "warning", "error"]
    phase: str
    subject: str
    code: str
    message: str
    span: SourceSpan | None = None
