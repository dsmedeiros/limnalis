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

## Known Limitations of the Conformance Harness

### Extra-diagnostic handling (updated 2026-08-24; largely remediated in M7)

**Severity:** non-blocking
**Status:** partially resolved
**Milestone:** M7 (comparator bidirectionality)

The original limitation recorded here — "the comparator does not flag unexpected additional diagnostics when at least one expected diagnostic matches" — no longer describes the comparator. Since M7 (`src/limnalis/conformance/compare.py`; behavioral contract in `src/limnalis/conformance/agents.md`):

- Whenever a case pins a `diagnostics` expectation, unmatched **error/fatal** actual diagnostics are reported as mismatches (the case fails), regardless of how many expected entries matched.
- Step-level reverse checks flag extra actual claims, blocks, and transports under a pinned map, with exactly two documented exemptions (non-evaluable note claims, e.g. vendored B1 `c5`; per-bridge transport scaffolding entries keyed by declared bridge ids, e.g. vendored A7).
- Under-specified pins that deserve author attention (a B/N truth pinned without a reason while the actual carries one) surface through `CaseComparison.warnings` without affecting `passed`.

Remaining known limits (accepted):

- Extra **warning/info** diagnostics are still tolerated by design — expectations are partial matchers (spec §18.2).
- Two diagnostic codes (`frame_pattern_completed`, `logical_composition`) are *injected* into actual results by the fixture-echo runner because no phase can produce them under fixture evaluation (`src/limnalis/conformance/runner.py:_build_injected_diagnostics`); for those two codes the comparison is self-fulfilling.

## Deviation Ledger

Deviations filed per the recording format above. Synthetic IDs are used for non-corpus deviations. Line references are to the tree as of 2026-08-24.

### DEV-ADEQ-CONTESTED — `aggregate_contested_adequacy` implements superseded aggregation semantics

