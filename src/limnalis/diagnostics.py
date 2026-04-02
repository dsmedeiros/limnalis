from __future__ import annotations

from typing import Any, Literal

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

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Diagnostic:
        """Normalize a raw runtime dict to a typed Diagnostic instance.

        Handles missing fields with sensible defaults and ignores
        unrecognised keys.
        """
        return cls(
            severity=raw.get("severity") or "info",
            phase=raw.get("phase") or "unknown",
            subject=raw.get("subject") or "",
            code=raw.get("code") or "unknown",
            message=raw.get("message") or "",
            span=raw.get("span"),
        )
