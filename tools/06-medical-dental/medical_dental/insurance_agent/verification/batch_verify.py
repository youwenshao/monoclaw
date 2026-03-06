"""Bulk insurance verification for next-day appointments."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from medical_dental.insurance_agent.verification.generic_connector import GenericConnector

logger = logging.getLogger("openclaw.medical-dental.insurance.batch")


def batch_verify_next_day(
    scheduler_db_path: str | Path,
    insurance_db_path: str | Path,
    connectors: dict[str, GenericConnector],
) -> list[dict[str, Any]]:
    """Verify insurance for all patients with appointments tomorrow.

    1. Query the clinic_scheduler DB for tomorrow's appointments.
    2. For each patient, look up their insurance policy in the insurance_agent DB.
    3. Run verification through the appropriate insurer connector.
    4. Return a list of dicts describing any coverage issues found.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    with get_db(scheduler_db_path) as conn:
        appointments = [dict(r) for r in conn.execute(
            "SELECT * FROM appointments WHERE appointment_date = ? AND status != 'cancelled'",
            (tomorrow,),
        ).fetchall()]

    if not appointments:
        logger.info("No appointments found for %s", tomorrow)
        return []

    phone_to_appointments: dict[str, list[dict[str, Any]]] = {}
    for appt in appointments:
        phone = appt.get("patient_phone", "")
        phone_to_appointments.setdefault(phone, []).append(appt)

    results: list[dict[str, Any]] = []

    with get_db(insurance_db_path) as conn:
        for phone, appts in phone_to_appointments.items():
            patient_row = conn.execute(
                "SELECT id, name_en FROM patients WHERE phone = ?", (phone,)
            ).fetchone()

            if not patient_row:
                for appt in appts:
                    results.append({
                        "appointment_id": appt["id"],
                        "patient_phone": phone,
                        "patient_name": appt.get("patient_name", ""),
                        "appointment_date": tomorrow,
                        "start_time": appt.get("start_time", ""),
                        "service_type": appt.get("service_type", ""),
                        "issue": "no_insurance_record",
                        "detail": "Patient not found in insurance database",
                        "verification": None,
                    })
                continue

            patient = dict(patient_row)
            policies = [dict(r) for r in conn.execute(
                "SELECT * FROM insurance_policies WHERE patient_id = ? AND status = 'active'",
                (patient["id"],),
            ).fetchall()]

            if not policies:
                for appt in appts:
                    results.append({
                        "appointment_id": appt["id"],
                        "patient_phone": phone,
                        "patient_name": patient.get("name_en", ""),
                        "appointment_date": tomorrow,
                        "start_time": appt.get("start_time", ""),
                        "service_type": appt.get("service_type", ""),
                        "issue": "no_active_policy",
                        "detail": "No active insurance policy on file",
                        "verification": None,
                    })
                continue

            policy = policies[0]
            insurer = policy.get("insurer", "").lower()
            connector = connectors.get(insurer)

            if not connector:
                for appt in appts:
                    results.append({
                        "appointment_id": appt["id"],
                        "patient_phone": phone,
                        "patient_name": patient.get("name_en", ""),
                        "appointment_date": tomorrow,
                        "start_time": appt.get("start_time", ""),
                        "service_type": appt.get("service_type", ""),
                        "issue": "unsupported_insurer",
                        "detail": f"No connector configured for insurer: {insurer}",
                        "verification": None,
                    })
                continue

            verification = connector.verify_coverage(
                policy.get("policy_number", ""),
                policy.get("member_id", ""),
            )

            for appt in appts:
                issues = _check_coverage_issues(verification, appt, policy)
                if issues:
                    for issue in issues:
                        results.append({
                            "appointment_id": appt["id"],
                            "patient_phone": phone,
                            "patient_name": patient.get("name_en", ""),
                            "appointment_date": tomorrow,
                            "start_time": appt.get("start_time", ""),
                            "service_type": appt.get("service_type", ""),
                            **issue,
                            "verification": verification,
                        })

            if verification.get("status") == "active":
                conn.execute(
                    "UPDATE insurance_policies SET last_verified = CURRENT_TIMESTAMP, "
                    "remaining_balance = ? WHERE id = ?",
                    (verification.get("remaining_balance", policy.get("remaining_balance")), policy["id"]),
                )

    logger.info(
        "Batch verification complete for %s: %d appointments, %d issues",
        tomorrow, len(appointments), len(results),
    )
    return results


def _check_coverage_issues(
    verification: dict[str, Any],
    appointment: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Identify coverage issues for a specific appointment."""
    issues: list[dict[str, Any]] = []

    if verification.get("error"):
        issues.append({
            "issue": "verification_error",
            "detail": verification["error"],
        })
        return issues

    status = verification.get("status", "unknown")
    if status != "active":
        issues.append({
            "issue": "policy_not_active",
            "detail": f"Policy status: {status}",
        })

    remaining = verification.get("remaining_balance", 0)
    if remaining <= 0:
        issues.append({
            "issue": "no_remaining_balance",
            "detail": f"Annual limit exhausted (balance: HK${remaining:,.0f})",
        })
    elif remaining < 500:
        issues.append({
            "issue": "low_balance_warning",
            "detail": f"Low remaining balance: HK${remaining:,.0f}",
        })

    expiry = policy.get("expiry_date", "")
    if expiry and expiry < (date.today() + timedelta(days=7)).isoformat():
        issues.append({
            "issue": "expiring_soon",
            "detail": f"Policy expires on {expiry}",
        })

    return issues
