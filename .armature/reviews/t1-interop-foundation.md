# Review: T1 — Interop Module Foundation

## Verdict: PASS

## Checklist
- [x] MODEL-001: All 7 models (SourceInfo, ASTEnvelope, ResultEnvelope, ConformanceEnvelope, ExchangeManifest, ExchangePackageMetadata, ProjectionResult) inherit from LimnalisModel, which inherits from pydantic.BaseModel. Compliant.
- [x] MODEL-002: LimnalisModel sets `model_config = ConfigDict(extra="forbid")` in `models/base.py`. All interop models inherit this config without overriding it. Compliant.
- [x] SCHEMA-001: Version constants SPEC_VERSION="0.2.2" and SCHEMA_VERSION="0.2.2" match the vendored schema filename `limnalis_ast_schema_v0.2.2.json`. Compliant.
- [x] Scope compliance: All 4 new files are within `src/limnalis/interop/`. No files outside declared scope were created or modified. The only other change on the branch is `.armature/session/state.md` (session bookkeeping, not part of this changeset).
- [x] No cross-cutting changes: `models/`, `runtime/`, governance files, grammar, normalizer, parser, CLI — all untouched.
- [x] Code quality: Clean imports with no circular dependencies (interop imports only from `limnalis.models.base` and stdlib). Consistent use of `from __future__ import annotations`. Alphabetical `__all__` in `__init__.py`. Appropriate use of `Literal` for artifact_kind discriminators. `Field(default_factory=list)` and `Field(default_factory=dict)` used correctly for mutable defaults.
- [x] agents.md correctness: Frontmatter follows the standard format with scope, governs, inherits, adrs, invariants, enforced-by, persona, authority, restricted fields. Inherits from `src/limnalis/agents.md`. Lists correct invariants [SCHEMA-001, MODEL-001, MODEL-002].

## Notes
- No issues found. The changeset is minimal, correctly scoped, and invariant-compliant.
- The `enforced-by` field in `agents.md` is empty (`[]`), which is acceptable for a new module that does not yet have dedicated tests. Tests should be added in a subsequent task.
- Envelope payload fields (`normalized_ast`, `evaluation_result`, `report`) are typed as `dict[str, Any]`, which is the correct approach — inner content validation is delegated to the schema module per the behavioral directives.
- `get_package_version()` gracefully handles the case where the package is not installed, returning `"unknown"`.
