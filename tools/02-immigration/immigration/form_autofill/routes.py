"""FormAutoFill FastAPI routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/form-autofill", tags=["FormAutoFill"])

templates = Jinja2Templates(directory="immigration/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "form-autofill", **extra}


def _output_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "documents" / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def form_autofill_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["form_autofill"]

    with get_db(db) as conn:
        clients = [dict(r) for r in conn.execute(
            "SELECT * FROM clients ORDER BY created_at DESC"
        ).fetchall()]
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        draft_apps = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE status = 'draft'"
        ).fetchone()[0]
        templates_count = conn.execute(
            "SELECT COUNT(*) FROM form_templates WHERE is_current = 1"
        ).fetchone()[0]
        recent_apps = [dict(r) for r in conn.execute(
            "SELECT a.*, c.name_en as client_name FROM applications a "
            "LEFT JOIN clients c ON a.client_id = c.id "
            "ORDER BY a.created_at DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "form_autofill/index.html",
        _ctx(
            request,
            clients=clients,
            total_apps=total_apps,
            draft_apps=draft_apps,
            templates_count=templates_count,
            recent_apps=recent_apps,
        ),
    )


# ── Clients ────────────────────────────────────────────────────────────────

@router.get("/clients")
async def list_clients(request: Request) -> list[dict]:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM clients ORDER BY name_en").fetchall()
    return [dict(r) for r in rows]


@router.get("/clients/{client_id}")
async def get_client(request: Request, client_id: int) -> dict:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    return dict(row)


# ── Generate form ──────────────────────────────────────────────────────────

class GenerateFormRequest(BaseModel):
    client_id: int
    scheme: str
    form_type: str
    field_overrides: dict[str, Any] | None = None


@router.post("/generate")
async def generate_form(request: Request, body: GenerateFormRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["form_autofill"]

    with get_db(db) as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (body.client_id,)
        ).fetchone()
    if not client_row:
        raise HTTPException(status_code=404, detail="Client not found")

    client = dict(client_row)

    from immigration.form_autofill.engine.mapper import map_client_to_fields
    from immigration.form_autofill.engine.validator import validate_fields
    from immigration.form_autofill.engine.overlay import generate_pdf

    field_values = map_client_to_fields(client, body.form_type)
    if body.field_overrides:
        field_values.update(body.field_overrides)

    validation = validate_fields(body.form_type, field_values)
    if validation["errors"]:
        return {"status": "validation_error", "errors": validation["errors"]}

    output_dir = _output_dir(request)
    pdf_path = generate_pdf(body.form_type, field_values, output_dir)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO applications
               (client_id, scheme, form_type, field_values, generated_pdf_path, status)
               VALUES (?,?,?,?,?,?)""",
            (body.client_id, body.scheme, body.form_type,
             json.dumps(field_values), str(pdf_path), "generated"),
        )
        app_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="form-autofill",
        summary=f"Form {body.form_type} generated for {client['name_en']} ({body.scheme})",
    )

    return {
        "application_id": app_id,
        "pdf_path": str(pdf_path),
        "validation": validation,
        "status": "generated",
    }


# ── Preview ────────────────────────────────────────────────────────────────

@router.get("/preview/{app_id}")
async def preview_form(request: Request, app_id: int) -> FileResponse:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = dict(row)
    pdf_path = Path(app_data.get("generated_pdf_path", ""))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(path=str(pdf_path), filename=pdf_path.name, media_type="application/pdf")


# ── Validate ───────────────────────────────────────────────────────────────

@router.get("/validate/{app_id}")
async def validate_application(request: Request, app_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = dict(row)
    field_values = json.loads(app_data.get("field_values", "{}"))

    from immigration.form_autofill.engine.validator import validate_fields
    validation = validate_fields(app_data["form_type"], field_values)

    return {"application_id": app_id, "validation": validation}


# ── Checklist ──────────────────────────────────────────────────────────────

@router.get("/checklist/{app_id}")
async def get_checklist(request: Request, app_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["form_autofill"]
    ocr_db = request.app.state.db_paths["visa_doc_ocr"]

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")

    app_data = dict(row)

    from immigration.form_autofill.tracking.checklist import generate_checklist
    checklist = generate_checklist(app_data["scheme"], app_data["client_id"], ocr_db)

    return {"application_id": app_id, "checklist": checklist}


# ── Batch generate ─────────────────────────────────────────────────────────

class BatchRequest(BaseModel):
    client_ids: list[int]
    scheme: str
    form_type: str


@router.post("/batch")
async def batch_generate(request: Request, body: BatchRequest) -> dict[str, Any]:
    results = []
    for cid in body.client_ids:
        try:
            gen_req = GenerateFormRequest(
                client_id=cid, scheme=body.scheme, form_type=body.form_type,
            )
            result = await generate_form(request, gen_req)
            results.append({"client_id": cid, **result})
        except Exception as e:
            results.append({"client_id": cid, "status": "error", "error": str(e)})

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="form-autofill",
        summary=f"Batch generation: {len(results)} forms for {body.scheme}/{body.form_type}",
    )

    return {"results": results, "total": len(results)}


# ── Template version status ────────────────────────────────────────────────

@router.get("/templates/status")
async def template_status(request: Request) -> list[dict]:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM form_templates WHERE is_current = 1 ORDER BY form_type"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/client-card/partial", response_class=HTMLResponse)
async def client_card_partial(request: Request, client_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Client not found")
    client = dict(row)
    return templates.TemplateResponse(
        "form_autofill/partials/client_card.html",
        {"request": request, "client": client},
    )


@router.get("/field-editor/partial", response_class=HTMLResponse)
async def field_editor_partial(request: Request, form_type: str, client_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["form_autofill"]
    with get_db(db) as conn:
        client_row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()

    client = dict(client_row) if client_row else {}

    from immigration.form_autofill.engine.mapper import map_client_to_fields
    from immigration.form_autofill.engine.validator import validate_fields

    field_values = map_client_to_fields(client, form_type)
    validation = validate_fields(form_type, field_values)

    fields_with_meta = []
    from immigration.form_autofill.forms.base import get_form_definition
    form_def = get_form_definition(form_type)
    for field in form_def.get_field_list():
        fname = field["name"]
        fields_with_meta.append({
            **field,
            "value": field_values.get(fname, ""),
            "valid": fname not in [e["field"] for e in validation.get("errors", [])],
            "char_count": len(str(field_values.get(fname, ""))),
        })

    return templates.TemplateResponse(
        "form_autofill/partials/field_editor.html",
        {"request": request, "fields": fields_with_meta, "form_type": form_type},
    )
