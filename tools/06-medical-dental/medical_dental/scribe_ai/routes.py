"""ScribeAI FastAPI routes — transcription, structuring, and note management."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from medical_dental.scribe_ai.transcription.whisper_engine import WhisperEngine
from medical_dental.scribe_ai.transcription.language_detect import detect_language, post_process_cantonese
from medical_dental.scribe_ai.structuring.soap_generator import SoapGenerator
from medical_dental.scribe_ai.structuring.entity_extractor import EntityExtractor
from medical_dental.scribe_ai.structuring.icd_coder import IcdCoder
from medical_dental.scribe_ai.records.note_manager import NoteManager
from medical_dental.scribe_ai.records.template_engine import TemplateEngine
from medical_dental.scribe_ai.records.finalization import Finalization

router = APIRouter(prefix="/scribe-ai", tags=["ScribeAI"])

templates = Jinja2Templates(directory="medical_dental/dashboard/templates")

_whisper = WhisperEngine()
_soap_gen = SoapGenerator()
_entity_ext = EntityExtractor()
_icd_coder = IcdCoder()
_note_mgr = NoteManager()
_template_eng = TemplateEngine()
_finalizer = Finalization()


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "scribe-ai",
        **extra,
    }


def _db(request: Request) -> Path:
    return request.app.state.db_paths["scribe_ai"]


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def scribe_ai_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        patients = [dict(r) for r in conn.execute(
            "SELECT * FROM patients ORDER BY name_en"
        ).fetchall()]
        total = conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
        drafts = conn.execute(
            "SELECT COUNT(*) FROM consultations WHERE status = 'draft'"
        ).fetchone()[0]
        finalized = conn.execute(
            "SELECT COUNT(*) FROM consultations WHERE status = 'finalized'"
        ).fetchone()[0]
        recent = [dict(r) for r in conn.execute(
            "SELECT c.*, p.name_en AS patient_name FROM consultations c "
            "LEFT JOIN patients p ON c.patient_id = p.id "
            "ORDER BY c.consultation_date DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "scribe_ai/index.html",
        _ctx(
            request,
            patients=patients,
            total_consultations=total,
            draft_count=drafts,
            finalized_count=finalized,
            recent_consultations=recent,
        ),
    )


# ── Patients API ───────────────────────────────────────────────────────────

@router.get("/api/patients")
async def list_patients(request: Request) -> list[dict[str, Any]]:
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY name_en"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Consultations API ──────────────────────────────────────────────────────

@router.get("/api/consultations")
async def list_consultations(
    request: Request,
    patient_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return _note_mgr.list_consultations(
        _db(request),
        patient_id=patient_id,
        status=status,
    )


@router.get("/api/consultations/{consultation_id}")
async def get_consultation(request: Request, consultation_id: int) -> dict[str, Any]:
    note = _note_mgr.get_note(_db(request), consultation_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return note


@router.post("/api/consultations")
async def create_consultation(request: Request) -> dict[str, Any]:
    body = await request.json()
    patient_id = body.get("patient_id")
    doctor = body.get("doctor", "")
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id is required")

    soap_data = {
        "subjective": body.get("soap_subjective", ""),
        "objective": body.get("soap_objective", ""),
        "assessment": body.get("soap_assessment", ""),
        "plan": body.get("soap_plan", ""),
    }

    consultation_id = _note_mgr.create_note(
        _db(request),
        patient_id=patient_id,
        doctor=doctor,
        soap_data=soap_data,
        raw_transcription=body.get("raw_transcription", ""),
        icd10_codes=body.get("icd10_codes"),
        medications=body.get("medications_prescribed"),
        follow_up_date=body.get("follow_up_date"),
        status=body.get("status", "draft"),
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="scribe-ai",
        summary=f"Consultation #{consultation_id} created for patient {patient_id}",
    )

    return {"consultation_id": consultation_id, "status": "created"}


@router.patch("/api/consultations/{consultation_id}")
async def update_consultation(request: Request, consultation_id: int) -> dict[str, Any]:
    body = await request.json()

    field_map: dict[str, str] = {
        "soap_subjective": "soap_subjective",
        "soap_objective": "soap_objective",
        "soap_assessment": "soap_assessment",
        "soap_plan": "soap_plan",
        "raw_transcription": "raw_transcription",
        "icd10_codes": "icd10_codes",
        "medications_prescribed": "medications_prescribed",
        "follow_up_date": "follow_up_date",
        "status": "status",
        "doctor": "doctor",
    }

    updates = {field_map[k]: v for k, v in body.items() if k in field_map}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    success = _note_mgr.update_note(_db(request), consultation_id, **updates)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Consultation not found or is finalized",
        )

    return {"consultation_id": consultation_id, "status": "updated"}


# ── Finalization & Amendment ───────────────────────────────────────────────

@router.post("/api/consultations/{consultation_id}/finalize")
async def finalize_consultation(request: Request, consultation_id: int) -> dict[str, Any]:
    body = await request.json()
    finalized_by = body.get("finalized_by", "")
    if not finalized_by:
        raise HTTPException(status_code=400, detail="finalized_by is required")

    success = _finalizer.finalize_note(_db(request), consultation_id, finalized_by)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Consultation not found or already finalized",
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="scribe-ai",
        summary=f"Consultation #{consultation_id} finalized by {finalized_by}",
    )

    return {"consultation_id": consultation_id, "status": "finalized"}


@router.post("/api/consultations/{consultation_id}/amend")
async def amend_consultation(request: Request, consultation_id: int) -> dict[str, Any]:
    body = await request.json()
    amended_by = body.get("amended_by", "")
    if not amended_by:
        raise HTTPException(status_code=400, detail="amended_by is required")

    soap_data = {
        "subjective": body.get("soap_subjective", ""),
        "objective": body.get("soap_objective", ""),
        "assessment": body.get("soap_assessment", ""),
        "plan": body.get("soap_plan", ""),
    }

    try:
        new_id = _finalizer.amend_note(
            _db(request),
            consultation_id,
            amended_by,
            soap_data,
            icd10_codes=body.get("icd10_codes"),
            medications=body.get("medications_prescribed"),
            follow_up_date=body.get("follow_up_date"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="scribe-ai",
        summary=f"Amendment #{new_id} created for consultation #{consultation_id} by {amended_by}",
        requires_human_action=True,
    )

    return {"amendment_id": new_id, "original_id": consultation_id, "status": "draft"}


# ── Transcription API ─────────────────────────────────────────────────────

@router.post("/api/transcribe")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        model_size = request.app.state.config.extra.get("whisper_model", "small")
        _whisper.load_model(model_size)
        result = _whisper.transcribe(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    text = result["text"]
    detected_lang = detect_language(text)

    if detected_lang in ("zh", "mixed"):
        text = post_process_cantonese(text)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="scribe-ai",
        summary=f"Audio transcribed ({detected_lang}): {len(text)} chars",
    )

    return {
        "text": text,
        "language": detected_lang,
        "raw_language": result.get("language", ""),
    }


# ── Structuring API ───────────────────────────────────────────────────────

@router.post("/api/structure")
async def structure_text(request: Request) -> dict[str, Any]:
    body = await request.json()
    text = body.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    llm = request.app.state.llm

    soap = await _soap_gen.generate(text, llm)
    entities = await _entity_ext.extract(text, llm)
    icd_suggestions = _icd_coder.suggest_codes(soap.get("assessment", text))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="scribe-ai",
        summary=f"Text structured: {len(entities.get('diagnoses', []))} diagnoses, {len(icd_suggestions)} ICD codes",
    )

    return {
        "soap": soap,
        "entities": entities,
        "icd10_suggestions": icd_suggestions,
    }


# ── Templates API ─────────────────────────────────────────────────────────

@router.get("/api/templates")
async def list_templates(
    request: Request,
    category: str | None = None,
) -> list[dict[str, Any]]:
    return _template_eng.get_templates(_db(request), category=category)


@router.post("/api/templates/apply")
async def apply_template(request: Request) -> dict[str, Any]:
    body = await request.json()
    template_id = body.get("template_id")
    if template_id is None:
        raise HTTPException(status_code=400, detail="template_id is required")

    template = _template_eng.get_template(_db(request), template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    overrides = body.get("overrides")
    result = _template_eng.apply_template(template, overrides)

    return {
        "template_id": template_id,
        "template_name": template.get("name", ""),
        "soap": result,
        "common_icd10": template.get("common_icd10", []),
        "common_medications": template.get("common_medications", []),
    }
