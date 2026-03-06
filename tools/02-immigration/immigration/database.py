"""Database schema initialization for all immigration tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# VisaDoc OCR
# ---------------------------------------------------------------------------
VISA_DOC_OCR_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    hkid TEXT,
    passport_number TEXT,
    nationality TEXT,
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    ocr_result TEXT,
    confidence_score REAL,
    issue_date DATE,
    expiry_date DATE,
    status TEXT DEFAULT 'pending',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheme_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    scheme TEXT NOT NULL,
    required_docs TEXT,
    submitted_docs TEXT,
    completeness_pct REAL,
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# FormAutoFill
# ---------------------------------------------------------------------------
FORM_AUTOFILL_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    surname_en TEXT,
    given_name_en TEXT,
    hkid TEXT,
    passport_number TEXT,
    passport_expiry DATE,
    nationality TEXT,
    date_of_birth DATE,
    gender TEXT,
    marital_status TEXT,
    phone TEXT,
    email TEXT,
    address_hk TEXT,
    address_overseas TEXT,
    education_level TEXT,
    current_employer TEXT,
    current_position TEXT,
    monthly_salary INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    scheme TEXT NOT NULL,
    form_type TEXT NOT NULL,
    form_version TEXT,
    field_values TEXT,
    generated_pdf_path TEXT,
    checklist_path TEXT,
    status TEXT DEFAULT 'draft',
    submitted_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS form_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_type TEXT NOT NULL,
    version TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    field_map_path TEXT,
    file_hash TEXT,
    downloaded_at TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS field_maps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    form_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    page_number INTEGER,
    x REAL,
    y REAL,
    width REAL,
    height REAL,
    font_size REAL DEFAULT 10,
    max_chars INTEGER,
    field_type TEXT DEFAULT 'text',
    required BOOLEAN DEFAULT FALSE
);
"""

# ---------------------------------------------------------------------------
# ClientPortal Bot
# ---------------------------------------------------------------------------
CLIENT_PORTAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_code TEXT UNIQUE NOT NULL,
    client_id INTEGER,
    client_name TEXT NOT NULL,
    client_phone TEXT,
    client_telegram_id TEXT,
    scheme TEXT NOT NULL,
    current_status TEXT DEFAULT 'documents_gathering',
    status_updated_at TIMESTAMP,
    submitted_date DATE,
    estimated_completion DATE,
    consultant_name TEXT,
    consultant_phone TEXT,
    notes TEXT,
    language_pref TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id),
    status TEXT NOT NULL,
    notes TEXT,
    notified_client BOOLEAN DEFAULT FALSE,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outstanding_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id),
    document_type TEXT NOT NULL,
    description TEXT,
    deadline DATE,
    received BOOLEAN DEFAULT FALSE,
    received_date DATE,
    last_reminder_sent TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id),
    datetime TIMESTAMP NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    type TEXT DEFAULT 'consultation',
    status TEXT DEFAULT 'confirmed',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER,
    channel TEXT NOT NULL,
    sender TEXT NOT NULL,
    message_text TEXT,
    intent TEXT,
    escalated BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# PolicyWatcher
# ---------------------------------------------------------------------------
POLICY_WATCHER_SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    last_scraped TIMESTAMP,
    scrape_frequency_hours INTEGER DEFAULT 24,
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS policy_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES policy_sources(id),
    title TEXT NOT NULL,
    title_zh TEXT,
    document_url TEXT,
    local_path TEXT,
    content_text TEXT,
    content_hash TEXT,
    gazette_ref TEXT,
    published_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES policy_documents(id),
    previous_document_id INTEGER,
    change_type TEXT,
    change_summary TEXT,
    affected_schemes TEXT,
    urgency TEXT DEFAULT 'routine',
    effective_date DATE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    consultant_name TEXT,
    phone TEXT,
    email TEXT,
    telegram_id TEXT,
    schemes_filter TEXT,
    urgency_threshold TEXT DEFAULT 'important',
    channel TEXT DEFAULT 'whatsapp',
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id INTEGER REFERENCES policy_changes(id),
    subscription_id INTEGER REFERENCES alert_subscriptions(id),
    sent_at TIMESTAMP,
    channel TEXT,
    delivery_status TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS policy_fts USING fts5(
    title, content_text, change_summary,
    content='policy_documents',
    content_rowid='id',
    tokenize='unicode61'
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    hkid TEXT,
    passport_number TEXT,
    nationality TEXT,
    date_of_birth DATE,
    phone TEXT,
    email TEXT,
    ocr_client_id INTEGER,
    form_client_id INTEGER,
    portal_case_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/immigration") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/immigration") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "visa_doc_ocr": db_dir / "visa_doc_ocr.db",
        "form_autofill": db_dir / "form_autofill.db",
        "client_portal": db_dir / "client_portal.db",
        "policy_watcher": db_dir / "policy_watcher.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["visa_doc_ocr"], VISA_DOC_OCR_SCHEMA)
    run_migrations(db_paths["form_autofill"], FORM_AUTOFILL_SCHEMA)
    run_migrations(db_paths["client_portal"], CLIENT_PORTAL_SCHEMA)
    run_migrations(db_paths["policy_watcher"], POLICY_WATCHER_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
