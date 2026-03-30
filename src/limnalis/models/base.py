from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
