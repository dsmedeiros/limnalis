# ADR-004: Public API Freeze for Release Candidate

## Status

Accepted

## Context

As the Limnalis reference implementation approaches v0.2.2 release candidate status, downstream consumers need a stable import surface they can rely on across patch releases. At the same time, internal module structure must remain free to change for maintenance and optimization.

## Decision

The public API is frozen at RC time under `limnalis.api.*`. Four submodules constitute the stable surface:

| Module | Stable Exports |
|--------|----------------|
| `limnalis.api.parser` | `LimnalisParser` |
| `limnalis.api.normalizer` | `Normalizer`, `NormalizationResult`, `NormalizationError`, `normalize_surface_file`, `normalize_surface_text` |
| `limnalis.api.evaluator` | `run_bundle`, `run_session`, `run_step`, `PrimitiveSet`, `BundleResult`, `SessionResult`, `StepResult`, `EvaluationResult` |
| `limnalis.api.conformance` | `load_corpus`, `load_corpus_from_default`, `run_case`, `compare_case`, `FixtureCase` |

All imports from `limnalis.api.*` are supported across patch releases within the same minor version (0.2.x). Internal module paths (e.g., `limnalis.normalizer`, `limnalis.runtime.runner`) are implementation details and may change without notice.

The CLI command set and its flags are also frozen for the RC. New commands may be added in future minor versions, but existing commands will not have their behavior or flags changed within 0.2.x.

## Consequences

**Positive:**
- Downstream consumers have a clear, documented stable surface
- Internal refactoring (module splits, renames, reorganization) does not break consumers
- The `limnalis.api` package serves as a natural boundary for API review

**Negative:**
- API additions within the RC cycle require careful consideration since they become part of the stable surface
- Bugs in the public API signatures may require deprecation rather than direct removal

**Neutral:**
- The freeze applies to the Python API and CLI; schema and corpus versions are governed by the spec version, not the package release
