"""Database schema initialization for all medical-dental tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# InsuranceAgent
# ---------------------------------------------------------------------------
INSURANCE_AGENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT,
    name_tc TEXT,
    phone TEXT,
    date_of_birth DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS insurance_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    insurer TEXT NOT NULL,
    policy_number TEXT,
    group_name TEXT,
    member_id TEXT,
    plan_type TEXT,
    effective_date DATE,
    expiry_date DATE,
    annual_limit REAL,
    remaining_balance REAL,
    last_verified TIMESTAMP,
    status TEXT CHECK(status IN ('active','expired','suspended','unknown')) DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS coverage_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER REFERENCES insurance_policies(id),
    benefit_category TEXT,
    sub_limit REAL,
    copay_percentage REAL,
    copay_fixed REAL,
    deductible REAL,
    requires_preauth BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    policy_id INTEGER REFERENCES insurance_policies(id),
    claim_date DATE,
    procedure_code TEXT,
    description TEXT,
    billed_amount REAL,
    approved_amount REAL,
    patient_copay REAL,
    status TEXT CHECK(status IN ('pending','submitted','approved','partial','rejected','paid','appealed')) DEFAULT 'pending',
    insurer_reference TEXT,
    submitted_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS preauthorizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    policy_id INTEGER REFERENCES insurance_policies(id),
    procedure_description TEXT,
    estimated_cost REAL,
    submission_date DATE,
    status TEXT CHECK(status IN ('draft','submitted','approved','denied','expired')) DEFAULT 'draft',
    reference_number TEXT,
    response_date DATE,
    approved_amount REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# ScribeAI
# ---------------------------------------------------------------------------
SCRIBE_AI_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_ref TEXT UNIQUE,
    name_en TEXT,
    name_tc TEXT,
    date_of_birth DATE,
    gender TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    doctor TEXT,
    consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audio_path TEXT,
    raw_transcription TEXT,
    soap_subjective TEXT,
    soap_objective TEXT,
    soap_assessment TEXT,
    soap_plan TEXT,
    icd10_codes TEXT,
    medications_prescribed TEXT,
    follow_up_date DATE,
    status TEXT CHECK(status IN ('recording','transcribing','draft','finalized')) DEFAULT 'recording',
    finalized_at TIMESTAMP,
    finalized_by TEXT,
    amendment_of INTEGER REFERENCES consultations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    category TEXT,
    soap_template TEXT,
    common_icd10 TEXT,
    common_medications TEXT,
    language TEXT DEFAULT 'en'
);

CREATE TABLE IF NOT EXISTS custom_vocabulary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT,
    category TEXT CHECK(category IN ('medication','diagnosis','procedure','anatomy','general')),
    language TEXT,
    phonetic TEXT
);
"""

# ---------------------------------------------------------------------------
# ClinicScheduler
# ---------------------------------------------------------------------------
CLINIC_SCHEDULER_SCHEMA = """
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    specialty TEXT,
    registration_number TEXT,
    default_slot_duration INTEGER DEFAULT 15,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER REFERENCES doctors(id),
    day_of_week INTEGER CHECK(day_of_week BETWEEN 0 AND 6),
    session TEXT CHECK(session IN ('morning','afternoon','evening')),
    start_time TIME,
    end_time TIME,
    room TEXT,
    effective_from DATE,
    effective_until DATE
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_phone TEXT NOT NULL,
    patient_name TEXT,
    patient_name_tc TEXT,
    doctor_id INTEGER REFERENCES doctors(id),
    service_type TEXT,
    appointment_date DATE,
    start_time TIME,
    end_time TIME,
    room TEXT,
    status TEXT CHECK(status IN ('booked','confirmed','arrived','in_progress','completed','cancelled','no_show')) DEFAULT 'booked',
    reminder_sent BOOLEAN DEFAULT FALSE,
    source TEXT CHECK(source IN ('whatsapp','phone','walk_in','online','telegram')) DEFAULT 'whatsapp',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_phone TEXT,
    patient_name TEXT,
    doctor_id INTEGER,
    preferred_date DATE,
    preferred_session TEXT,
    service_type TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'waiting',
    notified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# MedReminder
# ---------------------------------------------------------------------------
MED_REMINDER_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT,
    name_tc TEXT,
    phone TEXT UNIQUE NOT NULL,
    whatsapp_enabled BOOLEAN DEFAULT TRUE,
    preferred_language TEXT DEFAULT 'tc',
    date_of_birth DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    drug_name_en TEXT NOT NULL,
    drug_name_tc TEXT,
    dosage TEXT,
    frequency TEXT,
    time_slots TEXT,
    prescribing_doctor TEXT,
    start_date DATE,
    end_date DATE,
    refill_eligible BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS compliance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    medication_id INTEGER REFERENCES medications(id),
    reminder_sent_at TIMESTAMP,
    response TEXT,
    responded_at TIMESTAMP,
    taken BOOLEAN
);

CREATE TABLE IF NOT EXISTS refill_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER REFERENCES patients(id),
    medication_id INTEGER REFERENCES medications(id),
    photo_path TEXT,
    ocr_result TEXT,
    status TEXT CHECK(status IN ('pending','approved','modified','rejected','ready','collected')) DEFAULT 'pending',
    reviewed_by TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ready_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drug_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_a TEXT NOT NULL,
    drug_b TEXT NOT NULL,
    severity TEXT CHECK(severity IN ('minor','moderate','major','contraindicated')) DEFAULT 'moderate',
    description TEXT,
    source TEXT
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    name_en TEXT,
    name_tc TEXT,
    date_of_birth DATE,
    insurance_patient_id INTEGER,
    scribe_patient_id INTEGER,
    scheduler_patient_phone TEXT,
    reminder_patient_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/medical-dental") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/medical-dental") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "insurance_agent": db_dir / "insurance_agent.db",
        "scribe_ai": db_dir / "scribe_ai.db",
        "clinic_scheduler": db_dir / "clinic_scheduler.db",
        "med_reminder": db_dir / "med_reminder.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["insurance_agent"], INSURANCE_AGENT_SCHEMA)
    run_migrations(db_paths["scribe_ai"], SCRIBE_AI_SCHEMA)
    run_migrations(db_paths["clinic_scheduler"], CLINIC_SCHEDULER_SCHEMA)
    run_migrations(db_paths["med_reminder"], MED_REMINDER_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
