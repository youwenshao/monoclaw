"""InsuranceAgent FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db

from medical_dental.insurance_agent.claims.claim_tracker import ClaimTracker
from medical_dental.insurance_agent.estimation.copay_calculator import CopayCalculator
from medical_dental.insurance_agent.estimation.fee_schedule import FeeSchedule
from medical_dental.insurance_agent.estimation.ha_rate_lookup import compare_rates
from medical_dental.insurance_agent.preauth.form_generator import PreauthFormGenerator
from medical_dental.insurance_agent.preauth.submission_handler import PreauthTracker
from medical_dental.insurance_agent.verification.axa_connector import AxaConnector
from medical_dental.insurance_agent.verification.batch_verify import batch_verify_next_day
from medical_dental.insurance_agent.verification.bupa_connector import BupaConnector
from medical_dental.insurance_agent.verification.cigna_connector import CignaConnector

router = APIRouter(prefix="/insurance-agent", tags=["InsuranceAgent"])

templates = Jinja2Templates(directory="medical_dental/dashboard/templates")

_fee_schedule = FeeSchedule()
_copay_calc = CopayCalculator()
_form_gen = PreauthFormGenerator()

_connectors = {
    "bupa": BupaConnector(),
    "axa": AxaConnector(),
    "cigna": CignaConnector(),
}


# ── Request models ────────────────────────────────────────────────────────


class VerifyRequest(BaseModel):
    policy_id: int
    insurer: str = ""
    policy_number: str = ""
    member_id: str = ""


class CopayEstimateRequest(BaseModel):
    procedure: str
    clinic_fee: float
    policy_id: int | None = None
    coverage_override: dict[str, Any] | None = None


class CreateClaimRequest(BaseModel):
    patient_id: int
    policy_id: int
    procedure_code: str = ""
    description: str = ""
    billed_amount: float = 0.0
    claim_date: str = ""


class UpdateClaimRequest(BaseModel):
    status: str | None = None
    approved_amount: float | None = None
    patient_copay: float | None = None
    insurer_reference: str | None = None


class CreatePreauthRequest(BaseModel):
    patient_id: int
    policy_id: int
    procedure_description: str = ""
    estimated_cost: float = 0.0
    notes: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────


def _db(request: Request) -> Path:
    return request.app.state.db_paths["insurance_agent"]


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "insurance-agent",
        **extra,
    }


# ── Dashboard page ────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def insurance_agent_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        patients = [dict(r) for r in conn.execute(
            "SELECT * FROM patients ORDER BY name_en"
        ).fetchall()]
        total_policies = conn.execute("SELECT COUNT(*) FROM insurance_policies").fetchone()[0]
        active_policies = conn.execute(
            "SELECT COUNT(*) FROM insurance_policies WHERE status = 'active'"
        ).fetchone()[0]
        pending_claims = conn.execute(
            "SELECT COUNT(*) FROM claims WHERE status IN ('pending', 'submitted')"
        ).fetchone()[0]
        pending_preauths = conn.execute(
            "SELECT COUNT(*) FROM preauthorizations WHERE status IN ('draft', 'submitted')"
        ).fetchone()[0]
        recent_claims = [dict(r) for r in conn.execute(
            "SELECT c.*, p.name_en as patient_name FROM claims c "
            "LEFT JOIN patients p ON c.patient_id = p.id "
            "ORDER BY c.created_at DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "insurance_agent/index.html",
        _ctx(
            request,
            patients=patients,
            total_policies=total_policies,
            active_policies=active_policies,
            pending_claims=pending_claims,
            pending_preauths=pending_preauths,
            recent_claims=recent_claims,
        ),
    )


# ── Patients ──────────────────────────────────────────────────────────────


@router.get("/api/patients")
async def list_patients(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY name_en").fetchall()
    return [dict(r) for r in rows]


@router.get("/api/patients/{patient_id}/policies")
async def get_patient_policies(request: Request, patient_id: int) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        patient = conn.execute("SELECT id FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        policies = [dict(r) for r in conn.execute(
            "SELECT * FROM insurance_policies WHERE patient_id = ? ORDER BY effective_date DESC",
            (patient_id,),
        ).fetchall()]

        for pol in policies:
            coverage = [dict(r) for r in conn.execute(
                "SELECT * FROM coverage_details WHERE policy_id = ?",
                (pol["id"],),
            ).fetchall()]
            pol["coverage"] = coverage

    return policies


# ── Verification ──────────────────────────────────────────────────────────


@router.post("/api/verify")
async def verify_coverage(request: Request, body: VerifyRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM insurance_policies WHERE id = ?", (body.policy_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found")
        policy = dict(row)

    insurer = (body.insurer or policy.get("insurer", "")).lower()
    policy_number = body.policy_number or policy.get("policy_number", "")
    member_id = body.member_id or policy.get("member_id", "")

    connector = _connectors.get(insurer)
    if not connector:
        raise HTTPException(status_code=400, detail=f"Unsupported insurer: {insurer}")

    result = connector.verify_coverage(policy_number, member_id)

    if result.get("status") == "active":
        with get_db(db) as conn:
            conn.execute(
                "UPDATE insurance_policies SET last_verified = CURRENT_TIMESTAMP, "
                "remaining_balance = ?, status = 'active' WHERE id = ?",
                (result.get("remaining_balance", policy.get("remaining_balance")), body.policy_id),
            )
    elif result.get("status") in ("expired", "suspended"):
        with get_db(db) as conn:
            conn.execute(
                "UPDATE insurance_policies SET last_verified = CURRENT_TIMESTAMP, "
                "status = ? WHERE id = ?",
                (result["status"], body.policy_id),
            )

    return {"policy_id": body.policy_id, "insurer": insurer, **result}


# ── Co-pay estimation ────────────────────────────────────────────────────


@router.post("/api/copay-estimate")
async def estimate_copay(request: Request, body: CopayEstimateRequest) -> dict[str, Any]:
    clinic_fee = body.clinic_fee
    if clinic_fee <= 0:
        default = _fee_schedule.get_default_amount(body.procedure)
        if default > 0:
            clinic_fee = default
        else:
            raise HTTPException(status_code=400, detail="clinic_fee must be positive")

    if body.coverage_override:
        coverage = body.coverage_override
    elif body.policy_id:
        db = _db(request)
        with get_db(db) as conn:
            policy_row = conn.execute(
                "SELECT * FROM insurance_policies WHERE id = ?", (body.policy_id,)
            ).fetchone()
            if not policy_row:
                raise HTTPException(status_code=404, detail="Policy not found")
            policy = dict(policy_row)

            cov_row = conn.execute(
                "SELECT * FROM coverage_details WHERE policy_id = ? AND benefit_category = ?",
                (body.policy_id, body.procedure),
            ).fetchone()
            if not cov_row:
                cov_row = conn.execute(
                    "SELECT * FROM coverage_details WHERE policy_id = ? LIMIT 1",
                    (body.policy_id,),
                ).fetchone()

        if cov_row:
            coverage = dict(cov_row)
            coverage["annual_remaining"] = policy.get("remaining_balance")
        else:
            coverage = {"copay_percentage": 0, "copay_fixed": 0, "deductible": 0, "sub_limit": 0}
    else:
        coverage = {"copay_percentage": 0, "copay_fixed": 0, "deductible": 0, "sub_limit": 0}

    result = _copay_calc.estimate_from_db_coverage(
        body.procedure, clinic_fee, coverage,
        policy_remaining=coverage.get("annual_remaining"),
    )

    ha_comparison = compare_rates(body.procedure, clinic_fee)
    result["ha_comparison"] = ha_comparison

    return result


# ── Claims ────────────────────────────────────────────────────────────────


@router.get("/api/claims")
async def list_claims(request: Request, status: str | None = None) -> list[dict[str, Any]]:
    db = _db(request)
    tracker = ClaimTracker(db)
    return tracker.list_all(status=status)


@router.post("/api/claims")
async def create_claim(request: Request, body: CreateClaimRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        patient = conn.execute("SELECT id FROM patients WHERE id = ?", (body.patient_id,)).fetchone()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        policy = conn.execute("SELECT id FROM insurance_policies WHERE id = ?", (body.policy_id,)).fetchone()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

    tracker = ClaimTracker(db)
    claim_id = tracker.create_claim(body.model_dump())
    claim = tracker.get_by_id(claim_id)
    return {"claim_id": claim_id, "claim": claim}


@router.patch("/api/claims/{claim_id}")
async def update_claim(request: Request, claim_id: int, body: UpdateClaimRequest) -> dict[str, Any]:
    db = _db(request)
    tracker = ClaimTracker(db)

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = tracker.update_claim(claim_id, **updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return updated


# ── Pre-authorizations ────────────────────────────────────────────────────


@router.get("/api/preauth")
async def list_preauths(request: Request, status: str | None = None) -> list[dict[str, Any]]:
    db = _db(request)
    tracker = PreauthTracker(db)
    return tracker.list_all(status=status)


@router.post("/api/preauth")
async def create_preauth(request: Request, body: CreatePreauthRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        patient_row = conn.execute("SELECT * FROM patients WHERE id = ?", (body.patient_id,)).fetchone()
        if not patient_row:
            raise HTTPException(status_code=404, detail="Patient not found")
        policy_row = conn.execute(
            "SELECT * FROM insurance_policies WHERE id = ?", (body.policy_id,)
        ).fetchone()
        if not policy_row:
            raise HTTPException(status_code=404, detail="Policy not found")

    patient = dict(patient_row)
    policy = dict(policy_row)

    config = request.app.state.config
    clinic_info = {
        "clinic_name": config.extra.get("clinic_name", ""),
        "clinic_address": config.extra.get("clinic_address", ""),
        "clinic_phone": config.extra.get("clinic_phone", ""),
        "hkma_registration": config.extra.get("hkma_registration", ""),
    }

    form_result = _form_gen.generate(
        patient, policy,
        body.procedure_description,
        body.estimated_cost,
        clinic_info=clinic_info,
    )

    tracker = PreauthTracker(db)
    preauth_id = tracker.create_preauth({
        "patient_id": body.patient_id,
        "policy_id": body.policy_id,
        "procedure_description": body.procedure_description,
        "estimated_cost": body.estimated_cost,
        "notes": body.notes,
    })

    preauth = tracker.get_by_id(preauth_id)
    return {
        "preauth_id": preauth_id,
        "preauth": preauth,
        "form_data": form_result["form_data"],
        "pdf_path": form_result["pdf_path"],
    }


# ── Batch verification ────────────────────────────────────────────────────


@router.post("/api/batch-verify")
async def batch_verify(request: Request) -> dict[str, Any]:
    insurance_db = _db(request)
    scheduler_db = request.app.state.db_paths.get("clinic_scheduler")

    if not scheduler_db:
        raise HTTPException(status_code=400, detail="Clinic scheduler database not configured")

    issues = batch_verify_next_day(scheduler_db, insurance_db, _connectors)

    return {
        "date_checked": "tomorrow",
        "total_issues": len(issues),
        "issues": issues,
    }
