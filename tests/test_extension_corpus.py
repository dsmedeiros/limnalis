"""Tests for the project-authored extension corpus (milestone 7, T5).

The extension corpus (fixtures/limnalis_extension_corpus_v0.1.{yaml,json})
closes the coverage gaps the vendored corpus is blind to (spec §17.4):

- logical connectives computed LIVE through sub-expression evaluation
  (atom-level fixture bindings in limnalis.plugins.fixtures, not the
  claim-id-keyed echo the vendored corpus runs on),
- unparenthesized operator precedence per the recovered EBNF A.9,
- session semantics added in wave 2: EvaluationSession.shared_state
  (§16.6.3) exercised through the spec §17.2 A11 narrative
  (test://baseline/by_context_v1), and EvaluationStep.claim_subset
  (§16.2.1).

Contract enforced here:
(a) the extension corpus validates against the VENDORED fixture-corpus
    schema with zero errors;
(b) the YAML and JSON twins parse to identical data;
(c) every extension case runs through the real conformance machinery
    (load_corpus + run_case + compare_case) and passes with zero
    mismatches;
(d) a canary proves test://eval/atoms_v2 evaluates ATOMS — composition is
    computed, not claim-id keyed.
"""

from __future__ import annotations

import copy
import json

import pytest
import yaml

from limnalis.conformance.compare import compare_case
from limnalis.conformance.fixtures import load_corpus
from limnalis.conformance.runner import run_case
from limnalis.loader import normalize_surface_text
from limnalis.models.ast import FrameNode
from limnalis.plugins.fixtures import (
    ATOMS_V2_URI,
    FixtureEvalHandlerForEvaluator,
    build_live_fixture_services,
)
from limnalis.runtime.builtins import eval_expr as builtin_eval_expr
from limnalis.runtime.models import MachineState, StepContext, TruthCore
from limnalis.schema import collect_validation_errors, fixtures_dir

EXTENSION_CORPUS_YAML = fixtures_dir() / "limnalis_extension_corpus_v0.1.yaml"
EXTENSION_CORPUS_JSON = fixtures_dir() / "limnalis_extension_corpus_v0.1.json"

EXTENSION_CASE_IDS = ["D1", "D2", "D3", "D4", "D5", "D6"]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def extension_corpus():
    return load_corpus(EXTENSION_CORPUS_YAML)


def _run_and_compare(corpus, case_id: str):
    case = corpus.get_case(case_id)
    assert case is not None, f"Case {case_id} not found in extension corpus"
    result = run_case(case, corpus)
    assert result.error is None, f"Runner error for {case_id}: {result.error}"
    comparison = compare_case(case, result)
    if not comparison.passed:
        details = "\n".join(str(m) for m in comparison.mismatches)
        pytest.fail(f"Extension case {case_id} failed:\n{details}")
    return result


# ---------------------------------------------------------------------------
# (a) Schema validation against the VENDORED fixture-corpus schema
# ---------------------------------------------------------------------------


class TestExtensionCorpusSchema:
    """The extension corpus must validate against the vendored schema."""

    def test_yaml_validates_against_vendored_schema_zero_errors(self):
        data = yaml.safe_load(EXTENSION_CORPUS_YAML.read_text(encoding="utf-8"))
        violations = collect_validation_errors(data, "fixture_corpus")
        assert violations == [], "\n".join(
            f"{v.path}: {v.message}" for v in violations
        )

    def test_json_twin_validates_against_vendored_schema_zero_errors(self):
        data = json.loads(EXTENSION_CORPUS_JSON.read_text(encoding="utf-8"))
        violations = collect_validation_errors(data, "fixture_corpus")
        assert violations == [], "\n".join(
            f"{v.path}: {v.message}" for v in violations
        )

    def test_track_labels_respect_vendored_enum(self):
        """The vendored schema pins track to the enum ["A", "B"]; extension
        cases carry track "A" with the reserved D id prefix (documented in
        the corpus meta.purpose and ast_decisions)."""
        data = yaml.safe_load(EXTENSION_CORPUS_YAML.read_text(encoding="utf-8"))
        for case in data["cases"]:
            assert case["track"] == "A"
            assert case["id"].startswith("D")

    def test_all_fixture_bindings_use_test_scheme(self):
        data = yaml.safe_load(EXTENSION_CORPUS_YAML.read_text(encoding="utf-8"))
        fixture_ids = [f["id"] for f in data["fixtures"]]
        assert fixture_ids, "extension corpus must declare its fixture bindings"
        for fixture_id in fixture_ids:
            assert fixture_id.startswith("test://"), fixture_id


# ---------------------------------------------------------------------------
# (b) YAML / JSON twin parity
# ---------------------------------------------------------------------------


