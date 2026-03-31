# Armature Session State

## Current Objective
Milestone 6A: Interoperability, exchange formats, and LinkML/export pipeline for Limnalis v0.2.2

## Build Candidate
{pending — ready for tagging}

## Task Status
| Task | Description | Status | Depends |
|------|-------------|--------|---------|
| T1 | Interop module + envelope models + public API types | completed | aa89b24 |
| T2 | Export/import functions + envelope serialization | completed | 9c249bd |
| T3 | Exchange package format | completed | f0f294b |
| T4 | LinkML projection pipeline | completed | 02dfb17 |
| T5 | CLI export/package/project commands + versioning | completed | b85e872 |
| T6 | Envelope + round-trip + package + determinism tests | completed | 0660432 |
| T7 | CLI + LinkML projection tests | completed | 94d4b22 |
| T8 | Downstream consumer examples | completed | c5fbbf2 |
| T9 | Interoperability documentation | completed | d9e778f |
| T10 | Optional JSON-LD/RDF note | completed | d9e778f |

## Active Delegation
{none — red team cycle complete, all findings resolved}

## Pending Reviews
{none — all tasks reviewed PASS}

## Invariants Touched
MODEL-001, MODEL-002, SCHEMA-001, NORM-001

---
<!-- APPEND-ONLY BELOW THIS LINE -->

## Decisions Log
- Extension SDK uses pure re-export modules (no new logic in api/ layer)
- Plugin registry keyed by (kind, plugin_id) tuples for deterministic lookup
- Plugin packs are example-level implementations, not production-ready
- fixtures.py uses internal imports (acceptable as package-internal module)
- CLI plugins commands use demo registry with auto-discovery of installed packs

## Discovered Context
- Consumer examples can use conformance runner for B1/B2 (fixture-backed bindings), demonstrating the plugin registration pattern alongside conformance
- RegistryEvaluatorBindings uses "evaluator_id::expr_type" composite keys
- build_services_from_registry bridges registry to runner's services dict format
