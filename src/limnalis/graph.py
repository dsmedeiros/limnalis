"""Graph builder and Mermaid renderer for Limnalis bundle structures.

Builds graph representations (nodes + edges) from normalized BundleNode
ASTs and renders them as deterministic Mermaid flowchart syntax.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .models.ast import BundleNode, FrameNode, FramePatternNode


@dataclass(frozen=True)
class GraphNode:
    """A node in a Limnalis structure graph."""

    id: str
    label: str
    kind: str  # "frame", "evaluator", "claim_block", "bridge", "evidence", "anchor"


@dataclass(frozen=True)
class GraphEdge:
    """A directed edge in a Limnalis structure graph."""

    source: str
    target: str
    label: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame_label(frame: FrameNode | FramePatternNode) -> str:
    """Produce a short human-readable label for a frame or frame pattern."""
    if isinstance(frame, FrameNode):
        return f"{frame.system}/{frame.namespace}/{frame.scale}"
    # FramePatternNode
    parts: list[str] = []
    fv = frame.facets
    for name in ("system", "namespace", "scale", "task", "regime"):
        val = getattr(fv, name, None)
        if val is not None:
            parts.append(val)
    return "/".join(parts) if parts else "pattern"


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def build_frame_graph(
    bundle: BundleNode,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build a graph of frames connected by bridges.

    Returns nodes for the bundle's own frame and each bridge endpoint,
    plus edges representing each bridge (labeled with ID and transport mode).
    """
    nodes_map: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # Main frame
    main_label = _frame_label(bundle.frame)
    main_id = f"frame_{bundle.id}"
    nodes_map[main_id] = GraphNode(id=main_id, label=main_label, kind="frame")

    for bridge in bundle.bridges:
        src_label = _frame_label(bridge.from_)
        src_id = f"frame_{bridge.id}_from"
        nodes_map[src_id] = GraphNode(id=src_id, label=src_label, kind="frame")

        dst_label = _frame_label(bridge.to)
        dst_id = f"frame_{bridge.id}_to"
        nodes_map[dst_id] = GraphNode(id=dst_id, label=dst_label, kind="frame")

        edge_label = f"{bridge.id} ({bridge.transport.mode})"
        edges.append(GraphEdge(source=src_id, target=dst_id, label=edge_label))

    nodes = sorted(nodes_map.values(), key=lambda n: n.id)
    edges.sort(key=lambda e: (e.source, e.target, e.label))
    return nodes, edges


