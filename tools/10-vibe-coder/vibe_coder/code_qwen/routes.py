"""FastAPI routes for the CodeQwen feature module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from vibe_coder.code_qwen.features.debugger import BugDetector
from vibe_coder.code_qwen.features.docstring_writer import DocstringWriter
from vibe_coder.code_qwen.features.explainer import CodeExplainer
from vibe_coder.code_qwen.features.refactorer import RefactoringEngine
from vibe_coder.code_qwen.inference.chat_engine import ChatEngine
from vibe_coder.code_qwen.inference.completion_engine import CompletionEngine
from vibe_coder.code_qwen.inference.streaming import stream_response

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["CodeQwen"])


# -- Request / response models ------------------------------------------------

class CompletionRequest(BaseModel):
    prefix: str
    suffix: str = ""
    language: str = "python"
    max_tokens: int = Field(default=256, le=2048)


class ExplainRequest(BaseModel):
    code: str
    language: str = "python"
    output_language: str = "en"


class RefactorRequest(BaseModel):
    code: str
    language: str = "python"


class DebugRequest(BaseModel):
    code: str
    language: str = "python"


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    language: str = "python"


class DocstringRequest(BaseModel):
    code: str
    language: str = "python"
    style: str = "google"


# -- Dashboard page ------------------------------------------------------------

@router.get("/code-qwen/", response_class=HTMLResponse)
async def code_qwen_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "code_qwen/index.html",
        {
            "request": request,
            "config": request.app.state.config,
            "active_tab": "code-qwen",
        },
    )


# -- Completion (SSE streaming) -----------------------------------------------

@router.post("/api/code-qwen/complete")
async def complete(request: Request, body: CompletionRequest):
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    engine = CompletionEngine(llm, db_path)

    generator = engine.complete_stream(
        prefix=body.prefix,
        suffix=body.suffix,
        language=body.language,
        max_tokens=body.max_tokens,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="code-qwen",
        summary=f"Code completion requested ({body.language})",
    )

    return stream_response(generator)


# -- Explain -------------------------------------------------------------------

@router.post("/api/code-qwen/explain")
async def explain(request: Request, body: ExplainRequest) -> dict[str, Any]:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    explainer = CodeExplainer(llm, db_path)

    result = await explainer.explain(
        code=body.code,
        language=body.language,
        output_language=body.output_language,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="code-qwen",
        summary=f"Code explanation generated ({body.language})",
    )

    return {"explanation": result, "language": body.language}


# -- Refactor ------------------------------------------------------------------

@router.post("/api/code-qwen/refactor")
async def refactor(request: Request, body: RefactorRequest) -> dict[str, Any]:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    engine = RefactoringEngine(llm, db_path)

    suggestions = await engine.suggest(code=body.code, language=body.language)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="code-qwen",
        summary=f"Refactoring suggestions generated ({len(suggestions)} items)",
    )

    return {"suggestions": suggestions, "language": body.language}


# -- Debug ---------------------------------------------------------------------

@router.post("/api/code-qwen/debug")
async def debug(request: Request, body: DebugRequest) -> dict[str, Any]:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    detector = BugDetector(llm, db_path)

    issues = await detector.detect(code=body.code, language=body.language)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="code-qwen",
        summary=f"Bug detection completed ({len(issues)} issues found)",
    )

    return {"issues": issues, "language": body.language}


# -- Docstring -----------------------------------------------------------------

@router.post("/api/code-qwen/docstring")
async def generate_docstring(request: Request, body: DocstringRequest) -> dict[str, Any]:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    writer = DocstringWriter(llm, db_path)

    result = await writer.generate(
        code=body.code,
        language=body.language,
        style=body.style,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="code-qwen",
        summary=f"Docstring generated ({body.language}, {body.style} style)",
    )

    return {"docstring": result, "language": body.language, "style": body.style}


# -- Chat (SSE streaming) -----------------------------------------------------

@router.post("/api/code-qwen/chat")
async def chat(request: Request, body: ChatRequest):
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["code_qwen"]
    engine = ChatEngine(llm, db_path)

    generator = engine.chat_stream(
        message=body.message,
        session_id=body.session_id,
        language=body.language,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="code-qwen",
        summary="Chat message received",
    )

    return stream_response(generator)


# -- Stats ---------------------------------------------------------------------

@router.get("/api/code-qwen/stats")
async def stats(request: Request) -> dict[str, Any]:
    db_path = request.app.state.db_paths["code_qwen"]
    with get_db(db_path) as conn:
        usage_rows = conn.execute(
            """SELECT feature, date, request_count, avg_latency_ms, avg_tokens
               FROM usage_stats ORDER BY date DESC LIMIT 100"""
        ).fetchall()

        totals = conn.execute(
            """SELECT feature,
                      COUNT(*) as total_requests,
                      ROUND(AVG(latency_ms), 1) as avg_latency,
                      SUM(tokens_generated) as total_tokens
               FROM conversations
               GROUP BY feature"""
        ).fetchall()

    return {
        "daily": [dict(r) for r in usage_rows],
        "totals": [dict(r) for r in totals],
    }


# -- History -------------------------------------------------------------------

@router.get("/api/code-qwen/history")
async def history(
    request: Request,
    session_id: str = "default",
    feature: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    db_path = request.app.state.db_paths["code_qwen"]
    with get_db(db_path) as conn:
        conditions = []
        params: list[Any] = []

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if feature:
            conditions.append("feature = ?")
            params.append(feature)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM conversations {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
            params,
        ).fetchall()

    return {"conversations": [dict(r) for r in rows]}
