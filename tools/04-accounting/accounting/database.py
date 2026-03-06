"""Database schema initialization for all accounting tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# InvoiceOCR Pro
# ---------------------------------------------------------------------------
INVOICE_OCR_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT,
    supplier_br_number TEXT,
    invoice_number TEXT,
    invoice_date DATE,
    due_date DATE,
    currency TEXT DEFAULT 'HKD',
    subtotal REAL,
    tax_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    category TEXT,
    account_code TEXT,
    source TEXT NOT NULL,
    source_file TEXT,
    ocr_confidence REAL,
    status TEXT DEFAULT 'pending_review',
    duplicate_flag BOOLEAN DEFAULT FALSE,
    accounting_ref TEXT,
    pushed_to TEXT,
    pushed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER REFERENCES invoices(id),
    description TEXT,
    quantity REAL,
    unit_price REAL,
    amount REAL NOT NULL,
    account_code TEXT
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    br_number TEXT,
    default_category TEXT,
    default_account_code TEXT,
    currency TEXT DEFAULT 'HKD',
    total_invoices INTEGER DEFAULT 0,
    last_invoice_date DATE
);

CREATE TABLE IF NOT EXISTS category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_type TEXT NOT NULL,
    match_value TEXT NOT NULL,
    category TEXT NOT NULL,
    account_code TEXT,
    confidence REAL DEFAULT 1.0
);
"""

# ---------------------------------------------------------------------------
# ReconcileAgent
# ---------------------------------------------------------------------------
RECONCILE_AGENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS bank_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    bank_name TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    value_date DATE,
    description TEXT,
    reference TEXT,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    balance REAL,
    currency TEXT DEFAULT 'HKD',
    transaction_type TEXT,
    match_status TEXT DEFAULT 'unmatched',
    matched_ledger_id INTEGER,
    import_batch TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    entry_date DATE NOT NULL,
    description TEXT,
    reference TEXT,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    currency TEXT DEFAULT 'HKD',
    account_code TEXT,
    match_status TEXT DEFAULT 'unmatched',
    matched_bank_id INTEGER,
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    period_start DATE,
    period_end DATE,
    bank_closing_balance REAL,
    ledger_closing_balance REAL,
    matched_count INTEGER,
    unmatched_bank INTEGER,
    unmatched_ledger INTEGER,
    difference REAL,
    status TEXT DEFAULT 'in_progress',
    report_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# FXTracker
# ---------------------------------------------------------------------------
FX_TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT NOT NULL,
    buying_tt REAL,
    selling_tt REAL,
    mid_rate REAL NOT NULL,
    source TEXT DEFAULT 'HKMA',
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, base_currency, target_currency, source)
);

CREATE TABLE IF NOT EXISTS fx_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    transaction_date DATE NOT NULL,
    description TEXT,
    currency TEXT NOT NULL,
    foreign_amount REAL NOT NULL,
    exchange_rate REAL NOT NULL,
    hkd_amount REAL NOT NULL,
    transaction_type TEXT NOT NULL,
    nature TEXT DEFAULT 'revenue',
    reference TEXT,
    is_settled BOOLEAN DEFAULT FALSE,
    settled_date DATE,
    settlement_rate REAL,
    settlement_hkd REAL,
    realized_gain_loss REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS revaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    period_end_date DATE NOT NULL,
    currency TEXT NOT NULL,
    outstanding_foreign_amount REAL,
    original_hkd_amount REAL,
    closing_rate REAL,
    revalued_hkd_amount REAL,
    unrealized_gain_loss REAL,
    journal_entry_ref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fx_exposure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    as_of_date DATE NOT NULL,
    currency TEXT NOT NULL,
    receivables_foreign REAL DEFAULT 0,
    payables_foreign REAL DEFAULT 0,
    net_exposure_foreign REAL,
    net_exposure_hkd REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rate_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency_pair TEXT NOT NULL,
    alert_type TEXT,
    threshold REAL,
    current_rate REAL,
    triggered_at TIMESTAMP,
    notified BOOLEAN DEFAULT FALSE
);
"""

# ---------------------------------------------------------------------------
# TaxCalendar Bot
# ---------------------------------------------------------------------------
TAX_CALENDAR_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    br_number TEXT,
    year_end_month INTEGER NOT NULL,
    ird_file_number TEXT,
    company_type TEXT DEFAULT 'corporation',
    assigned_accountant TEXT,
    accountant_phone TEXT,
    partner TEXT,
    partner_phone TEXT,
    mpf_scheme TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    deadline_type TEXT NOT NULL,
    form_code TEXT,
    assessment_year TEXT,
    original_due_date DATE NOT NULL,
    extended_due_date DATE,
    extension_type TEXT,
    extension_status TEXT,
    filing_status TEXT DEFAULT 'not_started',
    submitted_date DATE,
    checklist_path TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deadline_id INTEGER REFERENCES deadlines(id),
    days_before INTEGER NOT NULL,
    scheduled_date DATE NOT NULL,
    channel TEXT DEFAULT 'whatsapp',
    recipient TEXT,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    escalated BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS mpf_deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    period_month DATE NOT NULL,
    contribution_due_date DATE NOT NULL,
    amount_due REAL,
    paid BOOLEAN DEFAULT FALSE,
    paid_date DATE,
    surcharge_applied BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS checklists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deadline_id INTEGER REFERENCES deadlines(id),
    total_items INTEGER,
    completed_items INTEGER DEFAULT 0,
    items TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    br_number TEXT,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    base_currency TEXT DEFAULT 'HKD',
    year_end_month INTEGER,
    invoice_ocr_supplier_id INTEGER,
    reconcile_account_id INTEGER,
    fx_client_id INTEGER,
    tax_client_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    source TEXT DEFAULT 'HKMA',
    UNIQUE(date, base_currency, target_currency)
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/accounting") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/accounting") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "invoice_ocr": db_dir / "invoice_ocr.db",
        "reconcile_agent": db_dir / "reconcile_agent.db",
        "fx_tracker": db_dir / "fx_tracker.db",
        "tax_calendar": db_dir / "tax_calendar.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["invoice_ocr"], INVOICE_OCR_SCHEMA)
    run_migrations(db_paths["reconcile_agent"], RECONCILE_AGENT_SCHEMA)
    run_migrations(db_paths["fx_tracker"], FX_TRACKER_SCHEMA)
    run_migrations(db_paths["tax_calendar"], TAX_CALENDAR_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
