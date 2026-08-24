# Cookbook: Transport Chains

## What Transport Does

Transport moves claims across frames via **bridges**. When a claim evaluated in one frame needs to inform a decision in another, a bridge defines how truth and evidence transfer. See `examples/cwt_transport_bundle.lmn` for a working example.

## Transport Modes

| Mode | Effect (spec §10.2) |
|------|--------|
| `metadata_only` | Header metadata only; no truth or support transferred |
| `preserve` | Truth and support copied only if preconditions hold and no property in the claim's `semantic_requirements` appears in the bridge's `lose` list; otherwise `N[transport_loss]` / `N[transport_precondition]` |
| `degrade` | Attempts preservation; on loss of required detail, truth weakens (`T`/`F` → `N[transport_loss]`, `B` → `B[boundary_mix]`, `N` → `N`) and support drops to `partial` |
| `remap_recompute` | Claims remapped via `claim_map` and recomputed in destination frame |

## Walking Through the CWT Example

The bundle models a two-hop chain: Physics to Theory to Policy.

The `preserve`/`lose`/`gain` lists hold **properties** -- semantic capabilities of the frame, not evidence ids (spec §10.1 types them as `[Property]`). Their teeth come from the intersection with each claim's `semantic_requirements`: under `preserve` and `degrade` modes, a claim whose required property appears in the bridge's `lose` list cannot cross with its truth intact.

**Hop 1: Physics to Theory** (`remap_recompute`) -- measurement predicates are remapped to model-fit predicates. Sensor fidelity and calibration traceability survive; model grounding is gained.

```
bridge b_phys_to_theory {
  from @{system=Physics, namespace=Measurement, ...};
  to @{system=Theory, namespace=ModelFit, ...};
  preserve [sensor_fidelity, calibration_traceability];
  gain [model_grounding];
  transport { mode remap_recompute; claim_map test://map/phys_claims_to_theory; }
}
```

**Hop 2: Theory to Policy** (`degrade`) -- theory-level detail is intentionally lost when entering the policy frame.

```
bridge b_theory_to_policy {
  from @{system=Theory, ...};  to @{system=Policy, ...};
  preserve [model_grounding];  lose [sensor_fidelity, calibration_traceability];
  gain [policy_traceability];
  transport { mode degrade; }
}
```

A claim that declares what it needs, e.g.

```
c_temp: temperature_within_range(sensor_1, 20, 25) refs [e_sensor] semantic_requirements [sensor_fidelity];
```

hits `semantic_requirements ∩ lose = {sensor_fidelity}` at hop 2, so its truth degrades per the table above (`T → N[transport_loss]`) instead of silently crossing. Each bridge also declares a `risk` list for provenance auditing.

> **Note:** `examples/cwt_transport_bundle.lmn` currently populates `preserve`/`lose`/`gain` with evidence ids (`e_sensor`, `e_model_output`, ...) rather than properties. It still normalizes (any symbol is accepted), but the property-based declarations above are the spec-intended usage. Also note that a plain `limnalis evaluate` run executes bridges without transport queries, so their results report status `pattern_only`; loss-based degradation applies when a transport query targets a claim over the bridge (as the conformance harness's `transport_queries` environment entries do for case B1).

## Running Transport

```bash
limnalis evaluate examples/cwt_transport_bundle.lmn
```

Transport executes in Phase 13. For chain composition and degradation policies, see the [Transport Semantics Guide](../transport_semantics.md).
