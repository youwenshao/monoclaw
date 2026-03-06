"""PaperSieve FastAPI routes — paper ingestion, semantic search, RAG Q&A."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

try:
    from academic.paper_sieve.ingestion.pdf_parser import extract_text_from_pdf, detect_sections
    from academic.paper_sieve.ingestion.metadata_extractor import (
        extract_metadata_from_pdf,
        extract_metadata_from_doi,
    )
    from academic.paper_sieve.ingestion.chunker import chunk_paper
    from academic.paper_sieve.ingestion.reference_parser import extract_references
    from academic.paper_sieve.indexing.index_manager import index_paper, get_index_stats
    from academic.paper_sieve.indexing.embedder import embed_query
    from academic.paper_sieve.indexing.chroma_store import get_collection, search as chroma_search, delete_paper as chroma_delete

    _DEPS_AVAILABLE = True
except ImportError as _import_err:
    _DEPS_AVAILABLE = False
    _IMPORT_ERROR = str(_import_err)

logger = logging.getLogger("openclaw.academic.paper_sieve.routes")

router = APIRouter(prefix="/paper-sieve", tags=["PaperSieve"])

templates = Jinja2Templates(directory="academic/dashboard/templates")


# ── Pydantic request models ──────────────────────────────────────────────

class QARequest(BaseModel):
    question: str


class TagsRequest(BaseModel):
    tags: list[str]


class CreateReviewRequest(BaseModel):
    review_name: str
    research_question: str
    inclusion_criteria: str = ""
    exclusion_criteria: str = ""


class ScreenPaperRequest(BaseModel):
    paper_id: int
    status: str  # included / excluded / maybe
    exclusion_reason: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────

def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "paper-sieve",
        **extra,
    }


def _db(request: Request) -> Path:
    return request.app.state.db_paths["paper_sieve"]


def _mona_db(request: Request) -> Path:
    return request.app.state.db_paths["mona_events"]


def _chroma_path(request: Request) -> Path:
    return request.app.state.workspace / "chroma" / "paper_sieve"


def _papers_dir(request: Request) -> Path:
    d = request.app.state.workspace / "papers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _require_deps() -> None:
    if not _DEPS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"PaperSieve dependencies not installed: {_IMPORT_ERROR}",
        )


# ── Dashboard page ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def paper_sieve_page(request: Request) -> HTMLResponse:
    db = _db(request)

    stats: dict[str, Any] = {
        "total_papers": 0,
        "indexed_papers": 0,
        "total_queries": 0,
        "total_reviews": 0,
    }

    try:
        with get_db(db) as conn:
            stats["total_papers"] = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            stats["indexed_papers"] = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE indexed = TRUE"
            ).fetchone()[0]
            stats["total_queries"] = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
            stats["total_reviews"] = conn.execute(
                "SELECT COUNT(*) FROM systematic_reviews"
            ).fetchone()[0]
    except Exception:
        logger.warning("Could not read paper_sieve stats — database may not be initialised")

    return templates.TemplateResponse(
        "paper_sieve/index.html",
        _ctx(request, stats=stats),
    )


# ── Upload & Ingest ──────────────────────────────────────────────────────

@router.post("/upload")
async def upload_paper(request: Request, file: UploadFile) -> dict[str, Any]:
    _require_deps()
    db = _db(request)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    dest = _papers_dir(request) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    metadata = extract_metadata_from_pdf(str(dest))

    if metadata.get("doi"):
        doi_meta = extract_metadata_from_doi(metadata["doi"])
        for key in ("journal", "volume", "pages"):
            if doi_meta.get(key) and not metadata.get(key):
                metadata[key] = doi_meta[key]
        if doi_meta.get("title") and (not metadata.get("title") or len(metadata["title"]) < 5):
            metadata["title"] = doi_meta["title"]

    with get_db(db) as conn:
        cur = conn.execute(
            """INSERT INTO papers
               (title, authors, abstract, doi, year, journal, volume, pages,
                file_path, total_pages, language)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metadata.get("title") or file.filename,
                json.dumps(metadata.get("authors", [])),
                metadata.get("abstract"),
                metadata.get("doi"),
                metadata.get("year"),
                metadata.get("journal"),
                metadata.get("volume"),
                metadata.get("pages"),
                str(dest),
                metadata.get("total_pages"),
                "en",
            ),
        )
        paper_id = cur.lastrowid

    pages = extract_text_from_pdf(str(dest))
    sections = detect_sections(pages)
    chunks = chunk_paper(sections)

    try:
        result = index_paper(db, _chroma_path(request), paper_id, chunks)
    except Exception as exc:
        logger.error("Indexing failed for paper %d: %s", paper_id, exc)
        result = {"paper_id": paper_id, "chunk_count": 0, "error": str(exc)}

    emit_event(
        _mona_db(request),
        tool="paper_sieve",
        action="paper_uploaded",
        detail=f"Uploaded '{metadata.get('title', file.filename)}' ({len(chunks)} chunks)",
    )

    return {
        "paper_id": paper_id,
        "title": metadata.get("title"),
        "authors": metadata.get("authors", []),
        "chunks_indexed": result.get("chunk_count", 0),
    }


