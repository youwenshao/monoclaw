"""Knowledge graph construction and retrieval using networkx."""

from __future__ import annotations

import json
import logging
from typing import Any

import networkx as nx

from openclaw_shared.database import get_db

from academic.paper_sieve.knowledge.concept_extractor import extract_paper_concepts

logger = logging.getLogger("openclaw.academic.paper_sieve.knowledge_graph")


def build_knowledge_graph(
    db_path: str,
    llm: Any,
) -> dict[str, Any]:
    """Build a knowledge graph from concepts extracted across all indexed papers.

    Returns {nodes: [{id, label, type, paper_count}],
             edges: [{from, to, label, weight}]}.
    """
    with get_db(db_path) as conn:
        papers = conn.execute(
            "SELECT id FROM papers WHERE indexed = 1"
        ).fetchall()

    all_concepts: list[dict[str, Any]] = []
    for paper in papers:
        concepts = extract_paper_concepts(db_path, paper["id"], llm)
        all_concepts.extend(concepts)

    G = _build_networkx_graph(all_concepts)
    graph_data = _serialize_graph(G)

    _store_graph(db_path, graph_data)

    return graph_data


def get_graph_data(db_path: str) -> dict[str, Any]:
    """Return the cached knowledge graph data for the frontend.

    Falls back to an empty graph if nothing has been built yet.
    """
    with get_db(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_graph_cache "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), graph_json TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        row = conn.execute(
            "SELECT graph_json FROM knowledge_graph_cache WHERE id = 1"
        ).fetchone()

    if row and row["graph_json"]:
        try:
            return json.loads(row["graph_json"])
        except json.JSONDecodeError:
            pass

    return {"nodes": [], "edges": []}


def _build_networkx_graph(concepts: list[dict[str, Any]]) -> nx.Graph:
    """Build a networkx graph from a flat list of concept dicts."""
    G = nx.Graph()

    node_papers: dict[str, set[int]] = {}
    node_types: dict[str, str] = {}

    for c in concepts:
        name = c["concept"].lower()
        node_types.setdefault(name, c.get("type", "other"))
        paper_id = c.get("paper_id")
        if paper_id is not None:
            node_papers.setdefault(name, set()).add(paper_id)

        for related in c.get("related_to", []):
            related_lower = related.lower()
            node_types.setdefault(related_lower, "other")
            if paper_id is not None:
                node_papers.setdefault(related_lower, set()).add(paper_id)

    for name in node_types:
        G.add_node(
            name,
            label=name,
            type=node_types[name],
            paper_count=len(node_papers.get(name, set())),
        )

    edge_weights: dict[tuple[str, str], int] = {}
    for c in concepts:
        src = c["concept"].lower()
        for related in c.get("related_to", []):
            tgt = related.lower()
            if src == tgt:
                continue
            edge_key = tuple(sorted([src, tgt]))
            edge_weights[edge_key] = edge_weights.get(edge_key, 0) + 1

    for (src, tgt), weight in edge_weights.items():
        G.add_edge(src, tgt, label="related_to", weight=weight)

    return G


def _serialize_graph(G: nx.Graph) -> dict[str, Any]:
    """Convert a networkx graph into the frontend-friendly dict format."""
    nodes = [
        {
            "id": node,
            "label": data.get("label", node),
            "type": data.get("type", "other"),
            "paper_count": data.get("paper_count", 0),
        }
        for node, data in G.nodes(data=True)
    ]

    edges = [
        {
            "from": u,
            "to": v,
            "label": data.get("label", "related_to"),
            "weight": data.get("weight", 1),
        }
        for u, v, data in G.edges(data=True)
    ]

    return {"nodes": nodes, "edges": edges}


def _store_graph(db_path: str, graph_data: dict[str, Any]) -> None:
    """Persist the graph JSON into a single-row cache table."""
    graph_json = json.dumps(graph_data, ensure_ascii=False)
    with get_db(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS knowledge_graph_cache "
            "(id INTEGER PRIMARY KEY CHECK (id = 1), graph_json TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO knowledge_graph_cache (id, graph_json) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET graph_json = excluded.graph_json, "
            "updated_at = CURRENT_TIMESTAMP",
            (graph_json,),
        )
    logger.info(
        "Stored knowledge graph: %d nodes, %d edges",
        len(graph_data.get("nodes", [])),
        len(graph_data.get("edges", [])),
    )
