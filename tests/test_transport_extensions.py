"""Tests for advanced transport engine (T2) functions."""

from __future__ import annotations

import pytest
import limnalis.runtime.builtins as builtins_mod

from limnalis.models.ast import (
    BridgeNode,
    DegradationPolicyNode,
    DestinationCompletionPolicy,
    FacetValueMap,
    FramePatternNode,
    TransportHop,
    TransportNode,
    TransportPlan,
)
from limnalis.models.conformance import TransportTrace
from limnalis.runtime.builtins import (
    _build_transport_trace,
    apply_destination_completion_policy,
    execute_transport_chain,
    execute_transport_with_degradation_policy,
    validate_claim_map_result,
)
from limnalis.runtime.models import (
    EvalNode,
    MachineState,
    StepContext,
    TransportChainResult,
    TransportResult,
)
from limnalis.models.ast import FrameNode


# ===================================================================
# Helpers
# ===================================================================


def _frame_pattern(**facets) -> FramePatternNode:
    return FramePatternNode(facets=FacetValueMap(**facets))


def _step_ctx() -> StepContext:
    return StepContext(
        effective_frame=FrameNode(
            system="sys", namespace="ns", scale="macro", task="predict", regime="standard"
        ),
    )


def _machine_state() -> MachineState:
    return MachineState()


def _bridge(
    id: str = "br1",
    mode: str = "degrade",
    preserve: list[str] | None = None,
    lose: list[str] | None = None,
    gain: list[str] | None = None,
    risk: list[str] | None = None,
    preconditions: list[str] | None = None,
    claim_map: str | None = None,
) -> BridgeNode:
    transport_kwargs: dict = {"mode": mode}
    if mode == "remap_recompute":
        transport_kwargs["claimMap"] = claim_map or "default_map"
    if preconditions:
        transport_kwargs["preconditions"] = preconditions
    return BridgeNode(
        id=id,
        **{"from": _frame_pattern(system="src")},
        to=_frame_pattern(system="dst"),
        via="via1",
        preserve=preserve or ["scale"],
        lose=lose or ["observer"],
        gain=gain or [],
        risk=risk or [],
        transport=TransportNode(**transport_kwargs),
    )


def _hop(bridge_id: str = "br1", status: str = "transported") -> TransportHop:
    return TransportHop(
        bridge_id=bridge_id,
        src_frame="src",
        dst_frame="dst",
        status=status,
        loss=["observer"],
        gain=[],
        risk=[],
        provenance=[bridge_id],
    )


# ===================================================================
# Test: transport chain
# ===================================================================


