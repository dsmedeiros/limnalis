"""Example: Parse and normalize a Limnalis surface file.

Demonstrates the minimal public API for parsing .lmn surface syntax
into a canonical AST. Uses only limnalis.api imports.
"""
from __future__ import annotations

from pathlib import Path

from limnalis.api.normalizer import normalize_surface_file


def main() -> None:
    lmn_path = Path(__file__).parent / "minimal_bundle.lmn"
    result = normalize_surface_file(lmn_path)

    bundle = result.canonical_ast
    if bundle is None:
        print("ERROR: normalization produced no AST")
        for d in result.diagnostics:
            print(f"  {d}")
        return

    print(f"Bundle ID : {bundle.id}")
    print(f"Frame     : {bundle.frame}")
    print(f"Evaluators: {len(bundle.evaluators)}")
    print(f"Claim blocks: {len(bundle.claimBlocks)}")

    for block in bundle.claimBlocks:
        print(f"\n  Block '{block.id}' (stratum={block.stratum})")
        for claim in block.claims:
            print(f"    Claim '{claim.id}' kind={claim.kind}")


if __name__ == "__main__":
    main()
