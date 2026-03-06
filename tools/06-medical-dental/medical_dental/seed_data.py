"""Demo data seeder for the Medical-Dental Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.seed")


# ---------------------------------------------------------------------------
# InsuranceAgent seed data
# ---------------------------------------------------------------------------

SAMPLE_PATIENTS_INSURANCE = [
    {"name_en": "Chan Tai Man", "name_tc": "陳大文", "phone": "+85291234567", "dob": "1975-06-15"},
    {"name_en": "Wong Mei Ling", "name_tc": "黃美玲", "phone": "+85298765432", "dob": "1982-03-22"},
    {"name_en": "Lee Ka Yan", "name_tc": "李嘉欣", "phone": "+85261234567", "dob": "1990-11-08"},
    {"name_en": "Cheung Wai Ming", "name_tc": "張偉明", "phone": "+85295551234", "dob": "1968-01-30"},
    {"name_en": "Lam Siu Fong", "name_tc": "林小鳳", "phone": "+85268887777", "dob": "1955-09-12"},
]

SAMPLE_POLICIES = [
    {"patient_idx": 0, "insurer": "bupa", "policy_number": "BUPA-HK-2024-001234", "group_name": "ABC Corp Group Plan", "member_id": "M001234", "plan_type": "comprehensive", "effective": "2024-01-01", "expiry": "2026-12-31", "annual_limit": 200000, "remaining": 185000, "status": "active"},
    {"patient_idx": 1, "insurer": "axa", "policy_number": "AXA-MED-567890", "group_name": "XYZ Ltd Group Medical", "member_id": "AXA567890", "plan_type": "standard", "effective": "2025-04-01", "expiry": "2026-03-31", "annual_limit": 100000, "remaining": 92000, "status": "active"},
    {"patient_idx": 2, "insurer": "cigna", "policy_number": "CGN-IND-112233", "group_name": None, "member_id": "CI112233", "plan_type": "individual", "effective": "2025-01-01", "expiry": "2025-12-31", "annual_limit": 150000, "remaining": 140000, "status": "active"},
    {"patient_idx": 3, "insurer": "bupa", "policy_number": "BUPA-HK-2023-005678", "group_name": "DEF Holdings", "member_id": "M005678", "plan_type": "executive", "effective": "2023-07-01", "expiry": "2025-06-30", "annual_limit": 500000, "remaining": 0, "status": "expired"},
    {"patient_idx": 4, "insurer": "axa", "policy_number": "AXA-SEN-334455", "group_name": None, "member_id": "AXA334455", "plan_type": "senior", "effective": "2025-01-01", "expiry": "2025-12-31", "annual_limit": 80000, "remaining": 45000, "status": "active"},
]

SAMPLE_COVERAGE = [
    {"policy_idx": 0, "category": "gp_consultation", "sub_limit": 800, "copay_pct": 20, "copay_fixed": 0, "deductible": 0, "preauth": False},
    {"policy_idx": 0, "category": "specialist", "sub_limit": 2000, "copay_pct": 20, "copay_fixed": 0, "deductible": 0, "preauth": False},
    {"policy_idx": 0, "category": "dental_basic", "sub_limit": 1500, "copay_pct": 0, "copay_fixed": 200, "deductible": 0, "preauth": False},
    {"policy_idx": 0, "category": "dental_major", "sub_limit": 5000, "copay_pct": 30, "copay_fixed": 0, "deductible": 500, "preauth": True},
    {"policy_idx": 1, "category": "gp_consultation", "sub_limit": 500, "copay_pct": 0, "copay_fixed": 50, "deductible": 0, "preauth": False},
    {"policy_idx": 1, "category": "specialist", "sub_limit": 1200, "copay_pct": 30, "copay_fixed": 0, "deductible": 0, "preauth": False},
    {"policy_idx": 2, "category": "gp_consultation", "sub_limit": 600, "copay_pct": 0, "copay_fixed": 100, "deductible": 0, "preauth": False},
]

SAMPLE_CLAIMS = [
    {"patient_idx": 0, "policy_idx": 0, "days_ago": 30, "procedure": "GP001", "description": "GP consultation — URTI", "billed": 500, "approved": 400, "copay": 100, "status": "paid", "ref": "CLM-BUPA-20260201"},
    {"patient_idx": 1, "policy_idx": 1, "days_ago": 14, "procedure": "SPEC001", "description": "Cardiology follow-up", "billed": 1200, "approved": 840, "copay": 360, "status": "approved", "ref": "CLM-AXA-20260215"},
    {"patient_idx": 4, "policy_idx": 4, "days_ago": 7, "procedure": "DENTAL01", "description": "Dental scaling and polish", "billed": 800, "approved": None, "copay": None, "status": "submitted", "ref": "CLM-AXA-20260225"},
]


# ---------------------------------------------------------------------------
# ScribeAI seed data
# ---------------------------------------------------------------------------

SAMPLE_PATIENTS_SCRIBE = [
    {"ref": "P-0001", "name_en": "Chan Tai Man", "name_tc": "陳大文", "dob": "1975-06-15", "gender": "M"},
    {"ref": "P-0002", "name_en": "Wong Mei Ling", "name_tc": "黃美玲", "dob": "1982-03-22", "gender": "F"},
    {"ref": "P-0003", "name_en": "Lee Ka Yan", "name_tc": "李嘉欣", "dob": "1990-11-08", "gender": "F"},
]

SAMPLE_CONSULTATIONS = [
    {
        "patient_idx": 0, "doctor": "Dr. Ho Wing Kei", "days_ago": 7,
        "soap_s": "Patient complains of sore throat and runny nose for 3 days. Low-grade fever yesterday.",
        "soap_o": "Temp 37.4°C, BP 128/82 mmHg, HR 78. Pharynx mildly erythematous. No tonsillar exudate. Lungs clear.",
        "soap_a": "Upper respiratory tract infection (URTI)",
        "soap_p": "Paracetamol 500mg QID PRN fever. Dextromethorphan 15mg TID for cough. Rest and fluids. Review in 5 days if no improvement.",
        "icd10": '["J06.9"]',
        "meds": '["Paracetamol 500mg QID","Dextromethorphan 15mg TID"]',
        "status": "finalized",
    },
    {
        "patient_idx": 1, "doctor": "Dr. Ho Wing Kei", "days_ago": 3,
        "soap_s": "Follow-up for hypertension. Feeling well. No headaches or dizziness. Compliant with medications.",
        "soap_o": "BP 132/84 mmHg, HR 72. BMI 24.5. No peripheral oedema.",
        "soap_a": "Essential hypertension — well controlled on current regimen",
        "soap_p": "Continue Amlodipine 5mg daily. Repeat blood panel in 3 months. Diet and exercise counselling.",
        "icd10": '["I10"]',
        "meds": '["Amlodipine 5mg OD"]',
        "status": "finalized",
    },
]

SAMPLE_TEMPLATES = [
    {"name": "URTI", "category": "gp", "soap": '{"subjective":"Sore throat / cough / runny nose for __ days.","objective":"Temp __°C, BP __/__ mmHg. Pharynx: __. Lungs: clear.","assessment":"Upper respiratory tract infection","plan":"Symptomatic relief. Review in 5 days if no improvement."}', "icd10": '["J06.9"]', "meds": '["Paracetamol","Dextromethorphan"]', "lang": "en"},
    {"name": "Hypertension Follow-up", "category": "gp", "soap": '{"subjective":"Follow-up for hypertension. Symptoms: __","objective":"BP __/__ mmHg, HR __, BMI __. Peripheral oedema: __","assessment":"Essential hypertension — __ controlled","plan":"Continue current medications. Review in __ months."}', "icd10": '["I10"]', "meds": '["Amlodipine","Losartan"]', "lang": "en"},
    {"name": "Diabetes Review", "category": "gp", "soap": '{"subjective":"Diabetes follow-up. Glucose control: __. Symptoms: __","objective":"HbA1c: __%. Fasting glucose: __ mmol/L. BMI: __. Feet: __","assessment":"Type 2 diabetes mellitus — __ controlled","plan":"Continue Metformin __mg. Diet counselling. HbA1c in 3 months."}', "icd10": '["E11.9"]', "meds": '["Metformin"]', "lang": "en"},
    {"name": "Dental Check-up", "category": "dental", "soap": '{"subjective":"Routine dental check-up. Complaints: __","objective":"Dentition: __. Gingiva: __. Caries: __. Periodontal: __","assessment":"Dental examination — __","plan":"Scaling and polish. Next review in 6 months."}', "icd10": '["Z01.2"]', "meds": '[]', "lang": "en"},
    {"name": "Dental Extraction", "category": "dental", "soap": '{"subjective":"Toothache at __ for __ days. Pain on biting.","objective":"Tooth __: __. Percussion: +ve. Vitality: __. X-ray: __","assessment":"__ — tooth __ indicated for extraction","plan":"Extract under LA. Post-op: Amoxicillin 500mg TID x 5d, Ibuprofen 400mg TID PRN."}', "icd10": '["K08.1"]', "meds": '["Amoxicillin 500mg TID","Ibuprofen 400mg TID PRN"]', "lang": "en"},
]


# ---------------------------------------------------------------------------
# ClinicScheduler seed data
# ---------------------------------------------------------------------------

SAMPLE_DOCTORS = [
    {"name_en": "Dr. Ho Wing Kei", "name_tc": "何穎琪醫生", "specialty": "General Practice", "reg": "M12345", "slot": 15},
    {"name_en": "Dr. Yip Chi Wai", "name_tc": "葉志偉醫生", "specialty": "Cardiology", "reg": "M23456", "slot": 30},
    {"name_en": "Dr. Ng Mei Sze", "name_tc": "吳美詩牙醫", "specialty": "Dentistry", "reg": "D34567", "slot": 45},
]

SAMPLE_SCHEDULES = [
    {"doc_idx": 0, "dow": 1, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 1, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 2, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 2, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 3, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 4, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 4, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 5, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 0, "dow": 6, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room A"},
    {"doc_idx": 1, "dow": 2, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room B"},
    {"doc_idx": 1, "dow": 2, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Room B"},
    {"doc_idx": 1, "dow": 4, "session": "morning", "start": "09:00", "end": "13:00", "room": "Room B"},
    {"doc_idx": 1, "dow": 4, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Room B"},
    {"doc_idx": 2, "dow": 1, "session": "morning", "start": "09:00", "end": "13:00", "room": "Dental Suite"},
    {"doc_idx": 2, "dow": 1, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Dental Suite"},
    {"doc_idx": 2, "dow": 3, "session": "morning", "start": "09:00", "end": "13:00", "room": "Dental Suite"},
    {"doc_idx": 2, "dow": 3, "session": "afternoon", "start": "14:30", "end": "18:00", "room": "Dental Suite"},
    {"doc_idx": 2, "dow": 5, "session": "morning", "start": "09:00", "end": "13:00", "room": "Dental Suite"},
    {"doc_idx": 2, "dow": 6, "session": "morning", "start": "09:00", "end": "13:00", "room": "Dental Suite"},
]

SAMPLE_APPOINTMENTS = [
    {"phone": "+85291234567", "name": "Chan Tai Man", "name_tc": "陳大文", "doc_idx": 0, "service": "gp", "days_offset": 1, "start": "09:30", "end": "09:45", "room": "Room A", "status": "confirmed", "source": "whatsapp"},
    {"phone": "+85298765432", "name": "Wong Mei Ling", "name_tc": "黃美玲", "doc_idx": 1, "service": "specialist", "days_offset": 1, "start": "10:00", "end": "10:30", "room": "Room B", "status": "booked", "source": "phone"},
    {"phone": "+85261234567", "name": "Lee Ka Yan", "name_tc": "李嘉欣", "doc_idx": 2, "service": "dental_cleaning", "days_offset": 2, "start": "14:30", "end": "15:15", "room": "Dental Suite", "status": "booked", "source": "whatsapp"},
    {"phone": "+85268887777", "name": "Lam Siu Fong", "name_tc": "林小鳳", "doc_idx": 0, "service": "follow_up", "days_offset": 3, "start": "11:00", "end": "11:15", "room": "Room A", "status": "booked", "source": "phone"},
]


# ---------------------------------------------------------------------------
# MedReminder seed data
# ---------------------------------------------------------------------------

SAMPLE_PATIENTS_MEDRM = [
    {"name_en": "Chan Tai Man", "name_tc": "陳大文", "phone": "+85291234567", "whatsapp": True, "lang": "zh", "dob": "1975-06-15"},
    {"name_en": "Wong Mei Ling", "name_tc": "黃美玲", "phone": "+85298765432", "whatsapp": True, "lang": "en", "dob": "1982-03-22"},
    {"name_en": "Lam Siu Fong", "name_tc": "林小鳳", "phone": "+85268887777", "whatsapp": False, "lang": "zh", "dob": "1955-09-12"},
]

SAMPLE_MEDICATIONS = [
    {"patient_idx": 0, "drug_en": "Amlodipine", "drug_tc": "氨氯地平", "dosage": "5mg", "freq": "once daily", "times": '["08:00"]', "doctor": "Dr. Ho Wing Kei", "start": -90, "refill": True},
    {"patient_idx": 0, "drug_en": "Atorvastatin", "drug_tc": "阿托伐他汀", "dosage": "20mg", "freq": "once daily at bedtime", "times": '["22:00"]', "doctor": "Dr. Ho Wing Kei", "start": -90, "refill": True},
    {"patient_idx": 1, "drug_en": "Metformin", "drug_tc": "二甲雙胍", "dosage": "500mg", "freq": "twice daily with meals", "times": '["08:00","20:00"]', "doctor": "Dr. Ho Wing Kei", "start": -60, "refill": True},
    {"patient_idx": 2, "drug_en": "Amlodipine", "drug_tc": "氨氯地平", "dosage": "10mg", "freq": "once daily", "times": '["08:00"]', "doctor": "Dr. Ho Wing Kei", "start": -180, "refill": True},
    {"patient_idx": 2, "drug_en": "Metformin", "drug_tc": "二甲雙胍", "dosage": "850mg", "freq": "twice daily", "times": '["08:00","20:00"]', "doctor": "Dr. Ho Wing Kei", "start": -180, "refill": True},
    {"patient_idx": 2, "drug_en": "Omeprazole", "drug_tc": "奧美拉唑", "dosage": "20mg", "freq": "once daily before breakfast", "times": '["07:30"]', "doctor": "Dr. Ho Wing Kei", "start": -60, "refill": True},
]

SAMPLE_INTERACTIONS = [
    {"drug_a": "Warfarin", "drug_b": "Aspirin", "severity": "major", "desc": "Increased risk of bleeding", "source": "BNF"},
    {"drug_a": "Metformin", "drug_b": "Contrast media", "severity": "major", "desc": "Risk of lactic acidosis; withhold Metformin 48h before and after contrast", "source": "BNF"},
    {"drug_a": "Amlodipine", "drug_b": "Simvastatin", "severity": "moderate", "desc": "Amlodipine may increase simvastatin levels; max simvastatin 20mg", "source": "BNF"},
    {"drug_a": "ACE inhibitor", "drug_b": "Potassium supplement", "severity": "moderate", "desc": "Risk of hyperkalaemia", "source": "BNF"},
    {"drug_a": "SSRI", "drug_b": "NSAID", "severity": "moderate", "desc": "Increased risk of GI bleeding", "source": "BNF"},
    {"drug_a": "Methotrexate", "drug_b": "NSAID", "severity": "major", "desc": "NSAIDs reduce methotrexate clearance; risk of toxicity", "source": "BNF"},
    {"drug_a": "Ciprofloxacin", "drug_b": "Theophylline", "severity": "major", "desc": "Ciprofloxacin inhibits theophylline metabolism", "source": "BNF"},
    {"drug_a": "Clarithromycin", "drug_b": "Statins", "severity": "major", "desc": "CYP3A4 inhibition increases statin levels; rhabdomyolysis risk", "source": "BNF"},
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_insurance_agent(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if existing > 0:
            logger.info("InsuranceAgent already has data, skipping seed")
            return 0

        for p in SAMPLE_PATIENTS_INSURANCE:
            conn.execute(
                "INSERT INTO patients (name_en, name_tc, phone, date_of_birth) VALUES (?,?,?,?)",
                (p["name_en"], p["name_tc"], p["phone"], p["dob"]),
            )
            count += 1

        patient_ids = [r[0] for r in conn.execute("SELECT id FROM patients ORDER BY id").fetchall()]

        policy_ids = []
        for pol in SAMPLE_POLICIES:
            pid = patient_ids[pol["patient_idx"]]
            conn.execute(
                """INSERT INTO insurance_policies
                   (patient_id, insurer, policy_number, group_name, member_id, plan_type,
                    effective_date, expiry_date, annual_limit, remaining_balance, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, pol["insurer"], pol["policy_number"], pol["group_name"],
                 pol["member_id"], pol["plan_type"], pol["effective"], pol["expiry"],
                 pol["annual_limit"], pol["remaining"], pol["status"]),
            )
            policy_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for cov in SAMPLE_COVERAGE:
            polid = policy_ids[cov["policy_idx"]]
            conn.execute(
                """INSERT INTO coverage_details
                   (policy_id, benefit_category, sub_limit, copay_percentage, copay_fixed, deductible, requires_preauth)
                   VALUES (?,?,?,?,?,?,?)""",
                (polid, cov["category"], cov["sub_limit"], cov["copay_pct"],
                 cov["copay_fixed"], cov["deductible"], cov["preauth"]),
            )
            count += 1

        for cl in SAMPLE_CLAIMS:
            pid = patient_ids[cl["patient_idx"]]
            polid = policy_ids[cl["policy_idx"]]
            claim_date = (date.today() - timedelta(days=cl["days_ago"])).isoformat()
            conn.execute(
                """INSERT INTO claims
                   (patient_id, policy_id, claim_date, procedure_code, description,
                    billed_amount, approved_amount, patient_copay, status, insurer_reference)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (pid, polid, claim_date, cl["procedure"], cl["description"],
                 cl["billed"], cl["approved"], cl["copay"], cl["status"], cl["ref"]),
            )
            count += 1

    logger.info("Seeded %d InsuranceAgent records", count)
    return count


def seed_scribe_ai(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if existing > 0:
            return 0

        for p in SAMPLE_PATIENTS_SCRIBE:
            conn.execute(
                "INSERT INTO patients (patient_ref, name_en, name_tc, date_of_birth, gender) VALUES (?,?,?,?,?)",
                (p["ref"], p["name_en"], p["name_tc"], p["dob"], p["gender"]),
            )
            count += 1

        patient_ids = [r[0] for r in conn.execute("SELECT id FROM patients ORDER BY id").fetchall()]

        for c in SAMPLE_CONSULTATIONS:
            pid = patient_ids[c["patient_idx"]]
            cdate = (datetime.now() - timedelta(days=c["days_ago"])).isoformat()
            conn.execute(
                """INSERT INTO consultations
                   (patient_id, doctor, consultation_date, soap_subjective, soap_objective,
                    soap_assessment, soap_plan, icd10_codes, medications_prescribed, status,
                    finalized_at, finalized_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, c["doctor"], cdate, c["soap_s"], c["soap_o"], c["soap_a"], c["soap_p"],
                 c["icd10"], c["meds"], c["status"],
                 cdate if c["status"] == "finalized" else None,
                 c["doctor"] if c["status"] == "finalized" else None),
            )
            count += 1

        for t in SAMPLE_TEMPLATES:
            conn.execute(
                "INSERT INTO templates (name, category, soap_template, common_icd10, common_medications, language) VALUES (?,?,?,?,?,?)",
                (t["name"], t["category"], t["soap"], t["icd10"], t["meds"], t["lang"]),
            )
            count += 1

    logger.info("Seeded %d ScribeAI records", count)
    return count


