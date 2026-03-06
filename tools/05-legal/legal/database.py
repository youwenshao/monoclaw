"""Database schema initialization for all legal tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# LegalDoc Analyzer
# ---------------------------------------------------------------------------
DOC_ANALYZER_SCHEMA = """
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    contract_type TEXT CHECK(contract_type IN ('tenancy','employment','nda','service','other')),
    language TEXT DEFAULT 'en',
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_status TEXT DEFAULT 'pending',
    page_count INTEGER,
    file_path TEXT
);

CREATE TABLE IF NOT EXISTS clauses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER REFERENCES contracts(id),
    clause_number TEXT,
    clause_type TEXT,
    text_content TEXT,
    anomaly_score REAL DEFAULT 0.0,
    flag_reason TEXT,
    page_number INTEGER,
    start_offset INTEGER,
    end_offset INTEGER
);

CREATE TABLE IF NOT EXISTS reference_clauses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_type TEXT,
    clause_type TEXT,
    standard_text TEXT,
    source TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# DeadlineGuardian
# ---------------------------------------------------------------------------
DEADLINE_GUARDIAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT UNIQUE,
    case_name TEXT,
    court TEXT CHECK(court IN ('CFI','DCT','Lands Tribunal','Labour Tribunal','Other')),
    case_type TEXT,
    client_name TEXT,
    solicitor_responsible TEXT,
    status TEXT DEFAULT 'active',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id),
    deadline_type TEXT,
    description TEXT,
    due_date DATE NOT NULL,
    trigger_date DATE,
    statutory_basis TEXT,
    status TEXT CHECK(status IN ('upcoming','due_soon','overdue','completed','waived')) DEFAULT 'upcoming',
    completed_date TIMESTAMP,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deadline_id INTEGER REFERENCES deadlines(id),
    reminder_date TIMESTAMP,
    channel TEXT CHECK(channel IN ('whatsapp','email','desktop')),
    sent_status TEXT DEFAULT 'pending',
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# DiscoveryAssistant
# ---------------------------------------------------------------------------
DISCOVERY_ASSISTANT_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    doc_type TEXT CHECK(doc_type IN ('email','attachment','standalone')),
    date_created TIMESTAMP,
    author TEXT,
    recipients TEXT,
    subject TEXT,
    body_text TEXT,
    hash_md5 TEXT,
    hash_sha256 TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of INTEGER REFERENCES documents(id),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id),
    relevance_tier TEXT CHECK(relevance_tier IN ('directly_relevant','potentially_relevant','not_relevant')),
    privilege_status TEXT CHECK(privilege_status IN ('privileged','not_privileged','partial','needs_review')),
    privilege_type TEXT,
    confidence_score REAL,
    reviewer_override TEXT,
    reviewed_by TEXT,
    review_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS privilege_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id),
    log_date DATE,
    description TEXT,
    privilege_basis TEXT,
    status TEXT DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER REFERENCES documents(id),
    tag_name TEXT,
    tagged_by TEXT,
    tag_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# IntakeBot
# ---------------------------------------------------------------------------
INTAKE_BOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT,
    name_tc TEXT,
    hkid_last4 TEXT,
    phone TEXT,
    email TEXT,
    wechat_id TEXT,
    whatsapp_number TEXT,
    source_channel TEXT CHECK(source_channel IN ('whatsapp','wechat','telegram','walk_in','referral','website')),
    intake_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending_review'
);

CREATE TABLE IF NOT EXISTS matters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    matter_type TEXT,
    description TEXT,
    adverse_party_name TEXT,
    adverse_party_name_tc TEXT,
    urgency TEXT CHECK(urgency IN ('urgent','normal','low')),
    assigned_solicitor TEXT,
    status TEXT DEFAULT 'intake',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conflict_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id INTEGER REFERENCES matters(id),
    checked_against TEXT,
    match_score REAL,
    match_type TEXT,
    result TEXT CHECK(result IN ('clear','potential_conflict','confirmed_conflict')),
    reviewed_by TEXT,
    check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    matter_id INTEGER REFERENCES matters(id),
    solicitor TEXT,
    datetime TIMESTAMP,
    duration_minutes INTEGER DEFAULT 60,
    location TEXT DEFAULT 'office',
    status TEXT CHECK(status IN ('scheduled','confirmed','completed','cancelled','no_show')),
    confirmation_sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    channel TEXT,
    direction TEXT CHECK(direction IN ('inbound','outbound')),
    message_text TEXT,
    state TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Shared (cross-tool client linking)
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    name_en TEXT,
    name_tc TEXT,
    doc_analyzer_contract_ids TEXT,
    deadline_guardian_case_ids TEXT,
    discovery_doc_ids TEXT,
    intake_client_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/legal") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/legal") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "doc_analyzer": db_dir / "doc_analyzer.db",
        "deadline_guardian": db_dir / "deadline_guardian.db",
        "discovery_assistant": db_dir / "discovery_assistant.db",
        "intake_bot": db_dir / "intake_bot.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["doc_analyzer"], DOC_ANALYZER_SCHEMA)
    run_migrations(db_paths["deadline_guardian"], DEADLINE_GUARDIAN_SCHEMA)
    run_migrations(db_paths["discovery_assistant"], DISCOVERY_ASSISTANT_SCHEMA)
    run_migrations(db_paths["intake_bot"], INTAKE_BOT_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
