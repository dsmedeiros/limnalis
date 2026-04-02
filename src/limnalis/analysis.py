"""Structural analysis functions for normalized Limnalis ASTs.

Public API:
    extract_symbols(bundle)      — extract all named IDs grouped by type
    analyze_structure(bundle)    — run structural checks returning diagnostic dicts
"""
from __future__ import annotations

from .models.ast import BundleNode, FramePatternNode


def extract_symbols(bundle: BundleNode) -> dict[str, list[str]]:
    """Extract all named IDs from a normalized AST, grouped by type.

    All lists are sorted alphabetically for deterministic output.
    """
    result: dict[str, list[str]] = {
        "bundle": [bundle.id],
        "evaluators": sorted(ev.id for ev in bundle.evaluators),
        "claim_blocks": sorted(cb.id for cb in bundle.claimBlocks),
        "claims": sorted(
            claim.id for cb in bundle.claimBlocks for claim in cb.claims
        ),
        "bridges": sorted(br.id for br in bundle.bridges),
        "anchors": sorted(a.id for a in bundle.anchors),
        "evidence": sorted(e.id for e in bundle.evidence),
        "baselines": sorted(b.id for b in bundle.baselines),
    }
    return result


def analyze_structure(bundle: BundleNode) -> list[dict]:
    """Run structural checks on a normalized AST.

    Returns a list of diagnostic-like dicts for any issues found.
    Exactly three checks are performed:
      1. Unreferenced evaluators
      2. Empty claim blocks
      3. Missing frame facets (FramePattern with fewer than 3 facets)
    """
    diagnostics: list[dict] = []

    # 1. Unreferenced evaluators — evaluators not referenced by the resolution
    #    policy's members or order lists.
    rp = bundle.resolutionPolicy
    referenced_ids: set[str] = set()
    if rp.members:
        referenced_ids.update(rp.members)
    if rp.order:
        referenced_ids.update(rp.order)
    for ev in bundle.evaluators:
        if ev.id not in referenced_ids:
            diagnostics.append({
                "severity": "warning",
                "phase": "analysis",
                "code": "unreferenced_evaluator",
                "subject": ev.id,
                "message": (
                    f"Evaluator '{ev.id}' is not referenced by the "
                    f"resolution policy"
                ),
            })

    # 2. Empty claim blocks — blocks with zero claims.
    for cb in bundle.claimBlocks:
        if len(cb.claims) == 0:
            diagnostics.append({
                "severity": "warning",
                "phase": "analysis",
                "code": "empty_claim_block",
                "subject": cb.id,
                "message": f"Claim block '{cb.id}' contains no claims",
            })

    # 3. Missing frame facets — FramePattern with fewer than 3 facets set.
    frame = bundle.frame
    if isinstance(frame, FramePatternNode):
        facets = frame.facets
        count = sum(
            1
            for field_name in type(facets).model_fields
            if getattr(facets, field_name) is not None
        )
        if count < 3:
            diagnostics.append({
                "severity": "warning",
                "phase": "analysis",
                "code": "missing_frame_facets",
                "subject": bundle.id,
                "message": (
                    f"Frame pattern has only {count} facet(s) set "
                    f"(recommend at least 3)"
                ),
            })

    # Sort for deterministic output
    diagnostics.sort(key=lambda d: (d["code"], d["subject"]))
    return diagnostics
