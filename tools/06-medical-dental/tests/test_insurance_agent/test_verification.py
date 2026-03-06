"""Tests for insurance verification connectors and batch verify."""

import time

from medical_dental.insurance_agent.verification.bupa_connector import BupaConnector
from medical_dental.insurance_agent.verification.axa_connector import AxaConnector
from medical_dental.insurance_agent.verification.generic_connector import GenericConnector


def test_generic_connector_caching():
    connector = BupaConnector(rate_limit_seconds=0)

    result1 = connector.verify_coverage("BUPA-HK-2024-001234", "M001234")
    result2 = connector.verify_coverage("BUPA-HK-2024-001234", "M001234")

    assert result1["policy_number"] == result2["policy_number"]
    assert result1["verified_at"] == result2["verified_at"]

    connector.clear_cache()
    result3 = connector.verify_coverage("BUPA-HK-2024-001234", "M001234")
    assert result3["verified_at"] != result1["verified_at"]


def test_bupa_connector_verify():
    connector = BupaConnector(rate_limit_seconds=0)
    result = connector.verify_coverage("BUPA-HK-2024-001234", "M001234")

    assert result["policy_number"] == "BUPA-HK-2024-001234"
    assert result["member_id"] == "M001234"
    assert result["status"] == "active"
    assert result["plan_type"] == "comprehensive"
    assert result["annual_limit"] == 200000
    assert result["remaining_balance"] > 0
    assert isinstance(result["benefits"], list)
    assert len(result["benefits"]) > 0
    assert result["error"] is None


def test_axa_connector_verify():
    connector = AxaConnector(rate_limit_seconds=0)
    result = connector.verify_coverage("AXA-MED-567890", "AXA567890")

    assert result["policy_number"] == "AXA-MED-567890"
    assert result["member_id"] == "AXA567890"
    assert result["status"] == "active"
    assert result["plan_type"] == "standard"
    assert result["annual_limit"] == 100000
    assert result["remaining_balance"] > 0
    assert isinstance(result["benefits"], list)
    assert result["error"] is None


def test_batch_verify_returns_issues(seeded_db_paths):
    from datetime import date, timedelta
    from openclaw_shared.database import get_db
    from medical_dental.insurance_agent.verification.batch_verify import batch_verify_next_day

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    scheduler_db = seeded_db_paths["clinic_scheduler"]
    insurance_db = seeded_db_paths["insurance_agent"]

    with get_db(scheduler_db) as conn:
        doctor_row = conn.execute("SELECT id FROM doctors LIMIT 1").fetchone()
        doctor_id = doctor_row["id"]
        conn.execute(
            """INSERT INTO appointments
               (patient_phone, patient_name, doctor_id, service_type,
                appointment_date, start_time, end_time, status, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("+85299999999", "Uninsured Patient", doctor_id, "gp",
             tomorrow, "10:00", "10:15", "booked", "whatsapp"),
        )

    connectors = {
        "bupa": BupaConnector(rate_limit_seconds=0),
        "axa": AxaConnector(rate_limit_seconds=0),
    }

    results = batch_verify_next_day(scheduler_db, insurance_db, connectors)
    assert isinstance(results, list)

    uninsured = [r for r in results if r.get("patient_phone") == "+85299999999"]
    assert len(uninsured) > 0
    assert uninsured[0]["issue"] == "no_insurance_record"