class TestTransportChain:
    def test_transport_chain_single_hop(self):
        """Execute a chain with one bridge, verify TransportChainResult."""
        bridge = _bridge(id="br1", mode="preserve")
        plan = TransportPlan(id="plan1", hops=[_hop("br1")])
        bridges = {"br1": bridge}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}}

        result, new_ms, diags = execute_transport_chain(
            plan, bridges, step_ctx, ms, services
        )

        assert isinstance(result, TransportChainResult)
        assert result.plan_id == "plan1"
        assert len(result.per_hop) == 1
        # Status should not be blocked since bridge exists and preconditions pass
        assert result.status in ("preserved", "transported", "degraded", "pattern_only")

    def test_transport_chain_multi_hop(self):
        """Execute chain with 2 bridges, verify per-hop provenance."""
        br1 = _bridge(id="br1", mode="preserve")
        br2 = _bridge(id="br2", mode="preserve")
        plan = TransportPlan(
            id="plan2",
            hops=[_hop("br1"), _hop("br2")],
        )
        bridges = {"br1": br1, "br2": br2}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}}

        result, _, diags = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        assert isinstance(result, TransportChainResult)
        assert len(result.per_hop) == 2
        assert "plan2" in result.provenance

    def test_transport_chain_fail_fast(self):
        """Chain with failure_mode='fail_fast', missing second bridge, verify chain stops."""
        br1 = _bridge(id="br1", mode="preserve")
        plan = TransportPlan(
            id="plan_ff",
            hops=[_hop("br1"), _hop("br_missing")],
            failure_mode="fail_fast",
        )
        bridges = {"br1": br1}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}}

        result, _, diags = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        assert result.status == "blocked"
        # fail_fast should stop after the missing bridge (2 hops attempted, chain stops at missing)
        assert len(result.per_hop) == 2

    def test_transport_chain_best_effort(self):
        """Chain with failure_mode='best_effort', missing second bridge, verify continues."""
        br1 = _bridge(id="br1", mode="preserve")
        br3 = _bridge(id="br3", mode="preserve")
        plan = TransportPlan(
            id="plan_be",
            hops=[_hop("br1"), _hop("br_missing"), _hop("br3")],
            failure_mode="best_effort",
        )
        bridges = {"br1": br1, "br3": br3}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}}

        result, _, diags = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        # best_effort continues past the missing bridge
        assert len(result.per_hop) == 3
        # Overall status should be blocked because one hop failed
        assert result.status == "blocked"

    def test_transport_chain_first_hop_uses_existing_aggregate_for_preconditions(self):
        """First hop preconditions should evaluate against real source aggregate when available."""
        bridge = _bridge(id="br1", mode="preserve", preconditions=["decisive_truth"])
        plan = TransportPlan(id="plan_pre", hops=[_hop("br1")])
        bridges = {"br1": bridge}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {"claim1": EvalNode(truth="T", reason="seeded")}}

        result, _, _ = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        assert result.per_hop[0].status != "blocked"

    def test_transport_chain_status_pattern_only_when_no_transport_executes(self):
        """When all hops are pattern_only/metadata_only, chain should not report transported."""
        bridge = _bridge(id="br1", mode="preserve")
        plan = TransportPlan(id="plan_pattern", hops=[_hop("br1")])
        bridges = {"br1": bridge}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}, "__transport_queries__": []}

        result, _, _ = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        assert result.per_hop[0].status == "pattern_only"
        assert result.status == "pattern_only"

    def test_transport_chain_first_hop_preconditions_use_target_claim(self):
        """First-hop precondition should bind to the transported claim, not arbitrary dict order."""
        bridge = _bridge(id="br1", mode="preserve", preconditions=["decisive_truth"])
        plan = TransportPlan(id="plan_targeted", hops=[_hop("br1")])
        bridges = {"br1": bridge}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {
            "__transport_queries__": [{"id": "tq1", "bridgeId": "br1", "claimId": "target_claim"}],
            "__per_claim_aggregates__": {
                "other_claim": EvalNode(truth="F", reason="unrelated"),
                "target_claim": EvalNode(truth="T", reason="transported"),
            },
        }

        result, _, _ = execute_transport_chain(plan, bridges, step_ctx, ms, services)

        assert result.per_hop[0].status != "blocked"

    def test_transport_chain_passes_prior_hop_dst_to_subsequent_hop_execution(self, monkeypatch):
        """Second-hop execution should see previous hop dstAggregate via per-claim aggregates."""
        br1 = _bridge(id="br1", mode="preserve")
        br2 = _bridge(id="br2", mode="preserve")
        plan = TransportPlan(id="plan_prog", hops=[_hop("br1"), _hop("br2")], failure_mode="best_effort")
        bridges = {"br1": br1, "br2": br2}
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {
            "__transport_queries__": [
                {"id": "q1", "bridgeId": "br1", "claimId": "c1"},
                {"id": "q2", "bridgeId": "br2", "claimId": "c1"},
            ],
            "__per_claim_aggregates__": {"c1": EvalNode(truth="T", reason="seed")},
        }

        call_truths: list[str] = []
        orig_execute_transport = builtins_mod.execute_transport

        def wrapped_execute_transport(bridge, step_ctx, machine_state, services):
            claim_eval = services.get("__per_claim_aggregates__", {}).get("c1")
            call_truths.append(claim_eval.truth if claim_eval is not None else "N")
            if bridge.id == "br1":
                return (
                    TransportResult(
                        status="transported",
                        srcAggregate=EvalNode(truth="T", reason="src"),
                        dstAggregate=EvalNode(truth="F", reason="hop1_dst"),
                        metadata={},
                        provenance=[bridge.id],
                    ),
                    machine_state,
                    [],
                )
            return orig_execute_transport(bridge, step_ctx, machine_state, services)

        monkeypatch.setattr(builtins_mod, "execute_transport", wrapped_execute_transport)
        try:
            execute_transport_chain(plan, bridges, step_ctx, ms, services)
        finally:
            monkeypatch.setattr(builtins_mod, "execute_transport", orig_execute_transport)

        assert len(call_truths) >= 2
        assert call_truths[0] == "T"
        assert call_truths[1] == "F"


# ===================================================================
# Test: degradation policy
# ===================================================================


