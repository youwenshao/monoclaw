"""Citation relationship mapping and cluster analysis."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Any

import networkx as nx

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.paper_sieve.citation_network")


def build_citation_network(db_path: str) -> dict[str, Any]:
    """Map citation relationships between indexed papers.

    Scans chunk text for references to other indexed papers (matched by
    title substring or DOI).

    Returns {nodes: [{id, title, authors, year, citation_count}],
             edges: [{source, target}]}.
    """
    with get_db(db_path) as conn:
        papers = conn.execute(
            "SELECT id, title, authors, year, doi FROM papers WHERE indexed = 1"
        ).fetchall()
        all_chunks = conn.execute(
            "SELECT paper_id, text_content FROM chunks ORDER BY paper_id, chunk_index"
        ).fetchall()

    paper_list = [dict(p) for p in papers]
    paper_texts: dict[int, str] = defaultdict(str)
    for chunk in all_chunks:
        paper_texts[chunk["paper_id"]] += " " + chunk["text_content"]

    edges: list[dict[str, int]] = []
    citation_counts: Counter[int] = Counter()

    for citing_paper in paper_list:
        citing_id = citing_paper["id"]
        full_text = paper_texts.get(citing_id, "").lower()
        if not full_text:
            continue

        for candidate in paper_list:
            if candidate["id"] == citing_id:
                continue

            if _paper_is_cited(full_text, candidate):
                edges.append({"source": citing_id, "target": candidate["id"]})
                citation_counts[candidate["id"]] += 1

    nodes = [
        {
            "id": p["id"],
            "title": p["title"],
            "authors": p["authors"],
            "year": p["year"],
            "citation_count": citation_counts.get(p["id"], 0),
        }
        for p in paper_list
    ]

    return {"nodes": nodes, "edges": edges}


def find_seminal_works(db_path: str) -> list[dict[str, Any]]:
    """Identify the most-cited papers in the local corpus."""
    network = build_citation_network(db_path)
    nodes = sorted(network["nodes"], key=lambda n: n["citation_count"], reverse=True)
    return [n for n in nodes if n["citation_count"] > 0]


def find_research_clusters(db_path: str) -> list[dict[str, Any]]:
    """Identify clusters of related papers using community detection on the citation graph."""
    network = build_citation_network(db_path)

    G = nx.Graph()
    node_map = {n["id"]: n for n in network["nodes"]}
    for n in network["nodes"]:
        G.add_node(n["id"])
    for e in network["edges"]:
        G.add_edge(e["source"], e["target"])

    if G.number_of_nodes() == 0:
        return []

    communities = nx.community.greedy_modularity_communities(G)

    clusters: list[dict[str, Any]] = []
    for idx, community in enumerate(communities):
        members = [node_map[nid] for nid in community if nid in node_map]
        if not members:
            continue

        years = [m["year"] for m in members if m.get("year")]
        clusters.append({
            "cluster_id": idx,
            "size": len(members),
            "papers": members,
            "year_range": (min(years), max(years)) if years else None,
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


def _paper_is_cited(full_text: str, candidate: dict[str, Any]) -> bool:
    """Heuristic check: does *full_text* cite *candidate*?

    Matches on DOI or title substring (>=6 words).
    """
    doi = candidate.get("doi")
    if doi and doi.lower() in full_text:
        return True

    title = candidate.get("title", "")
    title_words = title.split()
    if len(title_words) >= 6:
        search_fragment = " ".join(title_words[:8]).lower()
        if search_fragment in full_text:
            return True

    authors = candidate.get("authors", "")
    year = candidate.get("year")
    if authors and year:
        first_author_last = authors.split(",")[0].strip().split()[-1].lower()
        pattern = rf"\b{re.escape(first_author_last)}\b.*\b{year}\b"
        if re.search(pattern, full_text[:50000]):
            return True

    return False
