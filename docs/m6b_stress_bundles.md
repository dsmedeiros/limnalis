# Milestone 6B Stress-Test Bundles

## Purpose

These bundles push Limnalis at its current semantic edges, exercising transport chains, multi-evaluator disagreement, evidence relations, and adequacy assessments in realistic domain scenarios.

## CWT Cross-Frame Transport Bundle

**File:** `examples/cwt_transport_bundle.lmn`

Models a cross-frame reasoning scenario where a physical measurement claim is transported through a theoretical model frame to a policy compliance frame.

### What it stresses:
- **3 frames** at different abstraction levels (Physics/Measurement, Theory/ModelFit, Policy/Compliance)
- **3 evaluators** with different kinds and bindings
- **2 chained bridges:** remap_recompute (physics→theory) and degrade (theory→policy)
- **Transport loss/gain/risk** across each bridge hop
- **4 evidence items** with varying completeness and internal conflict
- **2 evidence relations** (corroborates, depends_on)
- **Claims across local, systemic, and meta strata**

### Key semantic questions it probes:
- What happens to truth when a measurement claim is remapped to a theoretical frame?
- How does degradation compound across multiple hops?
- Can transport provenance trace back through the full chain?

## Governance Stack / Multi-Evaluator Bundle

**File:** `examples/governance_stack_bundle.lmn`

Models a compliance evaluation scenario where three independent evaluators disagree, requiring adjudicated resolution.

### What it stresses:
- **3 evaluators** with different roles: institution (auditor), human (self-assessment), model (automated)
- **Adjudicated resolution policy** with explicit members and binding
- **4 evidence items** spanning audit, testimony, and measurement kinds
- **3 evidence relations:** 1 conflicts + 2 corroborates (auditor vs self-assessment conflict)
- **2 anchors** with adequacy assessments (one adequate, one inadequate)
- **Joint adequacy** assessment across anchors (fails threshold)
- **Claims requiring anchor licensing** via `uses` keyword

### Key semantic questions it probes:
- How does the system handle evaluator disagreement (T vs F vs N)?
- Can adjudicated resolution produce a coherent aggregate?
- Do summary policies produce different non-normative views of the same evaluator outputs?
- How do adequacy failures propagate to claim licensing?

## Corpus Integration

Corpus entries are in `fixtures/m6b_corpus_cases.yaml` with cases `M6B-T1` (transport) and `M6B-G1` (governance). These are versioned as `v0.2.2-m6b` and marked additive — they do not modify existing corpus cases.