class TestDegradationPolicy:
    def test_degradation_policy_default(self):
        """DegradationPolicyNode(kind='default'), verify existing behavior preserved."""
        bridge = _bridge(id="br_dp", mode="degrade")
        policy = DegradationPolicyNode(id="dp1", kind="default")
        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {"__per_claim_aggregates__": {}}

        result, _, diags = execute_transport_with_degradation_policy(
            bridge, step_ctx, ms, services, degradation_policy=policy
        )

        assert isinstance(result, TransportResult)
        assert result.degradation_policy_used == "dp1"

    def test_degradation_policy_custom_binding(self):
        """Custom degradation with binding in services."""
        bridge = _bridge(id="br_custom", mode="degrade")
        policy = DegradationPolicyNode(id="dp_custom", kind="custom", binding="my_handler")

        def my_handler(bridge, step_ctx, machine_state, services, policy):
            return TransportResult(
                status="degraded",
                srcAggregate=EvalNode(truth="T", reason="custom_src"),
                dstAggregate=EvalNode(truth="T", reason="custom_dst"),
                metadata={"custom": True},
                provenance=["custom_handler"],
            )

        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {
            "__per_claim_aggregates__": {},
            "__degradation_handlers__": {"my_handler": my_handler},
        }

        result, _, diags = execute_transport_with_degradation_policy(
            bridge, step_ctx, ms, services, degradation_policy=policy
        )

        assert result.degradation_policy_used == "dp_custom"
        assert result.metadata.get("custom") is True

    def test_degradation_policy_max_loss_exceeded(self):
        """max_loss set, loss exceeds it, verify blocked status."""
        # Bridge with 1 preserve and 3 lose => loss_ratio = 3/4 = 0.75
        bridge = _bridge(
            id="br_maxloss",
            mode="degrade",
            preserve=["scale"],
            lose=["observer", "version", "task"],
        )
        policy = DegradationPolicyNode(
            id="dp_maxloss", kind="custom", binding="simple_degrade", max_loss=0.5
        )

        def simple_degrade(bridge, step_ctx, machine_state, services, policy):
            return TransportResult(
                status="degraded",
                srcAggregate=EvalNode(truth="T"),
                dstAggregate=EvalNode(truth="T"),
                metadata={},
                provenance=["simple"],
            )

        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {
            "__per_claim_aggregates__": {},
            "__degradation_handlers__": {"simple_degrade": simple_degrade},
        }

        result, _, diags = execute_transport_with_degradation_policy(
            bridge, step_ctx, ms, services, degradation_policy=policy
        )

        assert result.status == "blocked"
        assert any(d["code"] == "degradation_exceeds_max_loss" for d in diags)

    def test_degradation_policy_preserve_fields(self):
        """Verify preserve_fields are kept from src to dst."""
        bridge = _bridge(id="br_pf", mode="degrade")
        policy = DegradationPolicyNode(
            id="dp_pf", kind="custom", binding="pf_handler",
            preserve_fields=["reason"],
        )

        def pf_handler(bridge, step_ctx, machine_state, services, policy):
            return TransportResult(
                status="degraded",
                srcAggregate=EvalNode(truth="T", reason="original_reason"),
                dstAggregate=EvalNode(truth="F", reason="degraded_reason"),
                metadata={},
                provenance=["pf"],
            )

        step_ctx = _step_ctx()
        ms = _machine_state()
        services: dict = {
            "__per_claim_aggregates__": {},
            "__degradation_handlers__": {"pf_handler": pf_handler},
        }

        result, _, diags = execute_transport_with_degradation_policy(
            bridge, step_ctx, ms, services, degradation_policy=policy
        )

        # preserve_fields copies "reason" from src to dst
        assert result.dstAggregate is not None
        assert result.dstAggregate.reason == "original_reason"


# ===================================================================
# Test: claim map validation
# ===================================================================


