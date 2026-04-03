# Limnalis

Limnalis is a structured evaluation language for making **claims** about a system and then formally **evaluating** whether those claims hold. You write bundles (`.lmn` files) that declare claims — things you believe to be true about a system — along with the evaluators and evidence needed to assess them. Limnalis then runs a deterministic evaluation pipeline that produces machine-readable verdicts using four-valued logic (true, false, both, neither).

**Use Limnalis when you need to:**

- **Formally evaluate claims** — go beyond pass/fail testing by expressing nuanced truth values, including contradictory or insufficient evidence
- **Compose multiple evaluators** — have independent evaluators assess the same claims, then aggregate results via resolution policies (unanimous, majority, adjudicated)
- **Structure evaluation evidence** — attach evidence to claims, track completeness and internal conflicts, and reason about adequacy before evaluation
- **Transport truth across boundaries** — use bridges to carry evaluated results between evaluation frames (e.g., from a subsystem assessment into a governance review)

### A minimal example

```
bundle minimal_bundle {
  frame @Test:Minimal::nominal;

  evaluator ev0 {
    kind model;
    binding test://eval/atoms_v1;
  }

  local {
    c1: p;
  }
}
```

This bundle declares a single claim `c1: p` evaluated by `ev0` within the `@Test:Minimal::nominal` frame. Running `limnalis evaluate` on it produces a full result hierarchy — from bundle-level summaries down to per-claim truth values.

For a deeper introduction, see the [Getting Started guide](docs/getting_started.md). For how the 13-phase evaluation pipeline works, see [How Evaluation Works](docs/how_evaluation_works.md). For the full architecture, see [Architecture Overview](docs/architecture.md). The upstream language specification and conformance matrix are in [`spec/`](spec/).

## Language Concepts

### Four architectural layers

Limnalis organizes language constructs into four layers. These are orthogonal to claim strata — a meta claim can belong to any layer depending on what it talks about.

| Layer | What it covers | Expressed through |
|-------|---------------|-------------------|
| **World** | Claims about systems, entities, mechanisms, thresholds, emergent behavior | `local` and `systemic` claim blocks |
| **Knowledge** | Who evaluates, from what evidence, with what support and provenance | Evaluators, Evidence, EvidenceRelations, Eval results, frame facets |
| **Fiction** | Assumptions, idealizations, placeholders, proxies, and adequacy judgments | Anchors, Assumptions, JointAdequacy, license checks |
| **Notation** | Surface syntax, operator symbols, and bindings to external artifacts | Bindings (equations, datasets, code, policies) |

### The seven-part separation

Every Limnalis statement separates seven concerns that are commonly conflated elsewhere: the **claim** itself, the **frame** (evaluation context), the **assumptions** in play, the **model-status** of terms (literal, idealized, proxy, etc.), the **evaluator** assigning truth, the **evidence** available, and the **evaluation** result (T/F/B/N plus reason).

### Four-valued logic (Belnap-Dunn)

Limnalis uses four truth values instead of two, based on Belnap-Dunn semantics:

| Value | Meaning | When it arises |
|-------|---------|----------------|
| **T** | True | The claim holds under the active evaluator and evidence |
| **F** | False | The claim does not hold |
| **B** | Both (true and false) | Contradictory evidence — e.g., two sensors disagree |
| **N** | Neither | Insufficient evidence, missing bindings, or out-of-scope |

B and N are not error states — they are first-class evaluation outcomes. Both always carry a reason code (e.g., `source_conflict`, `undefined_term`, `missing_binding`). The logic defines conjunction, disjunction, negation, implication, and biconditional over these four values, with notable results like B AND N = F (falsity support remains when truth support vanishes).

### Bundles, frames, and claims

A **bundle** is the top-level evaluation unit. It declares:

- A **frame** — the epistemic context (system, namespace, scale, task, regime, and optional observer). Claims are evaluated relative to their frame; truth does not transfer across frames without an explicit bridge.
- One or more **evaluators** — the agents (models, humans, institutions, ensembles) that assess claims. Each evaluator has a kind, role, and binding to an external method.
- A **resolution policy** — how to aggregate when multiple evaluators assess the same claim (`single`, `paraconsistent_union`, `priority_order`, or `adjudicated`).
- **Claim blocks** organized by stratum:
  - `local` — entities, components, near-mechanistic relations
  - `systemic` — aggregates, distributions, attractors, emergence
  - `meta` — claims about claims, frames, evaluators, or anchors

Claims can use a range of expression forms: predicates, logical operators (AND/OR/NOT/IMPLIES/IFF), causal relations (observational or interventional), dynamic transitions, emergence patterns, declarations, and criterion-bound judgments (`judged_by`).

### Evidence and conflict

Evidence is typed (measurement, dataset, testimony, simulation, audit, derived) and carries completeness and internal-conflict scores. Evidence relations track cross-evidence relationships (corroborates, conflicts, depends_on, duplicate_of). When evaluating a claim, the engine builds per-claim evidence views and surfaces conflicts through support status (`supported`, `partial`, `conflicted`, `absent`, `inapplicable`).

