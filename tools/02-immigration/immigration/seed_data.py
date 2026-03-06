"""Demo data seeder for the Immigration Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.seed")


# ---------------------------------------------------------------------------
# VisaDoc OCR
# ---------------------------------------------------------------------------

SAMPLE_OCR_CLIENTS = [
    {
        "name_en": "Zhang Wei",
        "name_zh": "張偉",
        "hkid": None,
        "passport_number": "EA1234567",
        "nationality": "Chinese",
        "phone": "+8613800138000",
        "email": "zhang.wei@example.com",
    },
    {
        "name_en": "Priya Sharma",
        "name_zh": None,
        "hkid": None,
        "passport_number": "T1234567",
        "nationality": "Indian",
        "phone": "+919876543210",
        "email": "priya.sharma@example.com",
    },
    {
        "name_en": "James Wilson",
        "name_zh": None,
        "hkid": "A123456(7)",
        "passport_number": "987654321",
        "nationality": "British",
        "phone": "+447700900123",
        "email": "james.wilson@example.com",
    },
]

SAMPLE_DOCUMENTS = [
    {"client_idx": 0, "doc_type": "passport", "status": "processed", "confidence": 0.92},
    {"client_idx": 0, "doc_type": "bank_statement", "status": "processed", "confidence": 0.88},
    {"client_idx": 0, "doc_type": "employment_contract", "status": "pending", "confidence": None},
    {"client_idx": 1, "doc_type": "passport", "status": "processed", "confidence": 0.95},
    {"client_idx": 1, "doc_type": "tax_return", "status": "review", "confidence": 0.74},
    {"client_idx": 2, "doc_type": "hkid", "status": "processed", "confidence": 0.97},
    {"client_idx": 2, "doc_type": "passport", "status": "processed", "confidence": 0.93},
]


def seed_visa_doc_ocr(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if existing > 0:
            logger.info("VisaDoc OCR already has data, skipping seed")
            return 0

        for c in SAMPLE_OCR_CLIENTS:
            conn.execute(
                """INSERT INTO clients (name_en, name_zh, hkid, passport_number, nationality, phone, email)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["name_en"], c["name_zh"], c["hkid"], c["passport_number"],
                 c["nationality"], c["phone"], c["email"]),
            )
            count += 1

        client_ids = [r[0] for r in conn.execute("SELECT id FROM clients ORDER BY id").fetchall()]

        for d in SAMPLE_DOCUMENTS:
            cid = client_ids[d["client_idx"]]
            processed_at = datetime.now().isoformat() if d["status"] != "pending" else None
            conn.execute(
                """INSERT INTO documents (client_id, doc_type, file_path, confidence_score, status, processed_at)
                   VALUES (?,?,?,?,?,?)""",
                (cid, d["doc_type"], f"/demo/{d['doc_type']}_{cid}.pdf",
                 d["confidence"], d["status"], processed_at),
            )
            count += 1

    logger.info("Seeded %d VisaDoc OCR records", count)
    return count


# ---------------------------------------------------------------------------
# FormAutoFill
# ---------------------------------------------------------------------------

SAMPLE_FORM_CLIENTS = [
    {
        "name_en": "ZHANG WEI", "name_zh": "張偉", "surname_en": "ZHANG", "given_name_en": "WEI",
        "passport_number": "EA1234567", "passport_expiry": "2030-05-15", "nationality": "Chinese",
        "date_of_birth": "1990-03-20", "gender": "Male", "marital_status": "Single",
        "phone": "+8613800138000", "email": "zhang.wei@example.com",
        "education_level": "Bachelor", "current_employer": "TechCorp Ltd",
        "current_position": "Software Engineer", "monthly_salary": 35000,
    },
    {
        "name_en": "PRIYA SHARMA", "name_zh": None, "surname_en": "SHARMA", "given_name_en": "PRIYA",
        "passport_number": "T1234567", "passport_expiry": "2029-11-30", "nationality": "Indian",
        "date_of_birth": "1988-07-12", "gender": "Female", "marital_status": "Married",
        "phone": "+919876543210", "email": "priya.sharma@example.com",
        "education_level": "Master", "current_employer": "FinanceHK Ltd",
        "current_position": "Financial Analyst", "monthly_salary": 45000,
    },
]


