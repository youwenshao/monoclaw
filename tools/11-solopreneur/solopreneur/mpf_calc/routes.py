"""MPFCalc FastAPI routes — employee management, contribution calculation,
remittance generation, compliance dashboard, and what-if modelling.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from solopreneur.mpf_calc.calculation.employee_classifier import (
    classify_employee,
    get_mpf_enrollment_date,
    is_within_60_day_rule,
)
from solopreneur.mpf_calc.calculation.mpf_engine import (
    calculate_mandatory_contribution,
    calculate_monthly_all,
)
from solopreneur.mpf_calc.payroll.employee_manager import (
    create_employee,
    deactivate_employee,
    list_employees,
    update_employee,
)
from solopreneur.mpf_calc.reporting.annual_summary import generate_annual_summary
from solopreneur.mpf_calc.reporting.compliance_report import (
    check_late_contributions,
    get_compliance_status,
    get_contribution_day_countdown,
)
from solopreneur.mpf_calc.reporting.pdf_export import export_remittance_pdf
from solopreneur.mpf_calc.reporting.remittance_generator import generate_remittance

router = APIRouter(prefix="/mpf-calc", tags=["MPFCalc"])

templates = Jinja2Templates(directory="solopreneur/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "mpf-calc",
        **extra,
    }


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["mpf"])


def _mona(request: Request) -> str:
    return str(request.app.state.db_paths["mona_events"])


# ── Main page ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def mpf_calc_page(request: Request) -> HTMLResponse:
    db = _db(request)
    employees = list_employees(db)
    compliance = get_compliance_status(db)
    countdown = get_contribution_day_countdown()

    total_monthly = Decimal("0")
    with get_db(db) as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_contribution), 0) AS total
               FROM monthly_contributions
               WHERE strftime('%%Y-%%m', contribution_month) = ?""",
            (date.today().strftime("%Y-%m"),),
        ).fetchone()
        total_monthly = row["total"]

    return templates.TemplateResponse(
        "mpf_calc/index.html",
        _ctx(
            request,
            employees=employees,
            compliance=compliance,
            countdown=countdown,
            total_monthly=total_monthly,
            employee_count=len(employees),
        ),
    )


# ── Partials ───────────────────────────────────────────────────────────────

@router.get("/partials/employee-table", response_class=HTMLResponse)
async def employee_table_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    employees = list_employees(db)
    today = date.today()
    for emp in employees:
        sd = emp.get("start_date")
        if sd:
            start = date.fromisoformat(sd) if isinstance(sd, str) else sd
            emp["within_60_day"] = is_within_60_day_rule(start, today)
            emp["enrollment_date"] = get_mpf_enrollment_date(start).isoformat()
            classification = classify_employee(
                emp.get("employment_type", "full_time"), start, today
            )
            emp["mpf_eligible"] = classification["mpf_eligible"]
            emp["eligibility_reason"] = classification["reason"]
        else:
            emp["within_60_day"] = False
            emp["enrollment_date"] = ""
            emp["mpf_eligible"] = True
            emp["eligibility_reason"] = ""

    return templates.TemplateResponse(
        "mpf_calc/partials/employee_table.html",
        _ctx(request, employees=employees),
    )


@router.get("/partials/monthly-calculator", response_class=HTMLResponse)
async def monthly_calculator_partial(
    request: Request, month: str | None = None
) -> HTMLResponse:
    db = _db(request)
    if month is None:
        month = date.today().strftime("%Y-%m")

    contributions = calculate_monthly_all(db, month)

    grand_employer = sum(c["employer_mandatory"] for c in contributions)
    grand_employee = sum(c["employee_mandatory"] for c in contributions)
    grand_total = sum(c["total_contribution"] for c in contributions)

    return templates.TemplateResponse(
        "mpf_calc/partials/monthly_calculator.html",
        _ctx(
            request,
            month=month,
            contributions=contributions,
            grand_employer=grand_employer,
            grand_employee=grand_employee,
            grand_total=grand_total,
        ),
    )


