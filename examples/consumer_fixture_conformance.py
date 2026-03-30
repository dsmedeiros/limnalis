"""Example: Run a conformance case using the fixture plugin pack.

Demonstrates loading the fixture corpus, running a case through the
conformance harness, and inspecting results. Uses only public API imports.
"""
from __future__ import annotations

from limnalis.api.conformance import compare_case, load_corpus_from_default, run_case


def main() -> None:
    corpus = load_corpus_from_default()
    print(f"Loaded corpus with {len(corpus.cases)} cases:")
    for case in corpus.cases:
        print(f"  {case.summary()}")

    # Pick case A1 (or first available)
    target_id = "A1"
    case = corpus.get_case(target_id)
    if case is None:
        case = corpus.cases[0]
        print(f"\nCase '{target_id}' not found, using '{case.id}' instead.")
    else:
        print(f"\nRunning case '{case.id}': {case.name}")

    # Run the case through the conformance harness
    run_result = run_case(case, corpus)

    if run_result.error:
        print(f"  Runner error: {run_result.error}")
        return

    # Compare actual results to expected
    comparison = compare_case(case, run_result)
    print(f"\nResult: {comparison.summary()}")

    if not comparison.passed:
        print("\nMismatches:")
        for m in comparison.mismatches:
            print(f"  {m}")


if __name__ == "__main__":
    main()