def seed_form_autofill(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if existing > 0:
            return 0

        for c in SAMPLE_FORM_CLIENTS:
            conn.execute(
                """INSERT INTO clients
                   (name_en, name_zh, surname_en, given_name_en, passport_number, passport_expiry,
                    nationality, date_of_birth, gender, marital_status, phone, email,
                    education_level, current_employer, current_position, monthly_salary)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c["name_en"], c["name_zh"], c["surname_en"], c["given_name_en"],
                 c["passport_number"], c["passport_expiry"], c["nationality"],
                 c["date_of_birth"], c["gender"], c["marital_status"],
                 c["phone"], c["email"], c["education_level"],
                 c["current_employer"], c["current_position"], c["monthly_salary"]),
            )
            count += 1

        # Sample form templates
        templates = [
            ("ID990A", "2024-01", "https://www.immd.gov.hk/pdforms/ID990A.pdf"),
            ("ID990B", "2024-01", "https://www.immd.gov.hk/pdforms/ID990B.pdf"),
            ("GEP", "2024-03", "https://www.immd.gov.hk/pdforms/ID990A.pdf"),
            ("IANG", "2024-02", "https://www.immd.gov.hk/pdforms/ID990A.pdf"),
        ]
        for ft, ver, url in templates:
            conn.execute(
                """INSERT INTO form_templates (form_type, version, source_url, is_current)
                   VALUES (?,?,?,1)""",
                (ft, ver, url),
            )
            count += 1

    logger.info("Seeded %d FormAutoFill records", count)
    return count


# ---------------------------------------------------------------------------
# ClientPortal Bot
# ---------------------------------------------------------------------------

SAMPLE_CASES = [
    {
        "reference_code": "IM-2026-001",
        "client_name": "Zhang Wei",
        "client_phone": "+8613800138000",
        "scheme": "GEP",
        "current_status": "under_processing",
        "submitted_date": date.today() - timedelta(days=21),
        "consultant_name": "Alice Chan",
    },
    {
        "reference_code": "IM-2026-002",
        "client_name": "Priya Sharma",
        "client_phone": "+919876543210",
        "scheme": "GEP",
        "current_status": "application_submitted",
        "submitted_date": date.today() - timedelta(days=7),
        "consultant_name": "Alice Chan",
    },
    {
        "reference_code": "IM-2026-003",
        "client_name": "James Wilson",
        "client_phone": "+447700900123",
        "scheme": "IANG",
        "current_status": "documents_gathering",
        "submitted_date": None,
        "consultant_name": "Bob Lee",
    },
    {
        "reference_code": "IM-2026-004",
        "client_name": "Maria Garcia",
        "client_phone": "+34612345678",
        "scheme": "QMAS",
        "current_status": "acknowledgement_received",
        "submitted_date": date.today() - timedelta(days=90),
        "consultant_name": "Alice Chan",
    },
]


def seed_client_portal(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        if existing > 0:
            return 0

        for c in SAMPLE_CASES:
            sub_date = c["submitted_date"].isoformat() if c["submitted_date"] else None
            conn.execute(
                """INSERT INTO cases
                   (reference_code, client_name, client_phone, scheme,
                    current_status, submitted_date, consultant_name, status_updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (c["reference_code"], c["client_name"], c["client_phone"],
                 c["scheme"], c["current_status"], sub_date,
                 c["consultant_name"], datetime.now().isoformat()),
            )
            count += 1

        # Sample outstanding documents
        case_ids = [r[0] for r in conn.execute("SELECT id FROM cases ORDER BY id").fetchall()]
        docs = [
            (case_ids[2], "passport", "Original passport", date.today() + timedelta(days=14)),
            (case_ids[2], "bank_statement", "Last 3 months bank statement", date.today() + timedelta(days=14)),
            (case_ids[2], "degree_certificate", "Certified copy of degree", date.today() + timedelta(days=14)),
        ]
        for case_id, doc_type, desc, deadline in docs:
            conn.execute(
                """INSERT INTO outstanding_documents (case_id, document_type, description, deadline)
                   VALUES (?,?,?,?)""",
                (case_id, doc_type, desc, deadline.isoformat()),
            )
            count += 1

        # Sample appointments
        tomorrow = date.today() + timedelta(days=1)
        conn.execute(
            """INSERT INTO appointments (case_id, datetime, duration_minutes, type, status)
               VALUES (?,?,?,?,?)""",
            (case_ids[0], datetime.combine(tomorrow, datetime.min.time().replace(hour=10)).isoformat(),
             60, "consultation", "confirmed"),
        )
        count += 1

    logger.info("Seeded %d ClientPortal records", count)
    return count


# ---------------------------------------------------------------------------
# PolicyWatcher
# ---------------------------------------------------------------------------

SAMPLE_SOURCES = [
    ("Government Gazette", "https://www.gld.gov.hk/egazette/", 168),
    ("Immigration Department", "https://www.immd.gov.hk/eng/press/press.html", 24),
    ("LegCo Panel on Security", "https://www.legco.gov.hk/en/committees/panel/se.html", 168),
    ("Talent List", "https://www.talentlist.gov.hk/en/", 168),
]


def seed_policy_watcher(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM policy_sources").fetchone()[0]
        if existing > 0:
            return 0

        for name, url, freq in SAMPLE_SOURCES:
            conn.execute(
                """INSERT INTO policy_sources (source_name, source_url, scrape_frequency_hours)
                   VALUES (?,?,?)""",
                (name, url, freq),
            )
            count += 1

        source_ids = [r[0] for r in conn.execute("SELECT id FROM policy_sources ORDER BY id").fetchall()]

        # Sample policy documents
        sample_docs = [
            (source_ids[0], "L.N. 42 of 2026 — Immigration (Amendment) Regulation 2026",
             "L.N. 42/2026年 — 入境(修訂)規例2026",
             "Amendment to salary threshold requirements for General Employment Policy applicants.",
             "LN42/2026", date.today() - timedelta(days=30)),
            (source_ids[1], "TTPS University List Updated",
             "高才通大學名單更新",
             "Three new universities added to the Top Talent Pass Scheme eligible institutions list.",
             None, date.today() - timedelta(days=14)),
        ]
        for sid, title, title_zh, content, gref, pub_date in sample_docs:
            import hashlib
            chash = hashlib.sha256(content.encode()).hexdigest()
            conn.execute(
                """INSERT INTO policy_documents
                   (source_id, title, title_zh, content_text, content_hash, gazette_ref, published_date)
                   VALUES (?,?,?,?,?,?,?)""",
                (sid, title, title_zh, content, chash, gref, pub_date.isoformat()),
            )
            count += 1

        doc_ids = [r[0] for r in conn.execute("SELECT id FROM policy_documents ORDER BY id").fetchall()]
        changes = [
            (doc_ids[0], "modification",
             "GEP salary threshold increased from HK$20,000 to HK$25,000 per month for new applicants.",
             "GEP", "important", date.today() - timedelta(days=15)),
            (doc_ids[1], "addition",
             "Three new universities added to TTPS list: National University of Singapore, "
             "University of Melbourne, University of British Columbia.",
             "TTPS", "routine", date.today() - timedelta(days=14)),
        ]
        for did, ctype, summary, schemes, urgency, eff_date in changes:
            conn.execute(
                """INSERT INTO policy_changes
                   (document_id, change_type, change_summary, affected_schemes, urgency, effective_date)
                   VALUES (?,?,?,?,?,?)""",
                (did, ctype, summary, schemes, urgency, eff_date.isoformat()),
            )
            count += 1

    logger.info("Seeded %d PolicyWatcher records", count)
    return count


# ---------------------------------------------------------------------------
# Seed all
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "visa_doc_ocr": seed_visa_doc_ocr(db_paths["visa_doc_ocr"]),
        "form_autofill": seed_form_autofill(db_paths["form_autofill"]),
        "client_portal": seed_client_portal(db_paths["client_portal"]),
        "policy_watcher": seed_policy_watcher(db_paths["policy_watcher"]),
    }
