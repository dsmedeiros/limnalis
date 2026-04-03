# Cookbook: Transport Chains

## What Transport Does

Transport moves claims across frames via **bridges**. When a claim evaluated in one frame needs to inform a decision in another, a bridge defines how truth and evidence transfer. See `examples/cwt_transport_bundle.lmn` for a working example.

## Transport Modes

| Mode | Effect |
|------|--------|
| `metadata_only` | Header metadata only; no truth or support transferred |
| `preserve` | Truth and support unchanged |
| `degrade` | Support reduced; truth unchanged |
| `remap_recompute` | Claims remapped via `claim_map` and recomputed in destination frame |

## Walking Through the CWT Example

The bundle models a two-hop chain: Physics to Theory to Policy.

**Hop 1: Physics to Theory** (`remap_recompute`) -- measurement predicates are remapped to model-fit predicates. Sensor evidence is preserved; model output evidence is gained.

```
bridge b_phys_to_theory {
  from @{system=Physics, namespace=Measurement, ...};
  to @{system=Theory, namespace=ModelFit, ...};
  preserve [e_sensor, e_calibration];
  gain [e_model_output];
  transport { mode remap_recompute; claim_map test://map/phys_claims_to_theory; }
}
```

**Hop 2: Theory to Policy** (`degrade`) -- theory-level detail is intentionally lost. Sensor evidence is dropped; policy documentation is gained.

```
bridge b_theory_to_policy {
  from @{system=Theory, ...};  to @{system=Policy, ...};
  preserve [e_model_output];  lose [e_sensor, e_calibration];
  gain [e_policy_doc];
  transport { mode degrade; }
}
```

Each bridge declares `preserve`, `lose`, `gain`, and `risk` lists for full provenance auditing.

## Running Transport

```bash
limnalis evaluate examples/cwt_transport_bundle.lmn
```

Transport executes in Phase 13. For chain composition and degradation policies, see the [Transport Semantics Guide](../transport_semantics.md).
