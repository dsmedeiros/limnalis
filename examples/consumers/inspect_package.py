"""Example: Inspect an exchange package and summarize contents.

Usage:
    python examples/consumers/inspect_package.py <package_path>

The package can be a directory or a .zip file. This demonstrates
reading exchange package metadata using only the interop API.
"""
from __future__ import annotations

import sys

from limnalis.interop import inspect_package


def main(path: str) -> None:
    metadata = inspect_package(path)
    manifest = metadata.manifest

    print("=== Exchange Package Summary ===")
    print(f"Root path:        {metadata.root_path}")
    print(f"Format version:   {manifest.format_version}")
    print(f"Spec version:     {manifest.spec_version}")
    print(f"Schema version:   {manifest.schema_version}")
    print(f"Package version:  {manifest.package_version}")

    if manifest.created_at:
        print(f"Created at:       {manifest.created_at}")

    print(f"\nArtifact types: {', '.join(manifest.artifact_types) or '(none)'}")

    if manifest.plugin_requirements:
        print(f"Plugin requirements: {', '.join(manifest.plugin_requirements)}")
    else:
        print("Plugin requirements: (none)")

    if manifest.checksums:
        print(f"\nFile checksums ({len(manifest.checksums)}):")
        for filename, checksum in sorted(manifest.checksums.items()):
            print(f"  {filename}: {checksum[:16]}...")
    else:
        print("\nNo file checksums recorded.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(1)
    main(sys.argv[1])