class TestClaimMapValidation:
    def test_claim_map_validation_valid(self):
        """Valid claim map output, no diagnostics."""
        bridge = _bridge(id="br_cm", mode="remap_recompute")
        transport = bridge.transport
        output = {"mappedClaim": "mapped_c1", "per_evaluator": {}}

        diags = validate_claim_map_result(output, bridge, transport, "c1", {})

        assert len(diags) == 0

    def test_claim_map_validation_empty(self):
        """Empty claim map, verify transport_mapping_missing diagnostic."""
        bridge = _bridge(id="br_cm2", mode="remap_recompute")
        transport = bridge.transport

        diags = validate_claim_map_result(None, bridge, transport, "c1", {})

        assert len(diags) == 1
        assert diags[0]["code"] == "transport_mapping_missing"

    def test_claim_map_validation_invalid_evaluator(self):
        """Invalid evaluator reference, verify diagnostic."""
        bridge = _bridge(id="br_cm3", mode="remap_recompute")
        # Create a transport node with dstEvaluators set
        transport = TransportNode(
            mode="remap_recompute",
            claimMap="map1",
            dstEvaluators=["ev_dst1"],
        )
        output = {
            "mappedClaim": "mapped_c1",
            "per_evaluator": {"ev_invalid": EvalNode(truth="T")},
        }

        diags = validate_claim_map_result(output, bridge, transport, "c1", {})

        assert any(d["code"] == "transport_mapping_invalid" for d in diags)


# ===================================================================
# Test: destination completion
# ===================================================================


class TestDestinationCompletion:
    def test_destination_completion_none(self):
        """strategy='none', no changes."""
        bridge = _bridge(id="br_dc1")
        result = TransportResult(
            status="transported", metadata={"existing": "value"}, provenance=[]
        )
        policy = DestinationCompletionPolicy(id="dc_none", strategy="none")

        updated, diags = apply_destination_completion_policy(result, policy, bridge, {})

        assert len(diags) == 0
        assert "completion:none" in updated.completion_actions

    def test_destination_completion_infer_defaults(self):
        """strategy='infer_defaults', verify defaults applied."""
        bridge = _bridge(id="br_dc2")
        result = TransportResult(
            status="transported", metadata={}, provenance=[]
        )
        policy = DestinationCompletionPolicy(
            id="dc_infer",
            strategy="infer_defaults",
            defaults={"observer": "default_obs", "version": "1.0"},
        )

        updated, diags = apply_destination_completion_policy(result, policy, bridge, {})

        assert len(diags) == 0
        assert updated.metadata.get("observer") == "default_obs"
        assert updated.metadata.get("version") == "1.0"
        assert any("infer_defaults" in a for a in updated.completion_actions)

    def test_destination_completion_require_explicit_missing(self):
        """Missing facets, verify diagnostic."""
        bridge = _bridge(id="br_dc3", preserve=["scale", "observer"])
        result = TransportResult(
            status="transported", metadata={}, provenance=[]
        )
        policy = DestinationCompletionPolicy(
            id="dc_explicit", strategy="require_explicit"
        )

        updated, diags = apply_destination_completion_policy(result, policy, bridge, {})

        assert len(diags) == 1
        assert diags[0]["code"] == "destination_completion_missing_facets"
        assert "scale" in diags[0]["missing_facets"] or "observer" in diags[0]["missing_facets"]

    def test_destination_completion_binding(self):
        """strategy='binding', verify service called."""
        bridge = _bridge(id="br_dc4")
        result = TransportResult(
            status="transported", metadata={}, provenance=[]
        )
        policy = DestinationCompletionPolicy(
            id="dc_bind", strategy="binding", binding="my_completer"
        )

        called = []

        def my_completer(result, bridge, services, policy):
            called.append(True)
            return {"completed": True}

        services = {"__completion_handlers__": {"my_completer": my_completer}}

        updated, diags = apply_destination_completion_policy(
            result, policy, bridge, services
        )

        assert len(called) == 1
        assert updated.metadata.get("completed") is True


# ===================================================================
# Test: build transport trace
# ===================================================================


class TestBuildTransportTrace:
    def test_build_transport_trace(self):
        """Verify trace construction with hops, loss, gain."""
        hop1 = _hop("br1")
        hop2 = TransportHop(
            bridge_id="br2",
            src_frame="mid",
            dst_frame="dst",
            status="transported",
            loss=["version"],
            gain=["derived_metric"],
            risk=["aliasing"],
            provenance=["br2"],
        )
        r1 = TransportResult(status="transported", provenance=["br1"])
        r2 = TransportResult(status="transported", provenance=["br2"])

        trace = _build_transport_trace(
            [(hop1, r1), (hop2, r2)],
            precondition_outcomes={"br1": True, "br2": True},
            mapping_steps=["step1"],
        )

        assert isinstance(trace, TransportTrace)
        assert len(trace.hops) == 2
        assert "observer" in trace.total_loss
        assert "version" in trace.total_loss
        assert "derived_metric" in trace.total_gain
        assert trace.precondition_outcomes == {"br1": True, "br2": True}
