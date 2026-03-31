"""Stable public API for Limnalis adequacy execution with basis resolution.

Re-exports adequacy execution helpers from the runtime layer, plus the
basis resolution and trace types from the conformance model.
"""

from __future__ import annotations

from ..runtime import (
    execute_adequacy_with_basis,
    aggregate_contested_adequacy,
    detect_basis_circularity,
)
from ..models.conformance import BasisResolutionEntry, AdequacyExecutionTrace

__all__ = [
    # Execution helpers
    "execute_adequacy_with_basis",
    "aggregate_contested_adequacy",
    "detect_basis_circularity",
    # Result types
    "BasisResolutionEntry",
    "AdequacyExecutionTrace",
]
