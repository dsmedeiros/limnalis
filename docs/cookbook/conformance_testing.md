# Cookbook: Conformance Testing

## What Conformance Means

The fixture corpus is the conformance authority (invariant FIXTURE-001). Each case defines a bundle with expected outputs. Conformance testing verifies the implementation matches.

## CLI Commands

```bash
limnalis conformance run --all          # run all cases
limnalis conformance run --cases A1     # run one case
limnalis conformance show A1            # view a case definition
limnalis conformance report             # generate comparison report (JSON)
limnalis conformance report --format markdown  # markdown report
```

## Programmatic API

See `examples/consumer_fixture_conformance.py` for a complete example:

```python
from limnalis.api.conformance import compare_case, load_corpus_from_default, run_case

corpus = load_corpus_from_default()
case = corpus.get_case("A1")
run_result = run_case(case, corpus)
comparison = compare_case(case, run_result)

print(comparison.summary())
for m in comparison.mismatches:
    print(f"  {m}")
```

## What Comparison Checks

- **Session structure** -- correct number of sessions and steps
- **Claim results** -- truth values and evaluator outputs
- **Diagnostics** -- expected severity, code, and subject
- **Baseline states** and **adequacy expectations**

## Writing a Conformance Case

Cases are defined in `fixtures/limnalis_fixture_corpus_v0.2.2.yaml`. Each specifies a bundle ID, optional `.lmn` source, expected sessions, claim results, and diagnostics. Schema: `schemas/limnalis_fixture_corpus_schema_v0.2.2.json`.

## Plugins and Conformance

Some cases (B1, B2) need domain plugins. Register before running:

```python
from limnalis.api.services import PluginRegistry, build_services_from_registry
from limnalis.plugins.grid_example import register_grid_plugins

registry = PluginRegistry()
register_grid_plugins(registry)
services = build_services_from_registry(registry)
```

See `examples/consumer_grid_b1.py` for a full example.