- **Case ID:** DEV-ADEQ-CONTESTED (non-corpus; API helper `limnalis.api.adequacy.aggregate_contested_adequacy`)
- **Reason:** The standalone M6B helper implements ADR-008's original aggregation table, which the ADR's 2026-08-24 amendment records as diverging from spec §8.3/§9.3: its `paraconsistent_union` is "all must agree; disagreement → `adequate=False`, `failure_kind='method_conflict'`" (its `AdequacyExecutionTrace` result has no `truth` field, so it structurally cannot express a propagated B), and its `priority_order` is "first adequate wins" (an early decisive F is skipped — an exact inversion of the spec's first-non-N walk; it also accepts no `policy.order` input). Additionally, its `B[method_conflict]` **trigger mechanism** differs from the normative path: `execute_adequacy_with_basis` fires on computed-vs-declared score divergence beyond tolerance (the literal §9.2 rule), while the normative Phase-4 path (`evaluate_adequacy_set`, `builtins.py:1162-1196`) fires when same-task assessments use different method URIs (what corpus A12 exercises). The normative Phase-4 aggregation (`_aggregate_adequacy_by_policy`) follows the spec; only this helper diverges. Execution-confirmed in the checkpoint-2 review (`.armature/reviews/m8-ckpt2-contradictions.md`); see also the amendment appended to `docs/adr/008-contested-adequacy-aggregation.md` and the warning in `docs/adequacy_execution_guide.md`.
- **Severity:** non-blocking (no corpus case is served by the helper; the normative path is conformant)
- **Status:** open — remediation queued (no `src/` changes permitted in M8)

### DEV-REASON-VOCAB — `no_adequacy_result` is not a spec §8.5 reason code

- **Case ID:** DEV-REASON-VOCAB (non-corpus; license composition)
- **Reason:** Spec §9.2/§16.6.4 use `N[not_yet_applicable]` for adequacy that cannot yet be determined. The score-`N` path is conformant since M7: an assessment with `score: N` now yields `N[not_yet_applicable]` (`builtins.py:981-998`, m7 red-team MEDIUM-1). The no-record path is still divergent: when license composition finds no adequacy result at all for an `anchor:task` pair, it emits `truth="N", reason="no_adequacy_result"` (`builtins.py:1535`) — a reason string that appears in no spec §8.5 taxonomy list.
- **Severity:** non-blocking (reason-string wording; severity/truth are correct)
- **Status:** open — partially remediated (score-N path fixed in M7; no-record path pending)

### DEV-UNBOUND-REF — unbound reference surface syntax rejected

- **Case ID:** DEV-UNBOUND-REF (non-corpus; surface syntax)
- **Reason:** The reconstruction's EBNF defines `UnboundRef ::= "|∞:" Ident "|" | "|inf:" Ident "|"` (A.9 lines 1279-1280), and spec §13.2 lists the `|∞:kind|` reference form. The normalizer's scanners shield these spans as single terms, but term parsing then rejects them: `|inf:...|`/`|∞:...|` raise `NormalizationError: invalid baseline reference` (`normalizer.py:1575`); only the baseline form `|0:...|` is accepted.
- **Severity:** non-blocking (authored surface form not exercised by the fixture corpus)
- **Status:** open

### DEV-ASSUMPTION-SURFACE — assumption declarations have no surface grammar

- **Case ID:** DEV-ASSUMPTION-SURFACE (non-corpus; surface syntax)
- **Reason:** `AssumptionNode` exists in the AST models (`models/ast.py:362`) and the vendored AST schema (`$defs.AssumptionNode`), and `BundleNode.assumptions` is populated on import of AST JSON — but no `assumption` production exists in `grammar/limnalis.lark` and the normalizer builds no assumptions from surface text. Assumptions are reachable only via pre-built AST payloads, never from `.lmn` sources.
- **Severity:** non-blocking (authored surface form not exercised by the fixture corpus)
- **Status:** open

### DEV-INTERVENTION-CLAUSE — intervention clause syntax mutually incompatible with the EBNF

- **Case ID:** DEV-INTERVENTION-CLAUSE (non-corpus; surface syntax)
- **Reason:** The reconstruction's EBNF defines a trailing clause: `CausalExpr ::= SimpleExpr CausalOp SimpleExpr [InterventionClause]`, `InterventionClause ::= "intervention" (Ref | "(" Expr ")")`, with `CausalOp` allowing only bare `=>[obs]`/`=>[do]` (`Limnalis-v0.2.2-reconstructed.md:1249-1251`). The implementation instead encodes the intervention inside the operator bracket: `=>[do:<intervention>]` (`normalizer.py` `_CAUSAL_RE`). The two forms are bidirectionally incompatible: the implementation's `=>[do:X]` is underivable from the EBNF, and the EBNF's trailing form does not error but **misparses** — `a =>[do] b intervention c` normalizes with the entire trailing text absorbed into the rhs predicate name (execution-confirmed: rhs name becomes `"stable(grid) intervention shed_load"`). The misparse makes this the sharpest surface-syntax hazard in this ledger.
- **Severity:** non-blocking for corpus conformance (corpus uses the bracket form), but note the silent-misparse hazard for EBNF-derived sources
- **Status:** open

### DEV-EMRG-HYSTERESIS — emergence hysteresis/witness unimplemented

- **Case ID:** DEV-EMRG-HYSTERESIS (non-corpus; surface syntax + runtime)
- **Reason:** Spec `EmergenceExpr` carries `hysteresis?: Condition` and `witness: [ClaimId]` (`Limnalis-v0.2.2.md:1056-1057`), and the reconstruction's EBNF defines surface clauses `["hysteresis" Expr] ["witness" RefList]` (`:1253-1254`). The AST model and schema carry both fields (`models/ast.py:280-281`), so imported AST JSON can express them — but the EMRG surface parser (`normalizer.py:1080-1122`) never produces them, and the runtime has no hysteresis/witness semantics: `hysteresis` is only walked for baseline-reference collection (`builtins.py:734`), and emergence evaluation is a delegated leaf handed to evaluator bindings.
- **Severity:** non-blocking (feature deferred; not exercised by the fixture corpus)
- **Status:** open

### DEV-TRUTHPOLICY-DEAD — `TransportNode.truthPolicy` parsed but never read

- **Case ID:** DEV-TRUTHPOLICY-DEAD (non-corpus; runtime)
- **Reason:** Spec §10.1 defines `transport.truth_policy: BindingRef?` as the override hook for default degradation ("support becomes partial unless truth_policy overrides it", §10.2). The field exists on the AST (`models/ast.py:501`), is parsed from surface text (`normalizer.py:713,724`), and validates against the schema — but nothing under `src/limnalis/runtime/` ever reads it (execution-confirmed by the checkpoint-2 review, `.armature/reviews/m8-ckpt2-contradictions.md`). The working override mechanism is the M6B degradation-policy extension (`DegradationPolicyNode(kind="custom")` with `services["__degradation_handlers__"]`), documented in `docs/writing_a_transport_handler.md`.
- **Severity:** non-blocking (declared field is inert; no corpus case pins truth-policy behavior)
- **Status:** open
