"""Whoosh full-text search index for discovery documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from whoosh import index as whoosh_index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import DATETIME, ID, TEXT, Schema
from whoosh.highlight import UppercaseFormatter
from whoosh.qparser import MultifieldParser, OrGroup


def _schema() -> Schema:
    analyzer = StemmingAnalyzer()
    return Schema(
        id=ID(stored=True, unique=True),
        source_file=TEXT(stored=True, analyzer=analyzer),
        author=TEXT(stored=True, analyzer=analyzer),
        subject=TEXT(stored=True, analyzer=analyzer),
        body_text=TEXT(stored=True, analyzer=analyzer),
        date=ID(stored=True),
    )


def create_or_update_index(index_dir: str | Path) -> whoosh_index.Index:
    """Create a Whoosh index at *index_dir*, or open it if it already exists."""
    path = Path(index_dir)
    path.mkdir(parents=True, exist_ok=True)
    if whoosh_index.exists_in(str(path)):
        return whoosh_index.open_dir(str(path))
    return whoosh_index.create_in(str(path), _schema())


def add_document_to_index(index_dir: str | Path, doc: dict[str, Any]) -> None:
    """Add or update a single document in the search index."""
    ix = create_or_update_index(index_dir)
    writer = ix.writer()
    writer.update_document(
        id=str(doc.get("id", "")),
        source_file=doc.get("source_file", ""),
        author=doc.get("author", ""),
        subject=doc.get("subject", ""),
        body_text=doc.get("body_text", ""),
        date=doc.get("date_created", doc.get("date", "")),
    )
    writer.commit()


def search_documents(
    index_dir: str | Path,
    query_str: str,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """Search the Whoosh index with Boolean query support (AND/OR/NOT).

    Returns:
        dict with keys: results (list of hit dicts with highlights),
        total, page, per_page, query.
    """
    path = Path(index_dir)
    if not whoosh_index.exists_in(str(path)):
        return {"results": [], "total": 0, "page": page, "per_page": per_page, "query": query_str}

    ix = whoosh_index.open_dir(str(path))
    search_fields = ["subject", "body_text", "author", "source_file"]
    parser = MultifieldParser(search_fields, schema=ix.schema, group=OrGroup)
    parsed_query = parser.parse(query_str)

    results_list: list[dict[str, Any]] = []
    total = 0

    with ix.searcher() as searcher:
        results = searcher.search_page(parsed_query, page, pagelen=per_page)
        total = len(results)
        results.formatter = UppercaseFormatter()

        for hit in results:
            highlight_subject = hit.highlights("subject", top=3) or ""
            highlight_body = hit.highlights("body_text", top=3) or ""
            results_list.append({
                "id": hit.get("id"),
                "source_file": hit.get("source_file"),
                "author": hit.get("author"),
                "subject": hit.get("subject"),
                "date": hit.get("date"),
                "highlight_subject": highlight_subject,
                "highlight_body": highlight_body,
                "score": hit.score,
            })

    return {
        "results": results_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "query": query_str,
    }
