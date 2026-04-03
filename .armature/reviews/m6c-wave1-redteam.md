# Red Team Review: M6C Wave 1 (T1, T2, T3, T9)

## Summary

The Wave 1 changeset is a low-risk tooling wave: CLI restructuring (T3), a new diagnostic formatter (T1), a TextMate grammar (T2), and documentation (T9). The CLI restructuring is a clean decomposition with no behavioral changes -- all existing import paths (`from limnalis.cli import main`) continue to work, the entry point in `pyproject.toml` resolves correctly, and the `__main__.py` bridge is unaffected. The diagnostic formatter is well-tested and deterministic. Two MEDIUM-severity issues and several documentation inaccuracies were found. No critical or high-severity findings.

## Critical Findings

None.

## Subtle Issues

1. **`Diagnostic.from_dict()` does not handle `None` values in raw dicts** -- `src/limnalis/diagnostics.py` line 37-42. The method uses `raw.get("severity", "info")` which returns `None` (not the default `"info"`) when the key exists with an explicit `None` value. This causes a Pydantic `ValidationError` on construction. In practice, raw dicts from the runtime should not contain `None` for required fields, but the docstring promises "handles missing fields with sensible defaults" which creates an implicit contract that `None` values are also handled. Severity: MEDIUM.

   How to trigger: `Diagnostic.from_dict({"severity": None})` raises `ValidationError`.

2. **TextMate grammar keyword coverage is incomplete** -- `editor/vscode/syntaxes/limnalis.tmLanguage.json` line 70. The `keywords-control` pattern covers 19 keywords but omits several structural keywords that appear in `.lmn` example files: `adequacy`, `adequacy_policy`, `joint_adequacy` is covered but `adequacy` alone is not a standalone keyword match since it only matches as part of the regex `\bjoint_adequacy\b`. Additionally, property-level keywords (`kind`, `binding`, `role`, `subtype`, `status`, `score`, `threshold`, `method`, `basis`, `preserve`, `lose`, `gain`, `risk`, `mode`, `via`, `from`, `to`, `members`, `scale`, `namespace`, `system`, `regime`, `task`, `term`, `producer`, `id`, `completeness`, `refs`) receive no special highlighting -- they fall through to the `variable.other.limnalis` catch-all. This is a design choice (the Lark grammar is permissive and does not distinguish keywords from atoms), but the VS Code extension will not highlight these as keywords, reducing readability for authors. Severity: MEDIUM (cosmetic, does not affect functionality).

3. **`version` subparser registered in two places** -- The `version` subparser is registered in `_existing.py` `register_commands()` (line 32-35) and its handling is intercepted in `__init__.py` `main()` (line 64-65) before `dispatch()` is called. This split is intentional (the subparser must be registered for argparse to recognize it) but creates a maintenance risk: if someone adds version-related arguments to the subparser in `_existing.py`, they would not be processed in `__init__.py` without a corresponding change. Severity: LOW.

## Test Gaps

1. **No test for `Diagnostic.from_dict()` with `None` values** -- The test suite covers empty dicts and extra keys but does not test explicit `None` values for required fields like `severity`, which triggers a `ValidationError` rather than falling back to defaults.

2. **No test for `format_diagnostics` with an empty list** -- `format_diagnostics([])` is not tested. The code handles it correctly (returns empty string for plain/grouped, `[]` for json), but this boundary condition is not verified.

3. **No test for `_coerce` with invalid types** -- The `TypeError` path in `_coerce` (line 55 of `diagnostic_fmt.py`) is not exercised by any test.

4. **No integration test verifying `from limnalis.cli import build_parser`** -- While `from limnalis.cli import main` is exercised by many tests, `build_parser` is only called indirectly. No test verifies it is importable as a public API.

5. **TextMate grammar has no validation tests** -- The `tmLanguage.json` regex patterns are not tested against actual `.lmn` content. No automated check verifies that keywords match expected tokens or that nested patterns (strings, inline patterns) handle edge cases like escaped quotes.

## Semantic Drift Risks

1. **Documentation uses `--case` (singular) instead of `--cases` (plural)** -- `docs/cookbook/conformance_testing.md` line 11 uses `limnalis conformance run --case A1`. This works due to argparse prefix matching (`--case` resolves to `--cases`), but is technically incorrect and will break if another flag starting with `--case` is ever added.

2. **Documentation uses invalid `conformance report --all`** -- `docs/cookbook/conformance_testing.md` line 13 uses `limnalis conformance report --all`. The `report` subcommand does not accept `--all`. Argparse interprets `--all` as `--allowlist` via prefix matching and fails with a confusing error. This is a documentation bug.

3. **`language-configuration.json` declares only `#` as line comment** -- Line 3 sets `"lineComment": "#"` but the Lark grammar also supports `//` comments (line 44 of `limnalis.lark`). VS Code will only toggle `#` comments, not `//`, when the user presses the comment shortcut. This is a correctness issue for the editor extension.

4. **`format_diagnostics` is not yet consumed by any production code** -- The new `diagnostic_fmt.py` module is only tested, never imported from CLI or runtime code. This is expected for a foundation task but means the API could drift before integration.

## Verdict: PASS_WITH_ADVISORIES

## Advisories:

- **A1 (MEDIUM):** `Diagnostic.from_dict()` should use `raw.get("severity") or "info"` (or equivalent) to handle explicit `None` values gracefully, matching its documented contract. File: `src/limnalis/diagnostics.py` lines 37-42.
- **A2 (MEDIUM):** Fix documentation in `docs/cookbook/conformance_testing.md`: change `--case` to `--cases` on line 11, and remove `--all` from the `report` command on line 13 (or add `--all` as a valid flag to the `report` subcommand).
- **A3 (MEDIUM):** Add `//` as an additional line comment in `editor/vscode/language-configuration.json` to match the grammar's support for `//` comments.
- **A4 (LOW):** Consider adding property-level keyword highlighting to the TextMate grammar for commonly-used field names (`kind`, `binding`, `role`, `subtype`, `score`, etc.) to improve author experience.
- **A5 (LOW):** Add a test for `Diagnostic.from_dict()` with `None` values and for `format_diagnostics([])`.
