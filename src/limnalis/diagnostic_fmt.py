from __future__ import annotations

import json
from typing import Any

from .diagnostics import Diagnostic

# ---------------------------------------------------------------------------
# Remediation hints keyed by diagnostic code
# ---------------------------------------------------------------------------

REMEDIATION_HINTS: dict[str, str] = {
    "stubbed_primitive": (
        "Register a concrete implementation for this primitive via the plugin registry."
    ),
    "schema_validation_error": (
        "Check the normalized AST against the vendored JSON Schema and fix any structural mismatches."
    ),
    "evaluator_kind_canonicalized": (
        "Use the canonical evaluator kind spelling to suppress this warning."
    ),
    "frame_incomplete": (
        "Ensure all required frame fields (anchor, evaluator, criterion) are present."
    ),
    "baseline_mode_invalid": (
        "Use one of the accepted baseline modes: 'strict', 'permissive', or 'default'."
    ),
}

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_ANSI_RESET = "\033[0m"
_SEVERITY_COLORS: dict[str, str] = {
    "error": "\033[31m",   # red
    "warning": "\033[33m", # yellow
    "info": "\033[34m",    # blue
}

# Deterministic severity ordering (error first, then warning, then info).
_SEVERITY_ORDER: dict[str, int] = {"error": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _coerce(item: Any) -> Diagnostic:
    """Accept a Diagnostic or a raw dict and return a Diagnostic."""
    if isinstance(item, Diagnostic):
        return item
    if isinstance(item, dict):
        return Diagnostic.from_dict(item)
    raise TypeError(f"Expected Diagnostic or dict, got {type(item).__name__}")


def _sort_key(diag: Diagnostic) -> tuple[int, str, str, str]:
    return (
        _SEVERITY_ORDER.get(diag.severity, 99),
        diag.phase,
        diag.code,
        diag.subject,
    )


def _format_line(diag: Diagnostic, *, color: bool) -> str:
    severity_tag = diag.severity.upper()
    if color:
        c = _SEVERITY_COLORS.get(diag.severity, "")
        severity_tag = f"{c}{severity_tag}{_ANSI_RESET}"
    return (
        f"[{severity_tag}] "
        f"phase:{diag.phase} "
        f"code:{diag.code} "
        f"subject:{diag.subject} "
        f"\u2014 {diag.message}"
    )


def _hint_line(diag: Diagnostic) -> str | None:
    hint = REMEDIATION_HINTS.get(diag.code)
    if hint is None:
        return None
    return f"  hint: {hint}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_diagnostics(
    diagnostics: list[Any],
    *,
    mode: str = "plain",
    color: bool = False,
    show_hints: bool = True,
    source_file: str | None = None,
) -> str:
    """Format a list of diagnostics for human or machine consumption.

    Parameters
    ----------
    diagnostics:
        List of :class:`Diagnostic` objects or raw dicts (auto-normalised
        via ``Diagnostic.from_dict``).
    mode:
        ``"plain"`` -- one diagnostic per line.
        ``"grouped"`` -- diagnostics grouped by severity with headers.
        ``"json"`` -- deterministic JSON array.
        ``"sarif"`` -- SARIF 2.1.0 JSON output.
    color:
        Emit ANSI colour escapes for severity labels.
    show_hints:
        Append remediation hints for known diagnostic codes.
    source_file:
        Path to the source file that produced these diagnostics.  Passed
        through to SARIF output as ``artifactLocation.uri`` so that IDE
        consumers can map findings back to the originating file.
    """
    typed: list[Diagnostic] = [_coerce(d) for d in diagnostics]
    typed.sort(key=_sort_key)

    if mode == "json":
        return _format_json(typed)
    if mode == "sarif":
        from .sarif import diagnostics_to_sarif

        return json.dumps(
            diagnostics_to_sarif(typed, source_file=source_file),
            indent=2,
            ensure_ascii=False,
        )
    if mode == "grouped":
        return _format_grouped(typed, color=color, show_hints=show_hints)
    return _format_plain(typed, color=color, show_hints=show_hints)


def _format_plain(
    diagnostics: list[Diagnostic], *, color: bool, show_hints: bool
) -> str:
    lines: list[str] = []
    for diag in diagnostics:
        lines.append(_format_line(diag, color=color))
        if show_hints:
            hint = _hint_line(diag)
            if hint is not None:
                lines.append(hint)
    return "\n".join(lines)


def _format_grouped(
    diagnostics: list[Diagnostic], *, color: bool, show_hints: bool
) -> str:
    groups: dict[str, list[Diagnostic]] = {}
    for diag in diagnostics:
        groups.setdefault(diag.severity, []).append(diag)

    sections: list[str] = []
    for severity in ("error", "warning", "info"):
        group = groups.get(severity)
        if not group:
            continue
        header = severity.upper()
        if color:
            c = _SEVERITY_COLORS.get(severity, "")
            header = f"{c}{header}{_ANSI_RESET}"
        section_lines: list[str] = [f"--- {header} ---"]
        for diag in group:
            section_lines.append(_format_line(diag, color=color))
            if show_hints:
                hint = _hint_line(diag)
                if hint is not None:
                    section_lines.append(hint)
        sections.append("\n".join(section_lines))

    return "\n\n".join(sections)


def _format_json(diagnostics: list[Diagnostic]) -> str:
    return json.dumps(
        [d.to_schema_data() for d in diagnostics],
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
