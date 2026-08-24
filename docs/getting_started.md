# Getting Started with Limnalis

## Installation

Limnalis is not yet published to PyPI. Install it from a clone of this repository:

```bash
pip install -e .              # editable install from the repo root
pip install -e ".[dev]"       # development mode with test deps
```

Or run it without installing, from the repository root:

```bash
PYTHONPATH=src python -m limnalis parse examples/minimal_bundle.lmn
```

Requires Python 3.11+. Runtime dependencies (installed automatically by pip): `pydantic` 2.x, `lark`, `jsonschema`, `PyYAML`.

## Your First Bundle

A Limnalis **bundle** is a `.lmn` file declaring claims to be evaluated. See `examples/minimal_bundle.lmn`:

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

- **`bundle`** names the evaluation unit.
- **`frame`** sets the evaluation context (system, namespace, scale).
- **`evaluator`** declares who evaluates claims and how.
- **`local { ... }`** contains claims scoped to this frame.

## CLI Walkthrough

**Parse** -- produce the raw syntax tree:
```bash
limnalis parse examples/minimal_bundle.lmn
```

**Normalize** -- produce the canonical Pydantic AST as JSON:
```bash
limnalis normalize examples/minimal_bundle.lmn
```

**Validate** -- check the AST against the vendored JSON Schema:
```bash
limnalis validate-source examples/minimal_bundle.lmn
```

**Evaluate** -- run the full 13-phase pipeline:
```bash
limnalis evaluate examples/minimal_bundle.lmn
```

**Lint / analyze** -- collect diagnostics (add structural analysis with `analyze`); both support `--format plain|json|grouped|sarif`, e.g. SARIF for CI code-scanning upload (see [SARIF Export](sarif_export.md)):
```bash
limnalis lint examples/minimal_bundle.lmn
limnalis analyze examples/minimal_bundle.lmn --format sarif
```

Add `--json` to any command for machine-readable output. Stubbed primitives (phases without a registered plugin) are recorded as diagnostics rather than errors.

## Next Steps

- [How Evaluation Works](how_evaluation_works.md) -- the 13-phase pipeline
- [Multi-Evaluator Cookbook](cookbook/multi_evaluator.md) -- bundles with competing evaluators
- [Writing a Custom Plugin](cookbook/custom_plugin.md) -- extend Limnalis
- [Plugin SDK Overview](plugin_sdk_overview.md) -- full extension reference
