# Compatibility and Deviations Policy

This document defines how spec/implementation mismatches are recorded, classified, and managed for the Limnalis reference implementation.

## Recording Deviations

When the implementation cannot match a spec expectation or fixture corpus expected output, a **deviation** must be filed. Each deviation record contains:

- **Case ID**: The fixture case ID (e.g., A4, B1) or a synthetic ID for non-corpus deviations
- **Reason**: A clear explanation of why the deviation exists (implementation limitation, spec ambiguity, intentional design choice)
- **Severity**: `blocking` or `non-blocking` (see classification below)
- **Status**: `open`, `resolved`, or `accepted`

Deviations are tracked in the conformance allowlist file (JSON or YAML), which maps case IDs to reason strings.

## Blocking vs Non-Blocking Deviations

**Blocking deviations** prevent a release candidate from shipping:
- A fixture corpus case produces incorrect results (wrong truth values, missing sessions, wrong diagnostics)
- A public API function raises an unexpected error on valid input
- Schema validation rejects a payload that the spec considers valid

**Non-blocking deviations** are acceptable for RC release with documentation:
- Performance characteristics differ from expectations (no performance SLA in v0.2.2)
- Diagnostic messages differ in wording but not in severity/code/subject
- Authored surface forms that are not exercised by the fixture corpus
- Features explicitly deferred to future milestones

## Allowlist Mechanism

The CLI conformance commands support a `--allowlist` flag:

```bash
limnalis conformance run --allowlist deviations.yaml
```

The allowlist file maps case IDs to reason strings:

```yaml
# deviations.yaml
A99: "Transport theorem proving deferred to v0.3.0"
```

Cases in the allowlist that fail are reported as `ALLOWED_FAIL` instead of `FAIL`. In default mode, allowed failures do not cause a non-zero exit code. In `--strict` mode, even allowed failures cause exit code 1.

## Version Bump Policy

When AST or result shapes change:

- **Patch version (0.2.x)**: Bug fixes only. No changes to AST node shapes, serialization format, or public API signatures. Diagnostic codes and messages may be refined.
- **Minor version (0.x.0)**: May add new AST node types, new fields (with defaults), new CLI commands, or new public API functions. Existing fields and commands are not removed; they may be deprecated.
- **Major version (x.0.0)**: May remove deprecated fields, commands, or API functions. May change AST shapes in breaking ways.

Schema version tracks the spec version (e.g., v0.2.2), not the package version. A schema version bump always requires at least a minor package version bump.

## Deprecation Policy

### CLI Commands and Flags

Deprecated CLI commands or flags will:
1. Continue to work for at least one minor version after deprecation is announced
2. Emit a deprecation warning to stderr when used
3. Be documented as deprecated in the `--help` output
4. Be removed no earlier than the next major version

### Public API (`limnalis.api.*`)

Deprecated public API functions or classes will:
1. Continue to work for at least one minor version after deprecation
2. Emit a `DeprecationWarning` when called
3. Be documented as deprecated in the module docstring
4. Be removed no earlier than the next major version

### Internal APIs

Internal module paths (`limnalis.normalizer`, `limnalis.runtime.runner`, etc.) are not subject to deprecation policy. They may change without notice between any releases. Consumers should use `limnalis.api.*` exclusively.
