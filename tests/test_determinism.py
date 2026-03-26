"""Determinism tests: verify that the full pipeline produces identical outputs
across multiple runs for every fixture case.

T7: Determinism + property tests (determinism portion).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helper: load the fixture corpus once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def corpus():
    from limnalis.conformance.fixtures import load_corpus_from_default
    return load_corpus_from_default()


@pytest.fixture(scope="module")
def corpus_case_ids(corpus):
    return corpus.case_ids()


# ---------------------------------------------------------------------------
# T7.1 – Full pipeline determinism: parse -> normalize -> evaluate twice
# ---------------------------------------------------------------------------


class TestPipelineDeterminism:
    """Run each fixture case through the full pipeline twice and compare outputs."""

    def test_full_pipeline_determinism(self, corpus) -> None:
        """For each fixture case, run the pipeline twice and assert identical outputs."""
        from limnalis.conformance.runner import run_case

        for case in corpus.cases:
            result1 = run_case(case, corpus)
            result2 = run_case(case, corpus)

            # Both should have the same error state
            assert (result1.error is None) == (result2.error is None), (
                f"Case {case.id}: error state differs between runs"
            )

            if result1.error is not None:
                assert result1.error == result2.error, (
                    f"Case {case.id}: error messages differ"
                )
                continue

            # Both should have bundle results
            assert (result1.bundle_result is not None) == (result2.bundle_result is not None), (
                f"Case {case.id}: bundle_result presence differs"
            )

            if result1.bundle_result is None:
                continue

            # Compare serialized JSON for exact equality
            json1 = result1.bundle_result.model_dump_json(exclude_none=True)
            json2 = result2.bundle_result.model_dump_json(exclude_none=True)
            assert json1 == json2, (
                f"Case {case.id}: pipeline outputs differ between runs"
            )


# ---------------------------------------------------------------------------
# T7.2 – Normalizer diagnostics ordering is stable
# ---------------------------------------------------------------------------


class TestNormalizerDeterminism:
    """Verify that normalizer diagnostics have stable ordering."""

    def test_normalizer_diagnostics_ordering_stable(self, corpus) -> None:
        from limnalis.loader import normalize_surface_text

        skipped = []
        tested = 0
        for case in corpus.cases:
            try:
                result1 = normalize_surface_text(case.source, validate_schema=False)
                result2 = normalize_surface_text(case.source, validate_schema=False)
            except Exception as exc:
                skipped.append((case.id, type(exc).__name__))
                continue
            tested += 1
            assert result1.diagnostics == result2.diagnostics, (
                f"Case {case.id}: normalizer diagnostics ordering differs between runs"
            )
        assert tested > 0, f"All cases were skipped, none tested: {skipped}"


# ---------------------------------------------------------------------------
# T7.3 – Provenance fields maintain stable ordering
# ---------------------------------------------------------------------------


class TestProvenanceStability:
    """Verify that provenance fields in evaluation results are deterministically ordered."""

    def test_provenance_ordering_stable(self, corpus) -> None:
        from limnalis.conformance.runner import run_case

        skipped = []
        tested = 0
        for case in corpus.cases:
            result1 = run_case(case, corpus)
            result2 = run_case(case, corpus)

            if result1.bundle_result is None or result2.bundle_result is None:
                skipped.append((case.id, "no_bundle_result"))
                continue

            tested += 1
            for sess1, sess2 in zip(
                result1.bundle_result.session_results,
                result2.bundle_result.session_results,
            ):
                for step1, step2 in zip(sess1.step_results, sess2.step_results):
                    # Check per-claim aggregate provenance
                    for claim_id in step1.per_claim_aggregates:
                        agg1 = step1.per_claim_aggregates[claim_id]
                        agg2 = step2.per_claim_aggregates.get(claim_id)
                        if agg2 is not None:
                            assert agg1.provenance == agg2.provenance, (
                                f"Case {case.id}, claim {claim_id}: "
                                "provenance ordering differs between runs"
                            )
        assert tested > 0, f"All cases were skipped, none tested: {skipped}"


# ---------------------------------------------------------------------------
# T7.4 – Conformance report output is stable across runs
# ---------------------------------------------------------------------------


class TestConformanceReportStability:
    """Verify that conformance report output is identical across runs."""

    def test_json_report_stable(self, corpus, capsys) -> None:
        from limnalis.cli import main

        # Run report twice
        code1 = main(["conformance", "report", "--format", "json"])
        out1 = capsys.readouterr().out

        code2 = main(["conformance", "report", "--format", "json"])
        out2 = capsys.readouterr().out

        assert code1 == code2
        # Parse as JSON and compare structurally
        report1 = json.loads(out1)
        report2 = json.loads(out2)
        assert report1 == report2, "Conformance JSON reports differ between runs"

    def test_markdown_report_stable(self, corpus, capsys) -> None:
        from limnalis.cli import main

        code1 = main(["conformance", "report", "--format", "markdown"])
        out1 = capsys.readouterr().out

        code2 = main(["conformance", "report", "--format", "markdown"])
        out2 = capsys.readouterr().out

        assert code1 == code2
        assert out1 == out2, "Conformance Markdown reports differ between runs"
