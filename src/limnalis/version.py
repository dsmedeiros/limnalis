"""Version and build metadata for Limnalis reference implementation."""

from __future__ import annotations

PACKAGE_VERSION = "0.2.2rc1"
SPEC_VERSION = "v0.2.2"
SCHEMA_VERSION = "v0.2.2"
CORPUS_VERSION = "v0.2.2"


def get_version_info() -> dict[str, str]:
    """Return all version metadata as a dictionary."""
    return {
        "package": PACKAGE_VERSION,
        "spec": SPEC_VERSION,
        "schema": SCHEMA_VERSION,
        "corpus": CORPUS_VERSION,
    }