### Anchors, adequacy, and fiction licensing

An **anchor** marks a term as an idealization, placeholder, proxy, or aggregate — acknowledging that it is not literally true. Before evaluating claims that depend on anchors, the engine checks **adequacy**: is the fiction good enough for the task at hand? Adequacy assessments have producers, methods, scores, thresholds, and basis chains. Multiple assessments can be aggregated under a policy. Joint adequacy checks verify that combinations of anchors work together. Failed adequacy does not force the world claim false — it marks the modeling fiction as *unlicensed* under the active task.

### Bridges and truth transport

A **bridge** defines how evaluated truth can move between frames. Four transport modes control what happens at the boundary:

| Mode | Behavior |
|------|----------|
| `metadata_only` | No truth transfer; only provenance and metadata cross |
| `preserve` | Copy source truth if preconditions hold and no required properties are lost |
| `degrade` | Attempt preservation but weaken truth when lost detail matters |
| `remap_recompute` | Map the claim to the destination frame and re-evaluate from scratch |

### The 13-phase evaluation pipeline

Each evaluation step runs a fixed 13-phase pipeline: build context, resolve references, resolve baselines, evaluate adequacy, compose licenses, build evidence views, classify claims, evaluate expressions, synthesize support, assemble per-evaluator results, apply resolution policy, fold blocks, and execute transport. Each phase is backed by a replaceable primitive — the plugin system lets you swap in domain-specific logic at any phase. See [How Evaluation Works](docs/how_evaluation_works.md) for the full pipeline diagram.

For the complete language specification, see [`spec/`](spec/).

---

**Package version:** 0.2.2rc1 | **Spec version:** v0.2.2

## Quickstart

### Installation

```bash
# Standard install
pip install .

# Development install with test dependencies
pip install -e ".[dev,test]"
```

### Quick usage

Parse surface syntax into a raw parse tree:

```bash
limnalis parse examples/minimal_bundle.lmn
```

Normalize into canonical AST JSON:

```bash
limnalis normalize examples/minimal_bundle.lmn
```

Run the full evaluation pipeline:

```bash
limnalis evaluate examples/minimal_bundle.lmn
```

Run conformance against the fixture corpus:

```bash
limnalis conformance run --all
```

### Public API

```python
from limnalis.api.normalizer import normalize_surface_file
from limnalis.api.evaluator import (
    EvaluationEnvironment,
    SessionConfig,
    StepConfig,
    run_bundle,
)

result = normalize_surface_file("examples/minimal_bundle.lmn")
bundle = result.canonical_ast
sessions = [SessionConfig(id="default", steps=[StepConfig(id="step0")])]
env = EvaluationEnvironment()
evaluation = run_bundle(bundle, sessions, env)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `parse` | Parse a `.lmn` file and print the raw parse tree |
| `normalize` | Normalize a `.lmn` file into canonical AST JSON |
| `validate-source` | Parse, normalize, and schema-validate a `.lmn` file |
| `validate-ast` | Validate a canonical AST JSON/YAML payload against the schema |
| `validate-fixtures` | Validate a fixture corpus JSON/YAML file |
| `evaluate` | Run the full evaluation pipeline and output JSON result |
| `print-schema` | Print a vendored JSON Schema (`ast`, `fixture_corpus`, `conformance_result`) |
| `conformance list` | List all available fixture cases |
| `conformance show` | Show details for a fixture case |
| `conformance run` | Run conformance cases and report pass/fail |
| `conformance report` | Generate a conformance report (JSON or Markdown) |
| `version` | Print version info as JSON |

Global flags: `--version`, `--json` (on applicable commands), `--strict`, `--allowlist` (on conformance commands).

## Design Principles

The AST layer is **Pydantic-first**: all AST nodes inherit from `LimnalisModel` (a strict `BaseModel` with `extra='forbid'`), providing runtime validation, stable JSON serialization via `model_dump`, and model-emitted JSON Schema via `model_json_schema`.

## Repo Layout

```text
limnalis/
  spec/                             # Upstream language spec and conformance matrix
  grammar/limnalis.lark             # Lark grammar for surface syntax
  src/limnalis/
    api/                            # Stable public API surface
    models/                         # Pydantic AST models
    runtime/                        # 13-phase step runner and builtins
    conformance/                    # Fixture-based conformance harness
    parser.py, normalizer.py, loader.py, schema.py, cli.py, diagnostics.py
  schemas/                          # Vendored JSON Schemas (v0.2.2)
  fixtures/                         # Vendored fixture corpus (v0.2.2)
  tests/                            # Unit, integration, property, and conformance tests
  docs/                             # Architecture, ADRs, and status documents
```

## Running Tests

```bash
python -m pytest tests/ -q
```

## Known Vendored-Schema Issue

The shipped `limnalis_ast_schema_v0.2.2.json` contains a `$ref` typo where some `time` fields point to `#/$defs/FixtureTimeSpec` instead of `TimeCtxNode`. The runtime loader in `limnalis.schema` includes an opt-in repair pass so schema validation works in practice.
