"""Example: Read a ResultEnvelope JSON and generate a summary report.

Usage:
    python examples/consumers/read_result_envelope.py <result_envelope.json>

This demonstrates consuming a Limnalis evaluation result export
using only the interop API.
"""
from __future__ import annotations

import sys
from pathlib import Path

from limnalis.interop import (
    check_envelope_compatibility,
    import_result_envelope,
)


def main(path: str) -> None:
    envelope = import_result_envelope(Path(path))

    print("=== Result Envelope Summary ===")
    print(f"Spec version:    {envelope.spec_version}")
    print(f"Schema version:  {envelope.schema_version}")
    print(f"Package version: {envelope.package_version}")
    print(f"Artifact kind:   {envelope.artifact_kind}")

    if envelope.source_info:
        print(f"Source:          {envelope.source_info.path or '(unknown)'}")

    result = envelope.evaluation_result
    print(f"\nResult top-level keys: {', '.join(sorted(result.keys()))}")

    # Print counts for common result sub-structures
    for key in ("sessions", "steps", "phases", "outcomes", "verdicts"):
        if key in result and isinstance(result[key], list):
            print(f"  {key}: {len(result[key])} item(s)")

    # Compatibility check
    issues = check_envelope_compatibility(envelope)
    if issues:
        print("\nCompatibility warnings:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nEnvelope is compatible with this implementation.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(1)
    main(sys.argv[1])
