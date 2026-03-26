"""Limnalis reference Python scaffold."""

from .version import PACKAGE_VERSION, SPEC_VERSION

__version__ = PACKAGE_VERSION

from .loader import load_surface_bundle, normalize_surface_file, normalize_surface_text
from .models.ast import BundleNode
from .normalizer import NormalizationError, NormalizationResult, Normalizer
from .schema import SchemaValidationError, SchemaViolation

__all__ = [
    "__version__",
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
