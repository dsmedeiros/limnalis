from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, ConfigDict, field_validator


class LimnalisModel(BaseModel):
    """Strict base model for runtime AST validation."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=False,
    )


    def to_schema_data(self) -> dict:
        """Dump a JSON-schema-friendly dict (omit null optional fields)."""

        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class UniqueStringListModel(LimnalisModel):
    """Mixin helpers for models that want list uniqueness checks."""

    @staticmethod
    def _ensure_unique_strings(values: Iterable[str] | None, field_name: str) -> Iterable[str] | None:
        if values is None:
            return values
        as_list = list(values)
        if len(as_list) != len(set(as_list)):
            raise ValueError(f"{field_name} must contain unique values")
        return as_list
