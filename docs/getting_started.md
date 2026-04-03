# Getting Started with Limnalis

## Installation

```bash
pip install limnalis          # from PyPI
pip install -e ".[dev]"       # development mode with test deps
```

Requires Python 3.11+.

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

Add `--json` to any command for machine-readable output. Stubbed primitives (phases without a registered plugin) are recorded as diagnostics rather than errors.

## Next Steps

- [How Evaluation Works](how_evaluation_works.md) -- the 13-phase pipeline
- [Multi-Evaluator Cookbook](cookbook/multi_evaluator.md) -- bundles with competing evaluators
- [Writing a Custom Plugin](cookbook/custom_plugin.md) -- extend Limnalis
- [Plugin SDK Overview](plugin_sdk_overview.md) -- full extension reference