def build_evaluator_graph(
    bundle: BundleNode,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build a graph linking evaluators to claim blocks.

    Creates a node for each evaluator (labeled with ID and kind) and each
    claim block (labeled with ID and stratum).  Edges connect evaluators
    to claim blocks based on resolution-policy membership when possible,
    otherwise all evaluators connect to all blocks.
    """
    nodes_map: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for ev in bundle.evaluators:
        ev_id = f"ev_{ev.id}"
        nodes_map[ev_id] = GraphNode(
            id=ev_id, label=f"{ev.id} ({ev.kind})", kind="evaluator"
        )

    for cb in bundle.claimBlocks:
        cb_id = f"cb_{cb.id}"
        nodes_map[cb_id] = GraphNode(
            id=cb_id, label=f"{cb.id} ({cb.stratum})", kind="claim_block"
        )

    # Determine which evaluators to connect
    rp = bundle.resolutionPolicy
    member_ids: list[str] | None = rp.members if rp.members else (rp.order if rp.order else None)

    ev_ids_to_connect: list[str]
    if member_ids is not None:
        ev_ids_to_connect = [eid for eid in member_ids if f"ev_{eid}" in nodes_map]
    else:
        ev_ids_to_connect = [ev.id for ev in bundle.evaluators]

    for ev_id_raw in ev_ids_to_connect:
        for cb in bundle.claimBlocks:
            edges.append(
                GraphEdge(
                    source=f"ev_{ev_id_raw}",
                    target=f"cb_{cb.id}",
                    label="evaluates",
                )
            )

    nodes = sorted(nodes_map.values(), key=lambda n: n.id)
    edges.sort(key=lambda e: (e.source, e.target, e.label))
    return nodes, edges


def build_evidence_graph(
    bundle: BundleNode,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build a graph of evidence items connected by evidence relations.

    Creates a node for each evidence item (labeled with ID and kind) and
    edges from each evidence_relation entry (lhs -> rhs, labeled with
    relation kind).
    """
    nodes_map: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for ev in bundle.evidence:
        nid = f"evi_{ev.id}"
        nodes_map[nid] = GraphNode(id=nid, label=f"{ev.id} ({ev.kind})", kind="evidence")

    for rel in bundle.evidenceRelations:
        edges.append(
            GraphEdge(
                source=f"evi_{rel.lhs}",
                target=f"evi_{rel.rhs}",
                label=rel.kind,
            )
        )

    nodes = sorted(nodes_map.values(), key=lambda n: n.id)
    edges.sort(key=lambda e: (e.source, e.target, e.label))
    return nodes, edges


# ---------------------------------------------------------------------------
# Mermaid renderer
# ---------------------------------------------------------------------------

_SHAPE_MAP = {
    "frame": ("[", "]"),         # rectangle
    "evaluator": ("([", "])"),   # rounded / stadium
    "claim_block": ("[/", "/]"), # trapezoid (right-leaning)
    "evidence": ("((", "))"),    # circle
    "bridge": ("[", "]"),
    "anchor": ("[", "]"),
}


def _build_mermaid_id_map(ids: list[str]) -> dict[str, str]:
    """Build a collision-safe mapping from raw IDs to Mermaid-safe IDs.

    Distinct raw IDs like ``a-b`` and ``a_b`` would both sanitise to
    ``a_b``.  This function detects such collisions and appends a
    numeric suffix to disambiguate.  It tracks *emitted* IDs (not just
    base candidates) so that suffixed IDs like ``a_b_1`` cannot collide
    with a raw ID that also sanitises to ``a_b_1``.
    """
    sanitised: dict[str, str] = {}  # raw -> mermaid id
    emitted: set[str] = set()  # all final mermaid ids assigned so far

    for raw in ids:
        candidate = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw)
        if candidate not in emitted:
            unique = candidate
        else:
            counter = 1
            while f"{candidate}_{counter}" in emitted:
                counter += 1
            unique = f"{candidate}_{counter}"
        emitted.add(unique)
        sanitised[raw] = unique

    return sanitised


def render_mermaid(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    *,
    title: str = "",
    direction: str = "TD",
) -> str:
    """Render nodes and edges as a Mermaid flowchart string.

    Output is deterministic: nodes and edges are sorted by ID / endpoints.
    """
    lines: list[str] = []
    if title:
        safe_title = title.replace("\n", " ").replace("\r", "")
        lines.append(f"---")
        lines.append(f"title: {safe_title}")
        lines.append(f"---")
    lines.append(f"flowchart {direction}")

    sorted_nodes = sorted(nodes, key=lambda n: n.id)
    sorted_edges = sorted(edges, key=lambda e: (e.source, e.target, e.label))

    # Build collision-safe ID map from all raw IDs (nodes + edge endpoints)
    all_raw_ids = [n.id for n in sorted_nodes]
    for e in sorted_edges:
        if e.source not in all_raw_ids:
            all_raw_ids.append(e.source)
        if e.target not in all_raw_ids:
            all_raw_ids.append(e.target)
    id_map = _build_mermaid_id_map(all_raw_ids)

    for node in sorted_nodes:
        mid = id_map[node.id]
        left, right = _SHAPE_MAP.get(node.kind, ("[", "]"))
        safe_label = node.label.replace('"', "'").replace("`", "'").replace("\n", " ").replace("\r", "")
        lines.append(f"    {mid}{left}\"{safe_label}\"{right}")

    for edge in sorted_edges:
        src = id_map[edge.source]
        tgt = id_map[edge.target]
        safe_label = edge.label.replace('"', "'").replace("`", "'").replace("\n", " ").replace("\r", "")
        lines.append(f"    {src} -->|\"{safe_label}\"| {tgt}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def graph_to_json(
    nodes: list[GraphNode], edges: list[GraphEdge], *, indent: int = 2
) -> str:
    """Serialise a graph as a JSON object with ``nodes`` and ``edges`` arrays."""
    return json.dumps(
        {
            "nodes": [asdict(n) for n in sorted(nodes, key=lambda n: n.id)],
            "edges": [
                asdict(e)
                for e in sorted(edges, key=lambda e: (e.source, e.target, e.label))
            ],
        },
        indent=indent,
    )
