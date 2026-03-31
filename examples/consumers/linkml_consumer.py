"""Example: Load and inspect a LinkML projection artifact.

Usage:
    python examples/consumers/linkml_consumer.py <schema.linkml.yaml>

This demonstrates how a documentation or schema tool might
consume the LinkML projection without needing the Limnalis runtime.
Only PyYAML is required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def main(path: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    schema = yaml.safe_load(text)

    print("=== LinkML Schema Summary ===")
    print(f"Schema name: {schema.get('name', '(unnamed)')}")
    print(f"Title:       {schema.get('title', '(none)')}")
    print(f"ID:          {schema.get('id', '(none)')}")

    classes = schema.get("classes", {})
    enums = schema.get("enums", {})
    print(f"\nClasses: {len(classes)}")
    print(f"Enums:   {len(enums)}")

    if classes:
        print("\nClass summary:")
        for name, cls_def in sorted(classes.items()):
            attrs = cls_def.get("attributes", {}) if isinstance(cls_def, dict) else {}
            required = sum(
                1 for a in attrs.values()
                if isinstance(a, dict) and a.get("required")
            )
            print(f"  {name}: {len(attrs)} attribute(s), {required} required")

    if enums:
        print("\nEnum summary:")
        for name, enum_def in sorted(enums.items()):
            values = enum_def.get("permissible_values", {}) if isinstance(enum_def, dict) else {}
            print(f"  {name}: {len(values)} value(s)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(1)
    main(sys.argv[1])