class TestExtensionCorpusTwinParity:
    """The mechanically generated JSON twin must carry identical data."""

    def test_yaml_and_json_twins_parse_to_identical_data(self):
        yaml_data = yaml.safe_load(EXTENSION_CORPUS_YAML.read_text(encoding="utf-8"))
        json_data = json.loads(EXTENSION_CORPUS_JSON.read_text(encoding="utf-8"))
        assert yaml_data == json_data

    def test_twins_load_to_identical_corpora(self):
        corpus_yaml = load_corpus(EXTENSION_CORPUS_YAML)
        corpus_json = load_corpus(EXTENSION_CORPUS_JSON)
        assert corpus_yaml.case_ids() == corpus_json.case_ids()
        assert [b.id for b in corpus_yaml.bindings] == [
            b.id for b in corpus_json.bindings
        ]
        for case_id in corpus_yaml.case_ids():
            assert (
                corpus_yaml.get_case(case_id).expected
                == corpus_json.get_case(case_id).expected
            )


# ---------------------------------------------------------------------------
# (c) Every case runs through the real conformance machinery and passes
# ---------------------------------------------------------------------------


class TestExtensionCasesConformance:
    """load_corpus + run_case + compare_case, zero mismatches per case."""

    def test_expected_case_roster(self, extension_corpus):
        assert extension_corpus.case_ids() == EXTENSION_CASE_IDS

    def test_d1_live_conjunction(self, extension_corpus):
        result = _run_and_compare(extension_corpus, "D1")
        # Acceptance criterion: B AND N = F computed by the LIVE truth
        # algebra (not echoed) in at least one extension case.
        step = result.bundle_result.session_results[0].step_results[0]
        assert step.per_claim_aggregates["c1"].truth == "F"

    def test_d2_live_disjunction_negation(self, extension_corpus):
        _run_and_compare(extension_corpus, "D2")

    def test_d3_derived_connectives_canonical_spellings(self, extension_corpus):
        result = _run_and_compare(extension_corpus, "D3")
        # The '->' and '<=>' alias spellings must normalize with structure.
        bundle = result.bundle
        claims = {
            c.id: c for blk in bundle.claimBlocks for c in blk.claims
        }
        assert claims["c1"].expr.node == "LogicalExpr"
        assert claims["c1"].expr.op == "implies"
        assert claims["c2"].expr.node == "LogicalExpr"
        assert claims["c2"].expr.op == "iff"

    def test_d4_unparenthesized_precedence(self, extension_corpus):
        result = _run_and_compare(extension_corpus, "D4")
        # Pin the EBNF A.9 tree shapes: OR splits before AND (loosest-first).
        bundle = result.bundle
        claims = {
            c.id: c for blk in bundle.claimBlocks for c in blk.claims
        }
        for claim_id in ("c1", "c2", "c3"):
            expr = claims[claim_id].expr
            assert expr.node == "LogicalExpr" and expr.op == "or", (
                f"{claim_id}: expected an OR root, got "
                f"{getattr(expr, 'op', expr.node)}"
            )
        # c1: t AND f OR t -> or(and(t, f), t)
        c1 = claims["c1"].expr
        assert c1.args[0].node == "LogicalExpr" and c1.args[0].op == "and"
        assert [a.name for a in c1.args[0].args] == ["t", "f"]
        assert c1.args[1].name == "t"
        # c3: n OR t AND b -> or(n, and(t, b))
        c3 = claims["c3"].expr
        assert c3.args[0].name == "n"
        assert c3.args[1].node == "LogicalExpr" and c3.args[1].op == "and"
        assert [a.name for a in c3.args[1].args] == ["t", "b"]

    def test_d5_shared_state_narrative(self, extension_corpus):
        """Spec §17.2 A11 narrative: fixed-baseline caching under
        shared_state=true vs re-initialization under shared_state=false,
        resolved through services["baseline_criterion_resolver"]."""
        result = _run_and_compare(extension_corpus, "D5")
        sessions = {
            s.session_id: s for s in result.bundle_result.session_results
        }
        shared_steps = {s.step_id: s for s in sessions["s_shared"].step_results}
        isolated_steps = {
            s.step_id: s for s in sessions["s_isolated"].step_results
        }

        # s_shared s2: b_fixed reuses the session-cached value 10 while
        # b_step re-resolves to 20 under the (t2, stress) context.
        shared_s2 = shared_steps["s2"].machine_state.baseline_store
        assert shared_s2["b_fixed"].value == 10
        assert shared_s2["b_step"].value == 20

        # s_isolated s2: shared_state=false re-initializes the fixed
        # baseline per step, so b_fixed observes 20 as well.
        isolated_s2 = isolated_steps["s2"].machine_state.baseline_store
        assert isolated_s2["b_fixed"].value == 20
        assert isolated_s2["b_step"].value == 20

        # Both sessions observe 10/10 at s1.
        for steps in (shared_steps, isolated_steps):
            s1 = steps["s1"].machine_state.baseline_store
            assert s1["b_fixed"].value == 10
            assert s1["b_step"].value == 10

    def test_d6_claim_subset_restriction(self, extension_corpus):
        """§16.2.1: the excluded claim is absent from step-2 results and
        excluded from block folding."""
        result = _run_and_compare(extension_corpus, "D6")
        steps = result.bundle_result.session_results[0].step_results
        step1, step2 = steps[0], steps[1]

        assert set(step1.per_claim_aggregates) == {"c_keep", "c_drop"}
        assert set(step2.per_claim_aggregates) == {"c_keep"}
        assert "c_drop" not in step2.per_claim_per_evaluator

        block1 = {b.block_id: b for b in step1.block_results}["local#1"]
        block2 = {b.block_id: b for b in step2.block_results}["local#1"]
        assert block1.claims == ["c_keep", "c_drop"]
        assert block2.claims == ["c_keep"]
        # Excluding the F claim flips the block fold from F to T.
        assert block1.aggregate.truth == "F"
        assert block2.aggregate.truth == "T"

    def test_extension_results_are_deterministic(self, extension_corpus):
        """Run every extension case twice; results must be identical."""
        for case in extension_corpus.cases:
            result1 = run_case(case, extension_corpus)
            result2 = run_case(case, extension_corpus)
            assert result1.error is None and result2.error is None
            assert (
                result1.bundle_result.model_dump()
                == result2.bundle_result.model_dump()
            ), f"non-deterministic results for {case.id}"


