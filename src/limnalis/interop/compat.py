"""Compatibility checking for Limnalis interop envelopes."""

from __future__ import annotations

from limnalis.interop.envelopes import (
    ASTEnvelope,
    ConformanceEnvelope,
    ResultEnvelope,
)
from limnalis.interop.types import SCHEMA_VERSION, SPEC_VERSION


def check_envelope_compatibility(
    envelope: ASTEnvelope | ResultEnvelope | ConformanceEnvelope,
) -> list[str]:
    """Check if an envelope's version metadata is compatible with this implementation.

    Returns list of compatibility issues (empty = compatible).
    Checks:
    - spec_version matches SPEC_VERSION
    - schema_version matches SCHEMA_VERSION
    """
    issues: list[str] = []

    if envelope.spec_version != SPEC_VERSION:
        issues.append(
            f"spec_version mismatch: envelope has {envelope.spec_version!r}, "
            f"this implementation expects {SPEC_VERSION!r}"
        )

    if envelope.schema_version != SCHEMA_VERSION:
        issues.append(
            f"schema_version mismatch: envelope has {envelope.schema_version!r}, "
            f"this implementation expects {SCHEMA_VERSION!r}"
        )

    return issues