# ── Semantic Search ──────────────────────────────────────────────────────

@router.get("/search")
async def semantic_search(request: Request, q: str, n: int = 10) -> list[dict[str, Any]]:
    _require_deps()
    db = _db(request)

    query_vec = embed_query(q)
    collection = get_collection(_chroma_path(request))
    raw_results = chroma_search(collection, query_vec, n_results=n)

    results: list[dict[str, Any]] = []
    for hit in raw_results:
        paper_info: dict[str, Any] = {}
        paper_id = hit.get("metadata", {}).get("paper_id")
        if paper_id:
            with get_db(db) as conn:
                row = conn.execute(
                    "SELECT id, title, authors, year, journal FROM papers WHERE id = ?",
                    (paper_id,),
                ).fetchone()
                if row:
                    paper_info = dict(row)
                    try:
                        paper_info["authors"] = json.loads(paper_info.get("authors") or "[]")
                    except (json.JSONDecodeError, TypeError):
                        paper_info["authors"] = []

        results.append({
            "text": hit.get("text", ""),
            "section": hit.get("metadata", {}).get("section_name", ""),
            "distance": hit.get("distance"),
            "relevance": round(1.0 - (hit.get("distance") or 0.0), 3),
            "paper": paper_info,
        })

    return results


# ── RAG Question Answering ───────────────────────────────────────────────

@router.post("/qa")
async def question_answer(request: Request, body: QARequest) -> dict[str, Any]:
    _require_deps()
    db = _db(request)

    query_vec = embed_query(body.question)
    collection = get_collection(_chroma_path(request))
    hits = chroma_search(collection, query_vec, n_results=5)

    context_parts: list[str] = []
    cited_chunks: list[dict[str, Any]] = []
    for hit in hits:
        context_parts.append(hit.get("text", ""))
        cited_chunks.append({
            "chroma_id": hit.get("id"),
            "section": hit.get("metadata", {}).get("section_name", ""),
            "paper_id": hit.get("metadata", {}).get("paper_id"),
            "distance": hit.get("distance"),
        })

    context = "\n\n---\n\n".join(context_parts)
    llm = getattr(request.app.state, "llm", None)

    if llm:
        prompt = (
            f"Based on the following excerpts from academic papers, answer the question.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {body.question}\n\n"
            f"Provide a detailed answer with inline citations referencing the relevant passages."
        )
        try:
            answer = await llm.generate(prompt)
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            answer = f"LLM unavailable — retrieved {len(hits)} relevant passages. Review them in the sources panel."
    else:
        answer = f"No LLM configured — retrieved {len(hits)} relevant passages. Review them in the sources panel."

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO queries (query_text, answer_text, cited_chunks, confidence) VALUES (?, ?, ?, ?)",
            (body.question, answer, json.dumps(cited_chunks), hits[0]["distance"] if hits else None),
        )

    emit_event(
        _mona_db(request),
        tool="paper_sieve",
        action="qa_query",
        detail=f"Q: {body.question[:80]}",
    )

    return {
        "question": body.question,
        "answer": answer,
        "sources": cited_chunks,
    }


