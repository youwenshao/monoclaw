"""Demo data seeder for the Legal Dashboard."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.legal.seed")


# ---------------------------------------------------------------------------
# LegalDoc Analyzer
# ---------------------------------------------------------------------------

SAMPLE_CONTRACTS = [
    {"filename": "tenancy_agreement_kwun_tong.pdf", "contract_type": "tenancy", "language": "en", "analysis_status": "completed"},
    {"filename": "employment_contract_chan.docx", "contract_type": "employment", "language": "en", "analysis_status": "completed"},
    {"filename": "保密協議_李氏企業.pdf", "contract_type": "nda", "language": "zh", "analysis_status": "completed"},
    {"filename": "service_agreement_consultancy.pdf", "contract_type": "service", "language": "en", "analysis_status": "pending"},
    {"filename": "tenancy_central_office.docx", "contract_type": "tenancy", "language": "en", "analysis_status": "pending"},
]

SAMPLE_CLAUSES = [
    {"contract_idx": 0, "clause_number": "3.1", "clause_type": "rent_review", "text_content": "The rent shall be reviewed annually at a rate not exceeding 15% of the preceding year's rent.", "anomaly_score": 0.82, "flag_reason": "Rent escalation cap of 15% exceeds typical HK market standard of 10%"},
    {"contract_idx": 0, "clause_number": "7.2", "clause_type": "termination", "text_content": "Either party may terminate this agreement by giving not less than three months' prior written notice.", "anomaly_score": 0.15, "flag_reason": None},
    {"contract_idx": 0, "clause_number": "12.1", "clause_type": "indemnity", "text_content": "The Tenant shall indemnify the Landlord against all losses, damages, costs and expenses whatsoever.", "anomaly_score": 0.71, "flag_reason": "One-sided indemnity without reciprocal obligation or cap"},
    {"contract_idx": 1, "clause_number": "5.1", "clause_type": "termination", "text_content": "The employer may terminate employment by giving one month's notice or payment in lieu.", "anomaly_score": 0.10, "flag_reason": None},
    {"contract_idx": 1, "clause_number": "8.3", "clause_type": "non_compete", "text_content": "The employee shall not engage in any competing business within Hong Kong for a period of 24 months after termination.", "anomaly_score": 0.88, "flag_reason": "24-month non-compete exceeds typical HK enforceable range of 6-12 months"},
    {"contract_idx": 2, "clause_number": "2.1", "clause_type": "confidentiality", "text_content": "機密資料包括但不限於所有商業資料、技術資料及客戶資料。", "anomaly_score": 0.20, "flag_reason": None},
]

SAMPLE_REFERENCE_CLAUSES = [
    {"contract_type": "tenancy", "clause_type": "rent_review", "standard_text": "The rent shall be reviewed annually at a rate not exceeding 10% of the preceding year's rent, subject to mutual agreement.", "source": "HK Standard Tenancy Template"},
    {"contract_type": "tenancy", "clause_type": "termination", "standard_text": "Either party may terminate this agreement by giving not less than two months' prior written notice to the other party.", "source": "HK Standard Tenancy Template"},
    {"contract_type": "employment", "clause_type": "termination", "standard_text": "Either party may terminate employment by giving one month's written notice or payment in lieu of notice.", "source": "HK Employment Ordinance (Cap 57)"},
    {"contract_type": "employment", "clause_type": "non_compete", "standard_text": "The employee shall not engage in directly competing business within the specific geographic area for a period not exceeding 12 months.", "source": "HK Market Practice"},
    {"contract_type": "nda", "clause_type": "confidentiality", "standard_text": "Confidential Information means all information disclosed by the Disclosing Party that is designated as confidential or would reasonably be understood to be confidential.", "source": "HK Standard NDA Template"},
    {"contract_type": "nda", "clause_type": "duration", "standard_text": "The obligations of confidentiality shall survive for a period of 2 years from the date of disclosure.", "source": "HK Standard NDA Template"},
]


def seed_doc_analyzer(db_path: str | Path) -> int:
    """Seed contracts, clauses, and reference clauses."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        if existing > 0:
            logger.info("DocAnalyzer already has data, skipping seed")
            return 0

        for c in SAMPLE_CONTRACTS:
            conn.execute(
                """INSERT INTO contracts (filename, contract_type, language, analysis_status)
                   VALUES (?,?,?,?)""",
                (c["filename"], c["contract_type"], c["language"], c["analysis_status"]),
            )
            count += 1

        contract_ids = [r[0] for r in conn.execute("SELECT id FROM contracts ORDER BY id").fetchall()]

        for cl in SAMPLE_CLAUSES:
            cid = contract_ids[cl["contract_idx"]]
            conn.execute(
                """INSERT INTO clauses
                   (contract_id, clause_number, clause_type, text_content, anomaly_score, flag_reason)
                   VALUES (?,?,?,?,?,?)""",
                (cid, cl["clause_number"], cl["clause_type"],
                 cl["text_content"], cl["anomaly_score"], cl["flag_reason"]),
            )
            count += 1

        for rc in SAMPLE_REFERENCE_CLAUSES:
            conn.execute(
                """INSERT INTO reference_clauses (contract_type, clause_type, standard_text, source)
                   VALUES (?,?,?,?)""",
                (rc["contract_type"], rc["clause_type"], rc["standard_text"], rc["source"]),
            )
            count += 1

    logger.info("Seeded %d DocAnalyzer records", count)
    return count


