# Writing a Transport Handler

Transport handlers implement the `execute_transport` phase (phase 13), which carries evaluation results across frame boundaries via bridge declarations. This is the mechanism for cross-frame evaluation in Limnalis.

## What you'll need

- A `PluginRegistry` instance
- Understanding of bridge and transport node structure
- Familiarity with `TransportResult` (the return type)

## Transport in the Limnalis model

Bridges declare how evaluation results move between frames. Each bridge specifies:

- **Source and destination frames** (as frame patterns)
- **What is preserved, lost, gained, and at risk** during transport
- **A transport node** that controls the transport mode and policies

The transport phase executes after all per-claim evaluation, resolution, and block folding are complete.

## Transport modes

The `TransportNode` declares a mode that governs how results are carried:

| Mode | Description (spec §10.2) |
|---|---|
| `metadata_only` | Only metadata crosses the bridge; truth values are not transported |
| `preserve` | Source truth is copied only if preconditions hold and `claim.semantic_requirements ∩ bridge.lose = ∅`; otherwise the destination gets `N[transport_loss]` / `N[transport_precondition]` |
| `degrade` | Attempts preservation; when a required property is lost, **truth** weakens by the default degradation rule `T → N[transport_loss]`, `F → N[transport_loss]`, `B → B[boundary_mix]`, `N → N`, and support drops to `partial` (a custom truth/degradation policy may override this) |
| `remap_recompute` | Results are remapped and recomputed in the destination frame |

## Bridge structure

A `BridgeNode` describes the transport channel:

```python
from limnalis.api.models import BridgeNode

# BridgeNode fields:
#   id: str                    -- unique bridge identifier
#   from_: FramePatternNode    -- source frame pattern (aliased from "from" in JSON)
#   to: FramePatternNode       -- destination frame pattern
#   via: str                   -- transport mechanism identifier
#   preserve: list[str]        -- properties preserved across the bridge
#   lose: list[str]            -- properties lost during transport
#   gain: list[str]            -- properties gained at the destination
#   risk: list[str]            -- known risks (aggregation_reversal, aliasing,
#                                  temporal_smear, observer_shift)
#   transport: TransportNode   -- the transport configuration
```

The `TransportNode` within the bridge:

```python
from limnalis.api.models import TransportNode

# TransportNode fields:
#   mode: str          -- "metadata_only", "preserve", "degrade", "remap_recompute"
#   claimMap: str | None       -- optional claim mapping identifier
#   truthPolicy: str | None    -- optional truth handling policy
#   preconditions: list[str]   -- conditions that must hold for transport
#   dstEvaluators: list[str] | None  -- evaluators at the destination
#   dstResolutionPolicy: str | None  -- resolution policy at the destination
```

## The execute_transport phase

In phase 13, the runner iterates over bridges in the bundle and executes transport queries. The result is a `TransportResult` stored in `machine_state.transport_store`.

```python
from limnalis.api.results import TransportResult

# TransportResult fields:
#   status: str                    -- one of "metadata_only", "preserved",
#                                     "degraded", "transported", "blocked",
#                                     "unresolved", "pattern_only"
#   srcAggregate: EvalNode | None  -- aggregate evaluation at source
#   dstAggregate: EvalNode | None  -- aggregate evaluation at destination
#   metadata: dict                 -- transport metadata
#   mappedClaim: str | None        -- mapped claim identifier
#   per_evaluator: dict[str, EvalNode]  -- per-evaluator results at destination
#   provenance: list[str]          -- provenance trail
#   diagnostics: list[dict]        -- transport diagnostics
```

## Registering a transport handler

```python
from limnalis.api.services import PluginRegistry, TRANSPORT_HANDLER

registry = PluginRegistry()
registry.register(
    TRANSPORT_HANDLER,
    "my_transport_handler",
    my_transport_fn,
    description="My cross-frame transport handler",
)
```

## Example: metadata-only transport

A transport handler for the simplest mode, where only metadata crosses the bridge:

<!-- doc-snippet: runnable -->
```python
from limnalis.api.services import PluginRegistry, TRANSPORT_HANDLER
from limnalis.api.results import TransportResult, EvalNode


def metadata_only_transport(bridge, step_result, machine_state):
    """Transport handler that carries only metadata across the bridge.

    No truth values are transported. The destination receives a
    record of the transport with status and provenance only.
    """
    bridge_id = bridge.id
    mode = bridge.transport.mode

    if mode != "metadata_only":
        return TransportResult(
            status="blocked",
            metadata={"error": f"handler only supports metadata_only, got {mode}"},
            provenance=[bridge_id],
            diagnostics=[{
                "severity": "error",
                "code": "unsupported_transport_mode",
                "message": f"Expected metadata_only, got {mode}",
            }],
        )

    return TransportResult(
        status="metadata_only",
        metadata={
            "bridge": bridge_id,
            "source_frame": str(bridge.from_),
            "dest_frame": str(bridge.to),
            "preserved": bridge.preserve,
            "lost": bridge.lose,
        },
        provenance=[bridge_id, "metadata_only_transport"],
    )


registry = PluginRegistry()
registry.register(
    TRANSPORT_HANDLER,
    "metadata_only_v1",
    metadata_only_transport,
    description="Metadata-only transport handler",
)
```

## Example: a custom degradation policy that overrides the default

The spec's default `degrade` rule weakens **truth** on loss (`T`/`F` → `N[transport_loss]`, `B` → `B[boundary_mix]`) and drops support to `partial`; spec §10.2 allows a truth policy to override that. In this implementation the override hook is the M6B degradation-policy extension: a `DegradationPolicyNode(kind="custom", binding=...)` whose binding is looked up in `services["__degradation_handlers__"]` and called as `handler(bridge, step_ctx, machine_state, services, policy)`.

The handler below deliberately **replaces** the spec default: it keeps the source truth and instead scales confidence by the bridge's declared risk count. Note that `"confidence_scaling_v1"` appears only in provenance/metadata -- it is a policy-local label, not a spec §8.5 reason code, and the source eval's own reason is carried through unchanged.

<!-- doc-snippet: runnable -->
```python
from limnalis.api.context import MachineState, StepContext
from limnalis.api.models import BridgeNode, FrameNode, FramePatternNode, TransportNode
from limnalis.api.results import EvalNode, TransportResult
from limnalis.api.transport import (
    DegradationPolicyNode,
    execute_transport_with_degradation_policy,
)


def confidence_scaling_degradation(bridge, step_ctx, machine_state, services, policy):
    """CUSTOM degradation: keep truth, scale confidence by declared risks.

    Overrides the spec 10.2 default degradation rule.
    """
    src = services.get("__per_claim_aggregates__", {}).get("c1")
    scale = max(0.5, 1.0 - 0.1 * len(bridge.risk))
    dst = None
    if src is not None:
        dst = EvalNode(
            truth=src.truth,          # default rule would weaken this on loss
            reason=src.reason,        # carry the source reason; invent none
            support=src.support,
            confidence=None if src.confidence is None else src.confidence * scale,
            provenance=src.provenance + [bridge.id, "confidence_scaling_v1"],
        )
    return TransportResult(
        status="degraded",
        srcAggregate=src,
        dstAggregate=dst,
        metadata={"degradation_factor": scale, "risks": bridge.risk},
        provenance=[bridge.id, "confidence_scaling_v1"],
    )


bridge = BridgeNode(
    **{"from": FramePatternNode(facets={"system": "Theory"})},
    id="b_theory_to_policy",
    to=FramePatternNode(facets={"system": "Policy"}),
    via="test://bridge/theory_to_policy",
    preserve=["model_grounding"],
    lose=["sensor_fidelity"],
    risk=["aliasing", "temporal_smear"],
    transport=TransportNode(mode="degrade"),
)

policy = DegradationPolicyNode(id="dp_conf", kind="custom", binding="confidence_scaling_v1")

step_ctx = StepContext(
    effective_frame=FrameNode(
        system="Theory", namespace="ModelFit", scale="computational",
        task="analysis", regime="nominal",
    ),
)
services = {
    "__per_claim_aggregates__": {
        "c1": EvalNode(truth="T", support="supported", confidence=0.9),
    },
    "__degradation_handlers__": {
        "confidence_scaling_v1": confidence_scaling_degradation,
    },
}

result, machine_state, diagnostics = execute_transport_with_degradation_policy(
    bridge, step_ctx, MachineState(), services, degradation_policy=policy,
)
print(result.status)                    # degraded
print(result.degradation_policy_used)   # dp_conf
print(result.dstAggregate.truth)        # T -- kept, because the CUSTOM policy says so
print(result.dstAggregate.confidence)   # 0.72 -- scaled instead
```

With `kind="default"` (or no policy at all), the same call reduces to the normative `execute_transport` behavior and the spec's degradation table applies.

## Next steps

- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- the most common extension point
- [Writing an adequacy method](writing_an_adequacy_method.md) -- for adequacy scoring
- [Downstream usage examples](downstream_usage_examples.md) -- end-to-end usage cookbook
- [Plugin SDK overview](plugin_sdk_overview.md) -- registry model and full API surface