# ---------------------------------------------------------------------------
# (d) Canary: atoms_v2 evaluates ATOMS (composition != claim-id keying)
# ---------------------------------------------------------------------------


_CANARY_SOURCE = """bundle canary_atoms_v2 {
  frame {
    system Test;
    namespace Logic;
    scale unit;
    task check;
    regime nominal;
  }

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v2;
  }

  resolution_policy rp0 {
    kind single;
    members [ev0];
  }

  local {
    c1: (b AND n);
  }
}"""


class TestAtomLevelCanary:
    """Prove the extension binding path is atom-level, not claim-id keyed."""

    def test_composition_differs_from_claim_id_keying(self):
        """The same claim evaluated through atoms_v2 (live §4 algebra:
        B AND N = F) and through a claim-id-keyed fixture map seeded with T
        must disagree — claim-id keying is exactly the vendored blindness
        this corpus removes."""
        bundle = normalize_surface_text(
            _CANARY_SOURCE, validate_schema=True
        ).canonical_ast
        claim = bundle.claimBlocks[0].claims[0]
        step_ctx = StepContext(
            effective_frame=FrameNode(
                system="Test",
                namespace="Logic",
                scale="unit",
                task="check",
                regime="nominal",
            )
        )

        # Live path: atoms_v2 handlers behind the real builtin eval_expr.
        live_services = build_live_fixture_services(bundle)
        assert live_services is not None
        assert "evaluator_bindings" in live_services
        live_truth, _, _ = builtin_eval_expr(
            claim, "ev0", step_ctx, MachineState(), live_services
        )
        assert live_truth.truth == "F"  # B AND N = F per spec §4

        # Claim-id-keyed path: echoes whatever the map says for c1,
        # regardless of the claim's expression.
        keyed_handler = FixtureEvalHandlerForEvaluator(
            "ev0", {"c1": {"ev0": TruthCore(truth="T")}}
        )
        keyed_truth = keyed_handler(claim.expr, claim, step_ctx, MachineState())
        assert keyed_truth.truth == "T"

        assert live_truth.truth != keyed_truth.truth

    def test_conformance_path_computes_rather_than_echoes(self, extension_corpus):
        """Mutate D1's source — swap c1 from (b AND n) to (t OR t) while
        keeping the stated expectation F. If the conformance path echoed
        claim-id-keyed expectations the tampered case would still pass; the
        live path computes T and the comparison must fail at c1."""
        case = copy.deepcopy(extension_corpus.get_case("D1"))
        assert "c1: (b AND n);" in case.source
        case.source = case.source.replace("c1: (b AND n);", "c1: (t OR t);")

        result = run_case(case, extension_corpus)
        assert result.error is None
        step = result.bundle_result.session_results[0].step_results[0]
        assert step.per_claim_aggregates["c1"].truth == "T"

        comparison = compare_case(case, result)
        assert not comparison.passed, (
            "tampered source still passed — the conformance path is echoing "
            "expectations instead of evaluating atoms"
        )
        assert any("claims.c1" in m.path for m in comparison.mismatches)

    def test_live_pack_ignores_vendored_bindings(self):
        """Bundles bound to vendored fixture URIs (test://eval/atoms_v1)
        must NOT activate the live path — the vendored corpus keeps its
        claim-id-keyed fixture evaluation."""
        vendored_source = _CANARY_SOURCE.replace(ATOMS_V2_URI, "test://eval/atoms_v1")
        bundle = normalize_surface_text(
            vendored_source, validate_schema=True
        ).canonical_ast
        assert build_live_fixture_services(bundle) is None
