"""Example: Read an ASTEnvelope JSON and print bundle summary.

Usage:
    python examples/consumers/read_ast_envelope.py <envelope.json>

This demonstrates consuming a Limnalis AST export without
requiring the Limnalis runtime -- only the interop API.
"""
from __future__ import annotations

import sys
from pathlib import Path

from limnalis.interop import (
    SCHEMA_VERSION,
    SPEC_VERSION,
    check_envelope_compatibility,
    import_ast_envelope,
)


def main(path: str) -> None:
    envelope = import_ast_envelope(Path(path))

    print(f"Spec version:    {envelope.spec_version}")
    print(f"Schema version:  {envelope.schema_version}")
    print(f"Package version: {envelope.package_version}")
    print(f"Artifact kind:   {envelope.artifact_kind}")

    if envelope.source_info:
        print(f"Source path:     {envelope.source_info.path}")
        print(f"Source SHA256:   {envelope.source_info.sha256}")

    ast = envelope.normalized_ast
    print(f"\nAST top-level keys: {', '.join(sorted(ast.keys()))}")

    if "id" in ast:
        print(f"Bundle ID: {ast['id']}")

    # Count frames (claimBlocks, anchors, etc. that have frame-like structure)
    frame_keys = ["claimBlocks", "anchors", "bridges", "evidence"]
    for key in frame_keys:
        items = ast.get(key, [])
        if items:
            print(f"  {key}: {len(items)} item(s)")

    # Compatibility check
    issues = check_envelope_compatibility(envelope)
    if issues:
        print(f"\nCompatibility warnings (local: spec={SPEC_VERSION}, schema={SCHEMA_VERSION}):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nEnvelope is compatible with this implementation.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(1)
    main(sys.argv[1])
