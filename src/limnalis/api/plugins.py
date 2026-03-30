"""Stable public API for Limnalis plugin authors.

Extension protocols, context types, and result types needed to implement
custom evaluator bindings, criterion handlers, adequacy methods,
transport handlers, and other plugin types.
"""

from __future__ import annotations

from ..runtime.models import EvaluatorBindings, ExprHandler
from ..runtime.primitives import (
    ApplyResolutionPolicy,
    AssembleEval,
    BuildEvidenceView,
    BuildStepContext,
    ClassifyClaim,
    ComposeLicense,
    EvalExpr,
    EvaluateAdequacySet,
    ExecuteTransport,
    FoldBlock,
    ResolveBaseline,
    ResolveRef,
    SynthesizeSupport,
)
from ..runtime.runner import PrimitiveSet

__all__ = [
    # Phase protocols (13 phases)
    "ResolveRef",
    "BuildStepContext",
    "ResolveBaseline",
    "EvaluateAdequacySet",
    "ComposeLicense",
    "BuildEvidenceView",
    "ClassifyClaim",
    "EvalExpr",
    "SynthesizeSupport",
    "AssembleEval",
    "ApplyResolutionPolicy",
    "FoldBlock",
    "ExecuteTransport",
    # Evaluator bindings
    "EvaluatorBindings",
    "ExprHandler",
    # Primitive set
    "PrimitiveSet",
]
