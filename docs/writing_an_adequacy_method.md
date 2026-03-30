# Writing an Adequacy Method

Adequacy methods score adequacy assessments attached to anchor nodes. These scores determine whether claims meet the required quality threshold, which feeds into the license composition phase (phase 5).

## What you'll need

- A `PluginRegistry` instance
- Understanding of `AdequacyAssessmentNode` structure
- Knowledge of the method URIs referenced in your bundle's anchor nodes

## How adequacy works in Limnalis

The evaluation pipeline processes adequacy in two phases:

1. **Phase 4 (evaluate_adequacy_set):** For each anchor in the bundle, the runner calls the registered adequacy method handler for each assessment. Your handler returns a score.
2. **Phase 5 (compose_license):** The license composer uses adequacy results to determine whether claims are licensed for evaluation. If an anchor's assessments fail to meet their thresholds, the claim's license may restrict or block evaluation.

Each `AdequacyAssessmentNode` in the bundle specifies a `method` field -- a URI that identifies which adequacy method to use. You register your handler under that URI.

## AdequacyAssessmentNode structure

```python
from limnalis.api.models import AdequacyAssessmentNode

# AdequacyAssessmentNode fields:
#   id: str               -- unique assessment identifier
#   task: str             -- the task being assessed (e.g., "n1_contingency")
#   producer: str         -- who produced the assessment
#   score: float | "N" | None  -- declared score (0.0 to 1.0), "N" for not-applicable, or None
#   threshold: float      -- minimum acceptable score (0.0 to 1.0)
#   method: str           -- URI identifying the adequacy method (your plugin ID)
#   basis: list[str]      -- references to basis data
#   confidence: float | None  -- confidence in the assessment (0.0 to 1.0)
#   failureModes: list[str]   -- known failure modes
```

## Handler signature

An adequacy method handler takes an assessment and returns a float score:

```python
def my_adequacy_handler(assessment) -> float:
    ...
```

| Parameter | Type | Description |
|---|---|---|
| `assessment` | `AdequacyAssessmentNode` | The assessment to score |
| **Returns** | `float` | Computed adequacy score in [0.0, 1.0] |

The runner compares the returned score against `assessment.threshold` to determine adequacy.

## Registering as ADEQUACY_METHOD

Register your handler using the method URI as the plugin ID:

```python
from limnalis.api.services import PluginRegistry, ADEQUACY_METHOD

registry = PluginRegistry()
registry.register(
    ADEQUACY_METHOD,
    "sim://checks/n1_pred",     # must match the method URI in the bundle
    my_adequacy_handler,
    description="N-1 prediction adequacy check",
)
```

Multiple assessments can reference the same method URI, so one handler may be called for several assessments with different parameters.

## Example: threshold-based adequacy check

A simple handler that uses the assessment's declared score:

```python
from limnalis.api.services import PluginRegistry, ADEQUACY_METHOD


def threshold_adequacy_handler(assessment) -> float:
    """Return the assessment's declared score, or 0.0 if unavailable.

    The runner compares this against assessment.threshold automatically.
    """
    if assessment.score is not None:
        # score may be the literal "N" for not-applicable
        if isinstance(assessment.score, str):
            return 0.0
        return float(assessment.score)
    return 0.0


registry = PluginRegistry()

# Register for each method URI your bundle references
for method_uri in [
    "sim://checks/n1_pred",
    "sim://checks/n1_ctrl",
    "audit://postmortem/n1_expl",
]:
    registry.register(
        ADEQUACY_METHOD,
        method_uri,
        threshold_adequacy_handler,
        description=f"Threshold adequacy check: {method_uri}",
    )
```

## Example: domain-specific adequacy with failure mode inspection

A more sophisticated handler that inspects failure modes and confidence:

```python
def strict_adequacy_handler(assessment) -> float:
    """Strict adequacy scoring that penalizes low confidence and failure modes."""
    if assessment.score is None or isinstance(assessment.score, str):
        return 0.0

    base_score = float(assessment.score)

    # Penalize if confidence is low
    if assessment.confidence is not None and assessment.confidence < 0.8:
        base_score *= assessment.confidence

    # Penalize for known failure modes
    penalty_per_mode = 0.1
    failure_penalty = len(assessment.failureModes) * penalty_per_mode
    base_score = max(0.0, base_score - failure_penalty)

    return base_score
```

## How adequacy results feed into licensing

After phase 4, the adequacy results are stored in `machine_state.adequacy_store`. In phase 5 (compose_license), the license composer uses these results:

- If all assessments for an anchor meet their thresholds, the anchor is adequate.
- If any assessment fails its threshold, the anchor is inadequate, which may result in a license truth of `"F"` for the associated claim.
- Joint adequacy groups combine multiple anchors; all anchors in the group must be adequate for the group to pass.

The license result appears in `ClaimResult.license` and influences downstream evaluation.

## Next steps

- [Writing an evaluator binding](writing_an_evaluator_binding.md) -- the most common extension point
- [Writing a transport handler](writing_a_transport_handler.md) -- for cross-frame transport
- [Plugin SDK overview](plugin_sdk_overview.md) -- registry model and full API surface
