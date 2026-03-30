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

| Mode | Description |
|---|---|
| `metadata_only` | Only metadata crosses the bridge; truth values are not transported |
| `preserve` | Truth values are preserved across the bridge |
| `degrade` | Truth values may be degraded (e.g., confidence reduced) during transport |
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
#   status: str                    -- "ok", "degraded", "failed", etc.
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
            status="failed",
            metadata={"error": f"handler only supports metadata_only, got {mode}"},
            provenance=[bridge_id],
            diagnostics=[{
                "severity": "error",
                "code": "unsupported_transport_mode",
                "message": f"Expected metadata_only, got {mode}",
            }],
        )

    return TransportResult(
        status="ok",
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

## Example: degraded transport with confidence reduction

```python
from limnalis.api.results import TransportResult, EvalNode


def degrading_transport(bridge, step_result, machine_state):
    """Transport that degrades confidence based on bridge risks."""
    bridge_id = bridge.id
    risks = bridge.risk

    # Calculate degradation factor based on number of risks
    degradation = max(0.5, 1.0 - 0.1 * len(risks))

    # Get source aggregate from step result if available
    src_aggregate = None
    if step_result and step_result.per_block_aggregates:
        first_block = next(iter(step_result.per_block_aggregates.values()), None)
        src_aggregate = first_block

    dst_aggregate = None
    if src_aggregate:
        dst_confidence = None
        if src_aggregate.confidence is not None:
            dst_confidence = src_aggregate.confidence * degradation
        dst_aggregate = EvalNode(
            truth=src_aggregate.truth,
            reason="degraded_transport",
            support=src_aggregate.support,
            confidence=dst_confidence,
            provenance=src_aggregate.provenance + [bridge_id],
        )

    return TransportResult(
        status="degraded",
        srcAggregate=src_aggregate,
        dstAggregate=dst_aggregate,
        metadata={
            "degradation_factor": degradation,
            "risks": risks,
        },
        provenance=[bridge_id, "degrading_transport"],
    )
```

## Next steps

- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- the most common extension point
- [Writing an adequacy method](writing_an_adequacy_method.md) -- for adequacy scoring
- [Downstream usage examples](downstream_usage_examples.md) -- end-to-end usage cookbook
- [Plugin SDK overview](plugin_sdk_overview.md) -- registry model and full API surface
