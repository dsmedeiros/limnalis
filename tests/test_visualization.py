"""Tests for graph builder and Mermaid visualization (T6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from limnalis.graph import (
    GraphEdge,
    GraphNode,
    build_evidence_graph,
    build_evaluator_graph,
    build_frame_graph,
    graph_to_json,
    render_mermaid,
)
from limnalis.loader import load_surface_bundle

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CWT_PATH = EXAMPLES / "cwt_transport_bundle.lmn"
GOV_PATH = EXAMPLES / "governance_stack_bundle.lmn"


# ---------------------------------------------------------------------------
# Frame graph tests
# ---------------------------------------------------------------------------


class TestBuildFrameGraph:
    def test_cwt_has_bridge_nodes(self):
        bundle = load_surface_bundle(CWT_PATH)
        nodes, edges = build_frame_graph(bundle)

        # Main frame + 2 bridges * 2 endpoints = 5 nodes
        assert len(nodes) >= 3
        kinds = {n.kind for n in nodes}
        assert kinds == {"frame"}

        # Two bridges -> two edges
        assert len(edges) == 2

    def test_cwt_edge_labels_contain_mode(self):
        bundle = load_surface_bundle(CWT_PATH)
        _nodes, edges = build_frame_graph(bundle)

        labels = [e.label for e in edges]
        assert any("remap_recompute" in lbl for lbl in labels)
        assert any("degrade" in lbl for lbl in labels)

    def test_empty_bridges_produces_single_frame(self):
        """A bundle with no bridges produces a frame graph with just the main frame."""
        bundle = load_surface_bundle(GOV_PATH)
        nodes, edges = build_frame_graph(bundle)

        assert len(nodes) == 1
        assert nodes[0].kind == "frame"
        assert len(edges) == 0


# ---------------------------------------------------------------------------
# Evaluator graph tests
# ---------------------------------------------------------------------------


class TestBuildEvaluatorGraph:
    def test_governance_has_evaluators_and_blocks(self):
        bundle = load_surface_bundle(GOV_PATH)
        nodes, edges = build_evaluator_graph(bundle)

        ev_nodes = [n for n in nodes if n.kind == "evaluator"]
        cb_nodes = [n for n in nodes if n.kind == "claim_block"]

        # governance_stack has 3 evaluators and 3 claim blocks
        assert len(ev_nodes) == 3
        assert len(cb_nodes) == 3

    def test_governance_evaluator_labels_include_kind(self):
        bundle = load_surface_bundle(GOV_PATH)
        nodes, _edges = build_evaluator_graph(bundle)

        ev_labels = [n.label for n in nodes if n.kind == "evaluator"]
        assert any("institution" in lbl for lbl in ev_labels)
        assert any("human" in lbl for lbl in ev_labels)
        assert any("model" in lbl for lbl in ev_labels)

    def test_governance_edges_use_resolution_members(self):
        bundle = load_surface_bundle(GOV_PATH)
        _nodes, edges = build_evaluator_graph(bundle)

        # 3 evaluators in rp_adjudicated members * 3 claim blocks = 9 edges
        assert len(edges) == 9
        assert all(e.label == "evaluates" for e in edges)


# ---------------------------------------------------------------------------
# Evidence graph tests
# ---------------------------------------------------------------------------


class TestBuildEvidenceGraph:
    def test_governance_evidence_nodes(self):
        bundle = load_surface_bundle(GOV_PATH)
        nodes, edges = build_evidence_graph(bundle)

        # 4 evidence items
        assert len(nodes) == 4
        assert all(n.kind == "evidence" for n in nodes)

    def test_governance_evidence_relations(self):
        bundle = load_surface_bundle(GOV_PATH)
        _nodes, edges = build_evidence_graph(bundle)

        # 3 evidence relations
        assert len(edges) == 3
        labels = {e.label for e in edges}
        assert "conflicts" in labels
        assert "corroborates" in labels

    def test_cwt_evidence_relations(self):
        bundle = load_surface_bundle(CWT_PATH)
        nodes, edges = build_evidence_graph(bundle)

        assert len(nodes) == 4
        assert len(edges) == 2
        labels = {e.label for e in edges}
        assert "corroborates" in labels
        assert "depends_on" in labels


# ---------------------------------------------------------------------------
# Mermaid renderer tests
# ---------------------------------------------------------------------------


class TestRenderMermaid:
    def test_produces_valid_flowchart(self):
        nodes = [
            GraphNode(id="a", label="Alpha", kind="frame"),
            GraphNode(id="b", label="Beta", kind="evaluator"),
        ]
        edges = [GraphEdge(source="a", target="b", label="connects")]

        output = render_mermaid(nodes, edges)
        assert output.startswith("flowchart TD")
        assert "-->" in output

    def test_title_included(self):
        nodes = [GraphNode(id="a", label="A", kind="frame")]
        output = render_mermaid(nodes, [], title="Test Title")
        assert "title: Test Title" in output

    def test_direction_param(self):
        nodes = [GraphNode(id="a", label="A", kind="frame")]
        output = render_mermaid(nodes, [], direction="LR")
        assert "flowchart LR" in output

    def test_node_shapes_by_kind(self):
        nodes = [
            GraphNode(id="f1", label="Frame", kind="frame"),
            GraphNode(id="e1", label="Eval", kind="evaluator"),
            GraphNode(id="cb1", label="Block", kind="claim_block"),
            GraphNode(id="ev1", label="Evi", kind="evidence"),
        ]
        output = render_mermaid(nodes, [])

        # frame = rectangle [...]
        assert 'f1["Frame"]' in output
        # evaluator = stadium ([...])
        assert 'e1(["Eval"])' in output
        # claim_block = trapezoid [/... /]
        assert 'cb1[/"Block"/]' in output
        # evidence = circle ((...))
        assert 'ev1(("Evi"))' in output

    def test_edge_pipe_notation(self):
        nodes = [
            GraphNode(id="a", label="A", kind="frame"),
            GraphNode(id="b", label="B", kind="frame"),
        ]
        edges = [GraphEdge(source="a", target="b", label="link")]
        output = render_mermaid(nodes, edges)
        assert 'a -->|"link"| b' in output


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_frame_graph_deterministic(self):
        bundle = load_surface_bundle(CWT_PATH)
        r1 = build_frame_graph(bundle)
        r2 = build_frame_graph(bundle)
        assert r1 == r2

    def test_evaluator_graph_deterministic(self):
        bundle = load_surface_bundle(GOV_PATH)
        r1 = build_evaluator_graph(bundle)
        r2 = build_evaluator_graph(bundle)
        assert r1 == r2

    def test_evidence_graph_deterministic(self):
        bundle = load_surface_bundle(GOV_PATH)
        r1 = build_evidence_graph(bundle)
        r2 = build_evidence_graph(bundle)
        assert r1 == r2

    def test_mermaid_output_deterministic(self):
        bundle = load_surface_bundle(CWT_PATH)
        nodes, edges = build_frame_graph(bundle)
        m1 = render_mermaid(nodes, edges, title="T")
        m2 = render_mermaid(nodes, edges, title="T")
        assert m1 == m2


# ---------------------------------------------------------------------------
# JSON output tests
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_graph_to_json_valid(self):
        nodes = [GraphNode(id="a", label="A", kind="frame")]
        edges = [GraphEdge(source="a", target="a", label="self")]
        output = graph_to_json(nodes, edges)
        data = json.loads(output)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1

    def test_graph_to_json_structure(self):
        bundle = load_surface_bundle(CWT_PATH)
        nodes, edges = build_frame_graph(bundle)
        data = json.loads(graph_to_json(nodes, edges))
        for node in data["nodes"]:
            assert set(node.keys()) == {"id", "label", "kind"}
        for edge in data["edges"]:
            assert set(edge.keys()) == {"source", "target", "label"}


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_frame_graph_mermaid(self, capsys):
        from limnalis.cli import main

        rc = main(["visualize", "frame-graph", str(CWT_PATH)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "flowchart" in out
        assert "-->" in out

    def test_evaluator_graph_mermaid(self, capsys):
        from limnalis.cli import main

        rc = main(["visualize", "evaluator-graph", str(GOV_PATH)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "flowchart" in out

    def test_evidence_graph_json(self, capsys):
        from limnalis.cli import main

        rc = main(["visualize", "evidence-graph", "--format", "json", str(GOV_PATH)])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "nodes" in data
        assert "edges" in data

    def test_frame_graph_json(self, capsys):
        from limnalis.cli import main

        rc = main(["visualize", "frame-graph", "--format", "json", str(CWT_PATH)])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["edges"]) == 2

    def test_missing_file(self, capsys):
        from limnalis.cli import main

        rc = main(["visualize", "frame-graph", "nonexistent.lmn"])
        assert rc == 1