@router.get("/partials/remittance-preview", response_class=HTMLResponse)
async def remittance_preview_partial(
    request: Request, month: str | None = None
) -> HTMLResponse:
    db = _db(request)
    if month is None:
        month = date.today().strftime("%Y-%m")

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT mc.*, e.name_en, e.name_tc, e.mpf_member_number
               FROM monthly_contributions mc
               JOIN employees e ON e.id = mc.employee_id
               WHERE strftime('%%Y-%%m', mc.contribution_month) = ?
               ORDER BY e.name_en""",
            (month,),
        ).fetchall()
        items = [dict(r) for r in rows]

    total_employer = sum(i.get("employer_mandatory", 0) for i in items)
    total_employee = sum(i.get("employee_mandatory", 0) for i in items)
    total = total_employer + total_employee

    trustee = request.app.state.config.extra.get("mpf_trustee", "")

    return templates.TemplateResponse(
        "mpf_calc/partials/remittance_preview.html",
        _ctx(
            request,
            month=month,
            items=items,
            total_employer=total_employer,
            total_employee=total_employee,
            total=total,
            trustee=trustee,
        ),
    )


@router.get("/partials/compliance-dashboard", response_class=HTMLResponse)
async def compliance_dashboard_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    compliance = get_compliance_status(db)
    late = check_late_contributions(db)
    return templates.TemplateResponse(
        "mpf_calc/partials/compliance_dashboard.html",
        _ctx(request, compliance=compliance, late_contributions=late),
    )


@router.get("/partials/whatif-calculator", response_class=HTMLResponse)
async def whatif_calculator_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "mpf_calc/partials/whatif_calculator.html",
        _ctx(request),
    )


# ── Employee CRUD ──────────────────────────────────────────────────────────

@router.post("/employees", response_class=HTMLResponse)
async def add_employee(
    request: Request,
    name_en: str = Form(...),
    name_tc: str = Form(""),
    hkid_last4: str = Form(""),
    employment_type: str = Form("full_time"),
    start_date: str = Form(""),
    monthly_salary: float = Form(0),
    mpf_scheme: str = Form(""),
    mpf_member_number: str = Form(""),
) -> HTMLResponse:
    db = _db(request)
    data = {
        "name_en": name_en,
        "name_tc": name_tc,
        "hkid_last4": hkid_last4,
        "employment_type": employment_type,
        "start_date": start_date or date.today().isoformat(),
        "monthly_salary": monthly_salary,
        "mpf_scheme": mpf_scheme,
        "mpf_member_number": mpf_member_number,
    }
    emp = create_employee(db, data)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="mpf_calc",
        summary=f"Employee added: {emp['name_en']}",
    )

    employees = list_employees(db)
    today = date.today()
    for e in employees:
        sd = e.get("start_date")
        if sd:
            start = date.fromisoformat(sd) if isinstance(sd, str) else sd
            e["within_60_day"] = is_within_60_day_rule(start, today)
            e["enrollment_date"] = get_mpf_enrollment_date(start).isoformat()
            cl = classify_employee(e.get("employment_type", "full_time"), start, today)
            e["mpf_eligible"] = cl["mpf_eligible"]
            e["eligibility_reason"] = cl["reason"]
        else:
            e["within_60_day"] = False
            e["enrollment_date"] = ""
            e["mpf_eligible"] = True
            e["eligibility_reason"] = ""

    return templates.TemplateResponse(
        "mpf_calc/partials/employee_table.html",
        _ctx(request, employees=employees),
    )


@router.put("/employees/{employee_id}", response_class=HTMLResponse)
async def edit_employee(request: Request, employee_id: int) -> HTMLResponse:
    db = _db(request)
    form = await request.form()
    data = {k: v for k, v in form.items()}
    if "monthly_salary" in data:
        data["monthly_salary"] = float(data["monthly_salary"])

    update_employee(db, employee_id, data)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="mpf_calc",
        summary=f"Employee #{employee_id} updated",
    )

    employees = list_employees(db)
    today = date.today()
    for e in employees:
        sd = e.get("start_date")
        if sd:
            start = date.fromisoformat(sd) if isinstance(sd, str) else sd
            e["within_60_day"] = is_within_60_day_rule(start, today)
            e["enrollment_date"] = get_mpf_enrollment_date(start).isoformat()
            cl = classify_employee(e.get("employment_type", "full_time"), start, today)
            e["mpf_eligible"] = cl["mpf_eligible"]
            e["eligibility_reason"] = cl["reason"]
        else:
            e["within_60_day"] = False
            e["enrollment_date"] = ""
            e["mpf_eligible"] = True
            e["eligibility_reason"] = ""

    return templates.TemplateResponse(
        "mpf_calc/partials/employee_table.html",
        _ctx(request, employees=employees),
    )


# ── Calculations ───────────────────────────────────────────────────────────

@router.post("/calculate/{month}", response_class=HTMLResponse)
async def calculate_month(request: Request, month: str) -> HTMLResponse:
    db = _db(request)
    contributions = calculate_monthly_all(db, month)

    with get_db(db) as conn:
        for c in contributions:
            conn.execute(
                """INSERT OR REPLACE INTO monthly_contributions
                   (employee_id, contribution_month, relevant_income,
                    employer_mandatory, employee_mandatory, total_contribution,
                    payment_status)
                   VALUES (?, ?, ?, ?, ?, ?, 'calculated')""",
                (
                    c["employee_id"],
                    f"{month}-01",
                    c["relevant_income"],
                    c["employer_mandatory"],
                    c["employee_mandatory"],
                    c["total_contribution"],
                ),
            )

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="mpf_calc",
        summary=f"MPF calculated for {month}: {len(contributions)} employees",
    )

    grand_employer = sum(c["employer_mandatory"] for c in contributions)
    grand_employee = sum(c["employee_mandatory"] for c in contributions)
    grand_total = sum(c["total_contribution"] for c in contributions)

    return templates.TemplateResponse(
        "mpf_calc/partials/monthly_calculator.html",
        _ctx(
            request,
            month=month,
            contributions=contributions,
            grand_employer=grand_employer,
            grand_employee=grand_employee,
            grand_total=grand_total,
        ),
    )


# ── Remittance ─────────────────────────────────────────────────────────────

@router.post("/remittance/{month}")
async def create_remittance(request: Request, month: str) -> dict[str, Any]:
    db = _db(request)
    trustee = request.app.state.config.extra.get("mpf_trustee", "")
    result = generate_remittance(db, month, trustee)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="mpf_calc",
        summary=f"Remittance statement generated for {month}",
        details=f"Total: ${result['total_amount']:,.2f} for {result['employee_count']} employees",
    )

    return result


@router.get("/remittance/{month}/download")
async def download_remittance(request: Request, month: str) -> FileResponse:
    db = _db(request)
    trustee = request.app.state.config.extra.get("mpf_trustee", "")
    remittance = generate_remittance(db, month, trustee)

    workspace: Path = request.app.state.workspace
    reports_dir = workspace / "mpf" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = reports_dir / f"remittance_{month}.pdf"

    export_remittance_pdf(remittance, pdf_path)

    return FileResponse(
        path=str(pdf_path),
        filename=f"mpf_remittance_{month}.pdf",
        media_type="application/pdf",
    )


# ── Annual summary ─────────────────────────────────────────────────────────

@router.get("/annual-summary/{year}")
async def annual_summary(request: Request, year: int) -> list[dict[str, Any]]:
    db = _db(request)
    return generate_annual_summary(db, year)
