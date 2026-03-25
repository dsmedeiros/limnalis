"""Limnalis reference Python scaffold."""

SPEC_VERSION = "v0.2.2"

from .loader import load_surface_bundle, normalize_surface_file, normalize_surface_text
from .models.ast import BundleNode
from .normalizer import NormalizationError, NormalizationResult, Normalizer
from .schema import SchemaValidationError, SchemaViolation

__all__ = [
    "SPEC_VERSION",
    "BundleNode",
    "NormalizationError",
    "NormalizationResult",
    "Normalizer",
    "SchemaValidationError",
    "SchemaViolation",
    "load_surface_bundle",
    "normalize_surface_file",
    "normalize_surface_text",
]