# ── Paper CRUD ───────────────────────────────────────────────────────────

@router.get("/papers")
async def list_papers(
    request: Request,
    year: int | None = None,
    tag: str | None = None,
    indexed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    db = _db(request)
    query = "SELECT * FROM papers WHERE 1=1"
    params: list[Any] = []

    if year:
        query += " AND year = ?"
        params.append(year)
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    if indexed is not None:
        query += " AND indexed = ?"
        params.append(indexed)

    query += " ORDER BY added_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()

    papers = []
    for row in rows:
        paper = dict(row)
        try:
            paper["authors"] = json.loads(paper.get("authors") or "[]")
        except (json.JSONDecodeError, TypeError):
            paper["authors"] = []
        try:
            paper["tags"] = json.loads(paper.get("tags") or "[]")
        except (json.JSONDecodeError, TypeError):
            paper["tags"] = [t.strip() for t in (paper.get("tags") or "").split(",") if t.strip()]
        papers.append(paper)

    return papers


@router.get("/papers/{paper_id}")
async def get_paper(request: Request, paper_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    paper = dict(row)
    try:
        paper["authors"] = json.loads(paper.get("authors") or "[]")
    except (json.JSONDecodeError, TypeError):
        paper["authors"] = []
    try:
        paper["tags"] = json.loads(paper.get("tags") or "[]")
    except (json.JSONDecodeError, TypeError):
        paper["tags"] = [t.strip() for t in (paper.get("tags") or "").split(",") if t.strip()]

    with get_db(db) as conn:
        chunks = conn.execute(
            "SELECT chunk_index, section_name, token_count FROM chunks WHERE paper_id = ? ORDER BY chunk_index",
            (paper_id,),
        ).fetchall()
    paper["chunks"] = [dict(c) for c in chunks]

    return paper


@router.delete("/papers/{paper_id}")
async def delete_paper_route(request: Request, paper_id: int) -> dict[str, str]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT title, file_path FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    title = row["title"]

    if _DEPS_AVAILABLE:
        try:
            collection = get_collection(_chroma_path(request))
            chroma_delete(collection, paper_id)
        except Exception as exc:
            logger.warning("ChromaDB cleanup failed for paper %d: %s", paper_id, exc)

    with get_db(db) as conn:
        conn.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM review_papers WHERE paper_id = ?", (paper_id,))
        conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))

    if row["file_path"]:
        fp = Path(row["file_path"])
        if fp.exists():
            fp.unlink()

    emit_event(
        _mona_db(request),
        tool="paper_sieve",
        action="paper_deleted",
        detail=f"Deleted '{title}'",
    )

    return {"status": "deleted", "paper_id": str(paper_id)}


