"""Example: Run the B1 grid bundle using the grid example plugin pack.

Demonstrates registering domain-specific plugins and running a full
evaluation through the public API. Uses only limnalis.api imports
and the grid_example plugin pack.
"""
from __future__ import annotations

from limnalis.api.conformance import compare_case, load_corpus_from_default, run_case
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.plugins.grid_example import register_grid_plugins


def main() -> None:
    # -- Plugin registration demo --
    registry = PluginRegistry()
    register_grid_plugins(registry)

    print("Grid plugin registry contents:")
    for kind in registry.kinds():
        plugins = registry.list_plugins(kind)
        print(f"  {kind}: {len(plugins)} plugin(s)")
        for p in plugins:
            print(f"    - {p.plugin_id}: {p.description}")

    services = build_services_from_registry(registry)
    print(f"\nServices built: {sorted(services.keys())}")

    # -- Run B1 through the conformance harness --
    corpus = load_corpus_from_default()
    case = corpus.get_case("B1")
    if case is None:
        print("\nCase B1 not found in corpus.")
        return

    print(f"\nRunning case '{case.id}': {case.name}")
    run_result = run_case(case, corpus)

    if run_result.error:
        print(f"  Runner error: {run_result.error}")
        return

    comparison = compare_case(case, run_result)
    print(f"Result: {comparison.summary()}")

    if not comparison.passed:
        print("\nMismatches:")
        for m in comparison.mismatches:
            print(f"  {m}")


if __name__ == "__main__":
    main()