def seed_clinic_scheduler(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
        if existing > 0:
            return 0

        for d in SAMPLE_DOCTORS:
            conn.execute(
                "INSERT INTO doctors (name_en, name_tc, specialty, registration_number, default_slot_duration) VALUES (?,?,?,?,?)",
                (d["name_en"], d["name_tc"], d["specialty"], d["reg"], d["slot"]),
            )
            count += 1

        doctor_ids = [r[0] for r in conn.execute("SELECT id FROM doctors ORDER BY id").fetchall()]

        for s in SAMPLE_SCHEDULES:
            did = doctor_ids[s["doc_idx"]]
            conn.execute(
                """INSERT INTO schedules
                   (doctor_id, day_of_week, session, start_time, end_time, room)
                   VALUES (?,?,?,?,?,?)""",
                (did, s["dow"], s["session"], s["start"], s["end"], s["room"]),
            )
            count += 1

        today = date.today()
        for a in SAMPLE_APPOINTMENTS:
            did = doctor_ids[a["doc_idx"]]
            adate = today + timedelta(days=a["days_offset"])
            conn.execute(
                """INSERT INTO appointments
                   (patient_phone, patient_name, patient_name_tc, doctor_id, service_type,
                    appointment_date, start_time, end_time, room, status, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (a["phone"], a["name"], a["name_tc"], did, a["service"],
                 adate.isoformat(), a["start"], a["end"], a["room"], a["status"], a["source"]),
            )
            count += 1

    logger.info("Seeded %d ClinicScheduler records", count)
    return count


def seed_med_reminder(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        if existing > 0:
            return 0

        for p in SAMPLE_PATIENTS_MEDRM:
            conn.execute(
                "INSERT INTO patients (name_en, name_tc, phone, whatsapp_enabled, preferred_language, date_of_birth) VALUES (?,?,?,?,?,?)",
                (p["name_en"], p["name_tc"], p["phone"], p["whatsapp"], p["lang"], p["dob"]),
            )
            count += 1

        patient_ids = [r[0] for r in conn.execute("SELECT id FROM patients ORDER BY id").fetchall()]

        today = date.today()
        for m in SAMPLE_MEDICATIONS:
            pid = patient_ids[m["patient_idx"]]
            start = (today + timedelta(days=m["start"])).isoformat()
            conn.execute(
                """INSERT INTO medications
                   (patient_id, drug_name_en, drug_name_tc, dosage, frequency,
                    time_slots, prescribing_doctor, start_date, refill_eligible, active)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (pid, m["drug_en"], m["drug_tc"], m["dosage"], m["freq"],
                 m["times"], m["doctor"], start, m["refill"], True),
            )
            count += 1

        for ix in SAMPLE_INTERACTIONS:
            conn.execute(
                "INSERT INTO drug_interactions (drug_a, drug_b, severity, description, source) VALUES (?,?,?,?,?)",
                (ix["drug_a"], ix["drug_b"], ix["severity"], ix["desc"], ix["source"]),
            )
            count += 1

    logger.info("Seeded %d MedReminder records", count)
    return count


def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "insurance_agent": seed_insurance_agent(db_paths["insurance_agent"]),
        "scribe_ai": seed_scribe_ai(db_paths["scribe_ai"]),
        "clinic_scheduler": seed_clinic_scheduler(db_paths["clinic_scheduler"]),
        "med_reminder": seed_med_reminder(db_paths["med_reminder"]),
    }