@router.post("/papers/{paper_id}/tags")
async def update_tags(request: Request, paper_id: int, body: TagsRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Paper not found")

    with get_db(db) as conn:
        conn.execute(
            "UPDATE papers SET tags = ? WHERE id = ?",
            (json.dumps(body.tags), paper_id),
        )

    return {"paper_id": paper_id, "tags": body.tags}


# ── Systematic Reviews ───────────────────────────────────────────────────

@router.get("/reviews")
async def list_reviews(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM systematic_reviews ORDER BY created_at DESC"
        ).fetchall()

    reviews = []
    for row in rows:
        review = dict(row)
        with get_db(db) as conn:
            counts = conn.execute(
                """SELECT
                     COUNT(*) AS total,
                     SUM(CASE WHEN screening_status = 'included' THEN 1 ELSE 0 END) AS included,
                     SUM(CASE WHEN screening_status = 'excluded' THEN 1 ELSE 0 END) AS excluded,
                     SUM(CASE WHEN screening_status = 'pending' THEN 1 ELSE 0 END) AS pending
                   FROM review_papers WHERE review_id = ?""",
                (review["id"],),
            ).fetchone()
        review["paper_counts"] = dict(counts) if counts else {}
        reviews.append(review)

    return reviews


@router.post("/reviews")
async def create_review(request: Request, body: CreateReviewRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        cur = conn.execute(
            """INSERT INTO systematic_reviews
               (review_name, research_question, inclusion_criteria, exclusion_criteria)
               VALUES (?, ?, ?, ?)""",
            (body.review_name, body.research_question, body.inclusion_criteria, body.exclusion_criteria),
        )
        review_id = cur.lastrowid

    emit_event(
        _mona_db(request),
        tool="paper_sieve",
        action="review_created",
        detail=f"Created review '{body.review_name}'",
    )

    return {"review_id": review_id, "review_name": body.review_name, "status": "screening"}


@router.get("/reviews/{review_id}")
async def get_review(request: Request, review_id: int) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM systematic_reviews WHERE id = ?", (review_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    review = dict(row)

    with get_db(db) as conn:
        papers = conn.execute(
            """SELECT rp.*, p.title, p.authors, p.year, p.journal
               FROM review_papers rp
               JOIN papers p ON rp.paper_id = p.id
               WHERE rp.review_id = ?
               ORDER BY rp.screening_status, p.year DESC""",
            (review_id,),
        ).fetchall()

    review["papers"] = []
    for p in papers:
        pd = dict(p)
        try:
            pd["authors"] = json.loads(pd.get("authors") or "[]")
        except (json.JSONDecodeError, TypeError):
            pd["authors"] = []
        review["papers"].append(pd)

    return review


@router.post("/reviews/{review_id}/screen")
async def screen_paper(request: Request, review_id: int, body: ScreenPaperRequest) -> dict[str, Any]:
    db = _db(request)

    if body.status not in ("included", "excluded", "maybe", "pending"):
        raise HTTPException(status_code=400, detail="Invalid screening status")

    with get_db(db) as conn:
        existing = conn.execute(
            "SELECT id FROM review_papers WHERE review_id = ? AND paper_id = ?",
            (review_id, body.paper_id),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE review_papers SET screening_status = ?, exclusion_reason = ? WHERE id = ?",
                (body.status, body.exclusion_reason, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO review_papers (review_id, paper_id, screening_status, exclusion_reason)
                   VALUES (?, ?, ?, ?)""",
                (review_id, body.paper_id, body.status, body.exclusion_reason),
            )

    return {"review_id": review_id, "paper_id": body.paper_id, "status": body.status}


# ── Knowledge Graph & Citation Network ───────────────────────────────────

@router.get("/knowledge-graph")
async def knowledge_graph(request: Request) -> dict[str, Any]:
    db = _db(request)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    with get_db(db) as conn:
        papers = conn.execute(
            "SELECT id, title, authors, year, tags FROM papers ORDER BY year"
        ).fetchall()

    author_map: dict[str, int] = {}
    next_author_id = 10000

    for paper in papers:
        paper_id = paper["id"]
        nodes.append({
            "id": paper_id,
            "label": (paper["title"] or "Untitled")[:40],
            "group": "paper",
            "year": paper["year"],
        })

        try:
            authors = json.loads(paper["authors"] or "[]")
        except (json.JSONDecodeError, TypeError):
            authors = []

        for author in authors:
            if author not in author_map:
                author_map[author] = next_author_id
                nodes.append({
                    "id": next_author_id,
                    "label": author,
                    "group": "author",
                })
                next_author_id += 1

            edges.append({
                "from": author_map[author],
                "to": paper_id,
                "relation": "authored",
            })

        try:
            tags = json.loads(paper["tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            tags = []

        for tag in tags:
            tag_key = f"tag:{tag}"
            if tag_key not in author_map:
                author_map[tag_key] = next_author_id
                nodes.append({
                    "id": next_author_id,
                    "label": tag,
                    "group": "tag",
                })
                next_author_id += 1

            edges.append({
                "from": paper_id,
                "to": author_map[tag_key],
                "relation": "tagged",
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/citation-network")
async def citation_network(request: Request) -> dict[str, Any]:
    db = _db(request)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    with get_db(db) as conn:
        papers = conn.execute(
            "SELECT id, title, year, doi FROM papers ORDER BY year"
        ).fetchall()

    for paper in papers:
        nodes.append({
            "id": paper["id"],
            "label": (paper["title"] or "Untitled")[:40],
            "year": paper["year"],
            "doi": paper["doi"],
        })

    return {"nodes": nodes, "edges": edges}


# ── HTMX Partials ────────────────────────────────────────────────────────

@router.get("/partials/paper-library", response_class=HTMLResponse)
async def partial_paper_library(
    request: Request,
    year: int | None = None,
    tag: str | None = None,
) -> HTMLResponse:
    db = _db(request)

    query = "SELECT * FROM papers WHERE 1=1"
    params: list[Any] = []
    if year:
        query += " AND year = ?"
        params.append(year)
    if tag:
        query += " AND tags LIKE ?"
        params.append(f"%{tag}%")
    query += " ORDER BY added_at DESC LIMIT 50"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()

    papers = []
    for row in rows:
        paper = dict(row)
        try:
            paper["authors"] = json.loads(paper.get("authors") or "[]")
        except (json.JSONDecodeError, TypeError):
            paper["authors"] = []
        try:
            paper["tags"] = json.loads(paper.get("tags") or "[]")
        except (json.JSONDecodeError, TypeError):
            paper["tags"] = []
        papers.append(paper)

    all_tags: list[str] = []
    with get_db(db) as conn:
        tag_rows = conn.execute("SELECT DISTINCT tags FROM papers WHERE tags IS NOT NULL AND tags != ''").fetchall()
    for tr in tag_rows:
        try:
            all_tags.extend(json.loads(tr["tags"]))
        except (json.JSONDecodeError, TypeError):
            pass
    all_tags = sorted(set(all_tags))

    return templates.TemplateResponse(
        "paper_sieve/partials/paper_library.html",
        {"request": request, "papers": papers, "all_tags": all_tags, "filter_year": year, "filter_tag": tag},
    )


@router.get("/partials/search-results", response_class=HTMLResponse)
async def partial_search_results(request: Request, q: str = "") -> HTMLResponse:
    results: list[dict[str, Any]] = []

    if q.strip() and _DEPS_AVAILABLE:
        try:
            db = _db(request)
            query_vec = embed_query(q)
            collection = get_collection(_chroma_path(request))
            raw = chroma_search(collection, query_vec, n_results=10)

            for hit in raw:
                paper_info: dict[str, Any] = {}
                pid = hit.get("metadata", {}).get("paper_id")
                if pid:
                    with get_db(db) as conn:
                        row = conn.execute(
                            "SELECT id, title, authors, year, journal FROM papers WHERE id = ?",
                            (pid,),
                        ).fetchone()
                        if row:
                            paper_info = dict(row)
                            try:
                                paper_info["authors"] = json.loads(paper_info.get("authors") or "[]")
                            except (json.JSONDecodeError, TypeError):
                                paper_info["authors"] = []

                results.append({
                    "text": hit.get("text", ""),
                    "section": hit.get("metadata", {}).get("section_name", ""),
                    "distance": hit.get("distance"),
                    "relevance": round(1.0 - (hit.get("distance") or 0.0), 3),
                    "paper": paper_info,
                })
        except Exception as exc:
            logger.warning("Search partial error: %s", exc)

    return templates.TemplateResponse(
        "paper_sieve/partials/search_results.html",
        {"request": request, "results": results, "query": q},
    )


@router.get("/partials/qa-chat", response_class=HTMLResponse)
async def partial_qa_chat(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM queries ORDER BY queried_at DESC LIMIT 20"
        ).fetchall()

    messages: list[dict[str, Any]] = []
    for row in reversed(rows):
        entry = dict(row)
        try:
            entry["cited_chunks"] = json.loads(entry.get("cited_chunks") or "[]")
        except (json.JSONDecodeError, TypeError):
            entry["cited_chunks"] = []
        messages.append(entry)

    return templates.TemplateResponse(
        "paper_sieve/partials/qa_chat.html",
        {"request": request, "messages": messages},
    )


@router.get("/partials/knowledge-graph", response_class=HTMLResponse)
async def partial_knowledge_graph(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "paper_sieve/partials/knowledge_graph.html",
        {"request": request},
    )


@router.get("/partials/review-workflow", response_class=HTMLResponse)
async def partial_review_workflow(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "paper_sieve/partials/review_workflow.html",
        {"request": request},
    )