# ---------------------------------------------------------------------------
# DeadlineGuardian
# ---------------------------------------------------------------------------

SAMPLE_CASES = [
    {"case_number": "HCA 1234/2026", "case_name": "Chan v Wong", "court": "CFI", "case_type": "contract", "client_name": "Chan Tai Man", "solicitor_responsible": "J. Lee", "status": "active"},
    {"case_number": "DCCJ 567/2026", "case_name": "Li v Cheung Property Ltd", "court": "DCT", "case_type": "personal_injury", "client_name": "Li Siu Ling", "solicitor_responsible": "A. Ho", "status": "active"},
    {"case_number": "HCA 890/2025", "case_name": "Wong Enterprises v Star Trading", "court": "CFI", "case_type": "contract", "client_name": "Wong Enterprises Ltd", "solicitor_responsible": "J. Lee", "status": "active"},
]

SAMPLE_DEADLINES = [
    {"case_idx": 0, "deadline_type": "AoS", "description": "Acknowledgment of Service due", "days_offset": 5, "trigger_days_ago": 9, "statutory_basis": "RHC O.12 r.4", "status": "upcoming"},
    {"case_idx": 0, "deadline_type": "Defence", "description": "Defence filing deadline", "days_offset": 19, "trigger_days_ago": 9, "statutory_basis": "RHC O.18 r.2", "status": "upcoming"},
    {"case_idx": 1, "deadline_type": "Limitation", "description": "Limitation period expires (3yr PI)", "days_offset": 180, "trigger_days_ago": 900, "statutory_basis": "Cap 347 s.4A", "status": "upcoming"},
    {"case_idx": 1, "deadline_type": "Discovery", "description": "Discovery compliance deadline", "days_offset": 14, "trigger_days_ago": 30, "statutory_basis": "RHC O.24", "status": "due_soon"},
    {"case_idx": 2, "deadline_type": "SFD", "description": "Summons for Directions", "days_offset": -3, "trigger_days_ago": 60, "statutory_basis": "RHC O.25 r.1", "status": "overdue"},
]

SAMPLE_REMINDERS = [
    {"deadline_idx": 0, "days_before": 7, "channel": "email", "sent_status": "sent"},
    {"deadline_idx": 0, "days_before": 3, "channel": "whatsapp", "sent_status": "sent"},
    {"deadline_idx": 3, "days_before": 14, "channel": "email", "sent_status": "sent"},
    {"deadline_idx": 4, "days_before": 3, "channel": "whatsapp", "sent_status": "sent"},
    {"deadline_idx": 4, "days_before": 1, "channel": "desktop", "sent_status": "sent"},
]


