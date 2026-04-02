"""SARIF 2.1.0 JSON builder for Limnalis diagnostics.

Produces a deterministic SARIF log from a list of Diagnostic objects or
raw dicts.  No external dependencies — pure Python JSON construction.
"""

from __future__ import annotations

from typing import Any

from .diagnostics import Diagnostic

_SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-schema-2.1.0.json"
)

_SEVERITY_TO_LEVEL: dict[str, str] = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}


def _coerce(item: Any) -> Diagnostic:
    if isinstance(item, Diagnostic):
        return item
    if isinstance(item, dict):
        return Diagnostic.from_dict(item)
    raise TypeError(f"Expected Diagnostic or dict, got {type(item).__name__}")


def _build_region(diag: Diagnostic) -> dict[str, Any] | None:
    if diag.span is None:
        return None
    return {
        "startLine": diag.span.start.line,
        "startColumn": diag.span.start.column,
        "endLine": diag.span.end.line,
        "endColumn": diag.span.end.column,
    }


def _result_sort_key(result: dict[str, Any]) -> tuple[str, str]:
    return (result.get("ruleId", ""), result["message"]["text"])


def diagnostics_to_sarif(
    diagnostics: list[Any],
    *,
    tool_name: str = "limnalis",
    tool_version: str | None = None,
    source_file: str | None = None,
) -> dict[str, Any]:
    """Convert diagnostics to a SARIF 2.1.0 JSON-compatible dict.

    Parameters
    ----------
    diagnostics:
        List of :class:`Diagnostic` objects or raw dicts.
    tool_name:
        Name of the reporting tool.
    tool_version:
        Version string.  Defaults to ``limnalis.version.PACKAGE_VERSION``.
    source_file:
        Path to the source file that produced these diagnostics.  When
        provided, each SARIF result includes an ``artifactLocation`` so
        that consumers (VS Code SARIF viewer, GitHub code scanning) can
        map results back to the originating file.  Without this, only
        ``region`` (line/column) data is emitted.
    """
    if tool_version is None:
        from .version import PACKAGE_VERSION

        tool_version = PACKAGE_VERSION

    typed = [_coerce(d) for d in diagnostics]

    # Build results and collect unique rule IDs
    rule_ids: dict[str, str] = {}  # code -> first message seen
    results: list[dict[str, Any]] = []

    for diag in typed:
        if diag.code not in rule_ids:
            rule_ids[diag.code] = diag.message

        properties: dict[str, str] = {}
        if diag.phase:
            properties["phase"] = diag.phase
        if diag.subject:
            properties["subject"] = diag.subject

        result: dict[str, Any] = {
            "ruleId": diag.code,
            "level": _SEVERITY_TO_LEVEL.get(diag.severity, "note"),
            "message": {"text": diag.message},
        }

        region = _build_region(diag)
        phys_loc: dict[str, Any] = {}
        if source_file is not None:
            phys_loc["artifactLocation"] = {"uri": source_file}
        if region is not None:
            phys_loc["region"] = region
        if phys_loc:
            result["locations"] = [{"physicalLocation": phys_loc}]

        if properties:
            result["properties"] = properties

        results.append(result)

    results.sort(key=_result_sort_key)

    rules = [
        {"id": code, "shortDescription": {"text": rule_ids[code]}}
        for code in sorted(rule_ids)
    ]

    return {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": tool_name,
                        "version": tool_version,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
