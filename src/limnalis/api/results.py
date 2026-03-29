"""Stable public API for Limnalis evaluation result types.

Types that plugin implementations must return or that appear in
evaluation output.
"""

from __future__ import annotations

from ..runtime.models import (
    AdequacyResult,
    AnchorAdequacyResult,
    AnchorLicenseEntry,
    BlockResult,
    ClaimResult,
    EvalNode,
    JointAdequacyResult,
    JointLicenseEntry,
    LicenseOverall,
    LicenseResult,
    SupportResult,
    TransportResult,
    TruthCore,
)
from ..runtime.runner import (
    BundleResult,
    EvaluationResult,
    SessionResult,
    StepResult,
)

__all__ = [
    # Core result types
    "TruthCore",
    "SupportResult",
    "EvalNode",
    # License results
    "LicenseResult",
    "LicenseOverall",
    "AnchorLicenseEntry",
    "JointLicenseEntry",
    # Adequacy results
    "AdequacyResult",
    "AnchorAdequacyResult",
    "JointAdequacyResult",
    # Transport results
    "TransportResult",
    # Per-claim / per-block results
    "ClaimResult",
    "BlockResult",
    # Top-level results
    "StepResult",
    "SessionResult",
    "BundleResult",
    "EvaluationResult",
]