def seed_deadline_guardian(db_path: str | Path) -> int:
    """Seed cases, deadlines, and reminders."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        if existing > 0:
            logger.info("DeadlineGuardian already has data, skipping seed")
            return 0

        for c in SAMPLE_CASES:
            conn.execute(
                """INSERT INTO cases
                   (case_number, case_name, court, case_type, client_name, solicitor_responsible, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["case_number"], c["case_name"], c["court"], c["case_type"],
                 c["client_name"], c["solicitor_responsible"], c["status"]),
            )
            count += 1

        case_ids = [r[0] for r in conn.execute("SELECT id FROM cases ORDER BY id").fetchall()]
        today = date.today()

        deadline_ids = []
        for d in SAMPLE_DEADLINES:
            cid = case_ids[d["case_idx"]]
            due = today + timedelta(days=d["days_offset"])
            trigger = today - timedelta(days=d["trigger_days_ago"])
            conn.execute(
                """INSERT INTO deadlines
                   (case_id, deadline_type, description, due_date, trigger_date, statutory_basis, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (cid, d["deadline_type"], d["description"],
                 due.isoformat(), trigger.isoformat(),
                 d["statutory_basis"], d["status"]),
            )
            deadline_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for r in SAMPLE_REMINDERS:
            did = deadline_ids[r["deadline_idx"]]
            due_row = conn.execute("SELECT due_date FROM deadlines WHERE id=?", (did,)).fetchone()
            reminder_date = datetime.fromisoformat(due_row[0]) - timedelta(days=r["days_before"])
            conn.execute(
                """INSERT INTO reminders
                   (deadline_id, reminder_date, channel, sent_status)
                   VALUES (?,?,?,?)""",
                (did, reminder_date.isoformat(), r["channel"], r["sent_status"]),
            )
            count += 1

    logger.info("Seeded %d DeadlineGuardian records", count)
    return count


# ---------------------------------------------------------------------------
# DiscoveryAssistant
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENTS = [
    {"source_file": "archive_jan2026.mbox", "doc_type": "email", "author": "john.chan@firmxyz.com", "recipients": "client@example.com", "subject": "Legal advice re: contract dispute", "body_text": "Dear Mr. Wong, Further to our meeting, I advise that..."},
    {"source_file": "archive_jan2026.mbox", "doc_type": "email", "author": "client@example.com", "recipients": "john.chan@firmxyz.com", "subject": "RE: Legal advice re: contract dispute", "body_text": "Dear John, Thank you for your advice. I would like to proceed..."},
    {"source_file": "archive_jan2026.mbox", "doc_type": "email", "author": "john.chan@firmxyz.com", "recipients": "expert@valuation.hk", "subject": "Expert valuation instruction", "body_text": "Without prejudice. We are instructed to obtain your expert opinion..."},
    {"source_file": "contract_draft_v3.docx", "doc_type": "standalone", "author": "Firm XYZ", "recipients": None, "subject": "Draft Sale and Purchase Agreement", "body_text": "THIS AGREEMENT is made the 15th day of January 2026..."},
    {"source_file": "archive_jan2026.mbox", "doc_type": "attachment", "author": "accounting@firmxyz.com", "recipients": "john.chan@firmxyz.com", "subject": "Invoice Q4 2025", "body_text": "Invoice for professional services rendered..."},
]

SAMPLE_CLASSIFICATIONS = [
    {"doc_idx": 0, "relevance_tier": "directly_relevant", "privilege_status": "privileged", "privilege_type": "legal_professional_privilege", "confidence_score": 0.95},
    {"doc_idx": 1, "relevance_tier": "directly_relevant", "privilege_status": "privileged", "privilege_type": "legal_professional_privilege", "confidence_score": 0.92},
    {"doc_idx": 2, "relevance_tier": "potentially_relevant", "privilege_status": "needs_review", "privilege_type": "litigation_privilege", "confidence_score": 0.68},
    {"doc_idx": 3, "relevance_tier": "directly_relevant", "privilege_status": "not_privileged", "privilege_type": None, "confidence_score": 0.88},
    {"doc_idx": 4, "relevance_tier": "not_relevant", "privilege_status": "not_privileged", "privilege_type": None, "confidence_score": 0.91},
]

SAMPLE_TAGS = [
    {"doc_idx": 0, "tag_name": "solicitor-client", "tagged_by": "mona"},
    {"doc_idx": 2, "tag_name": "without-prejudice", "tagged_by": "mona"},
    {"doc_idx": 3, "tag_name": "key-document", "tagged_by": "J. Lee"},
]


def seed_discovery_assistant(db_path: str | Path) -> int:
    """Seed documents, classifications, and tags."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if existing > 0:
            logger.info("DiscoveryAssistant already has data, skipping seed")
            return 0

        base_date = datetime.now() - timedelta(days=60)
        for i, d in enumerate(SAMPLE_DOCUMENTS):
            doc_date = base_date + timedelta(days=i * 3)
            conn.execute(
                """INSERT INTO documents
                   (source_file, doc_type, date_created, author, recipients, subject, body_text, hash_md5)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (d["source_file"], d["doc_type"], doc_date.isoformat(),
                 d["author"], d["recipients"], d["subject"], d["body_text"],
                 f"mock_md5_{i:04d}"),
            )
            count += 1

        doc_ids = [r[0] for r in conn.execute("SELECT id FROM documents ORDER BY id").fetchall()]

        for cl in SAMPLE_CLASSIFICATIONS:
            did = doc_ids[cl["doc_idx"]]
            conn.execute(
                """INSERT INTO classifications
                   (document_id, relevance_tier, privilege_status, privilege_type, confidence_score)
                   VALUES (?,?,?,?,?)""",
                (did, cl["relevance_tier"], cl["privilege_status"],
                 cl["privilege_type"], cl["confidence_score"]),
            )
            count += 1

        for t in SAMPLE_TAGS:
            did = doc_ids[t["doc_idx"]]
            conn.execute(
                "INSERT INTO tags (document_id, tag_name, tagged_by) VALUES (?,?,?)",
                (did, t["tag_name"], t["tagged_by"]),
            )
            count += 1

    logger.info("Seeded %d DiscoveryAssistant records", count)
    return count


# ---------------------------------------------------------------------------
# IntakeBot
# ---------------------------------------------------------------------------

SAMPLE_CLIENTS = [
    {"name_en": "Chan Tai Man", "name_tc": "陳大文", "hkid_last4": "A123", "phone": "+85291234567", "email": "chan@example.com", "source_channel": "whatsapp", "status": "approved"},
    {"name_en": "Wong Siu Ming", "name_tc": "黃小明", "hkid_last4": "B456", "phone": "+85298765432", "email": "wong@example.com", "source_channel": "walk_in", "status": "approved"},
    {"name_en": "Li Mei Ling", "name_tc": "李美玲", "hkid_last4": "C789", "phone": "+85261234567", "email": None, "source_channel": "telegram", "status": "pending_review"},
    {"name_en": "Ho Ka Keung", "name_tc": "何家強", "hkid_last4": "D012", "phone": "+85297776666", "email": "ho@corporate.hk", "source_channel": "referral", "status": "approved"},
]

SAMPLE_MATTERS = [
    {"client_idx": 0, "matter_type": "contract_dispute", "description": "Breach of service agreement with supplier", "adverse_party_name": "Star Trading Ltd", "adverse_party_name_tc": "星貿易有限公司", "urgency": "normal", "status": "active"},
    {"client_idx": 1, "matter_type": "personal_injury", "description": "Workplace injury claim", "adverse_party_name": "ABC Construction Co", "adverse_party_name_tc": "ABC建築公司", "urgency": "urgent", "status": "active"},
    {"client_idx": 2, "matter_type": "tenancy_dispute", "description": "Landlord refusal to return deposit", "adverse_party_name": "Prosperity Properties Ltd", "adverse_party_name_tc": "興盛物業有限公司", "urgency": "normal", "status": "intake"},
    {"client_idx": 3, "matter_type": "corporate", "description": "Shareholder agreement review", "adverse_party_name": None, "adverse_party_name_tc": None, "urgency": "low", "status": "active"},
]

SAMPLE_CONFLICT_CHECKS = [
    {"matter_idx": 0, "checked_against": "Star Trading Ltd", "match_score": 0.0, "match_type": "exact", "result": "clear"},
    {"matter_idx": 1, "checked_against": "ABC Construction Co", "match_score": 0.0, "match_type": "exact", "result": "clear"},
    {"matter_idx": 2, "checked_against": "Prosperity Properties Ltd", "match_score": 0.82, "match_type": "fuzzy", "result": "potential_conflict"},
]

SAMPLE_APPOINTMENTS = [
    {"client_idx": 0, "matter_idx": 0, "solicitor": "J. Lee", "days_offset": -7, "status": "completed"},
    {"client_idx": 1, "matter_idx": 1, "solicitor": "A. Ho", "days_offset": -3, "status": "completed"},
    {"client_idx": 2, "matter_idx": 2, "solicitor": "J. Lee", "days_offset": 2, "status": "scheduled"},
]


def seed_intake_bot(db_path: str | Path) -> int:
    """Seed clients, matters, conflict checks, and appointments."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if existing > 0:
            logger.info("IntakeBot already has data, skipping seed")
            return 0

        for c in SAMPLE_CLIENTS:
            conn.execute(
                """INSERT INTO clients
                   (name_en, name_tc, hkid_last4, phone, email, source_channel, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["name_en"], c["name_tc"], c["hkid_last4"],
                 c["phone"], c["email"], c["source_channel"], c["status"]),
            )
            count += 1

        client_ids = [r[0] for r in conn.execute("SELECT id FROM clients ORDER BY id").fetchall()]

        matter_ids = []
        for m in SAMPLE_MATTERS:
            cid = client_ids[m["client_idx"]]
            conn.execute(
                """INSERT INTO matters
                   (client_id, matter_type, description, adverse_party_name,
                    adverse_party_name_tc, urgency, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (cid, m["matter_type"], m["description"],
                 m["adverse_party_name"], m["adverse_party_name_tc"],
                 m["urgency"], m["status"]),
            )
            matter_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for cc in SAMPLE_CONFLICT_CHECKS:
            mid = matter_ids[cc["matter_idx"]]
            conn.execute(
                """INSERT INTO conflict_checks
                   (matter_id, checked_against, match_score, match_type, result)
                   VALUES (?,?,?,?,?)""",
                (mid, cc["checked_against"], cc["match_score"],
                 cc["match_type"], cc["result"]),
            )
            count += 1

        today = date.today()
        for a in SAMPLE_APPOINTMENTS:
            cid = client_ids[a["client_idx"]]
            mid = matter_ids[a["matter_idx"]]
            appt_date = datetime.combine(
                today + timedelta(days=a["days_offset"]),
                datetime.strptime("10:00", "%H:%M").time(),
            )
            conn.execute(
                """INSERT INTO appointments
                   (client_id, matter_id, solicitor, datetime, duration_minutes, status)
                   VALUES (?,?,?,?,?,?)""",
                (cid, mid, a["solicitor"], appt_date.isoformat(), 60, a["status"]),
            )
            count += 1

    logger.info("Seeded %d IntakeBot records", count)
    return count


# ---------------------------------------------------------------------------
# Seed all
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "doc_analyzer": seed_doc_analyzer(db_paths["doc_analyzer"]),
        "deadline_guardian": seed_deadline_guardian(db_paths["deadline_guardian"]),
        "discovery_assistant": seed_discovery_assistant(db_paths["discovery_assistant"]),
        "intake_bot": seed_intake_bot(db_paths["intake_bot"]),
    }
