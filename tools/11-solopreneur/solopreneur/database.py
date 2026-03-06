"""Database schema initialization for all Solopreneur Dashboard tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# BizOwner OS
# ---------------------------------------------------------------------------
BIZOWNER_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pos_transaction_id TEXT,
    sale_date TIMESTAMP,
    total_amount REAL,
    payment_method TEXT CHECK(payment_method IN ('cash','credit_card','octopus','fps','alipay','wechat_pay','other')),
    items TEXT,
    customer_phone TEXT,
    pos_source TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date DATE,
    category TEXT CHECK(category IN ('rent','salary','inventory','utilities','marketing','equipment','mpf','insurance','other')),
    description TEXT,
    amount REAL,
    receipt_photo TEXT,
    payment_method TEXT,
    recurring BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    name TEXT,
    name_tc TEXT,
    whatsapp_enabled BOOLEAN DEFAULT TRUE,
    total_spend REAL DEFAULT 0,
    visit_count INTEGER DEFAULT 0,
    last_visit DATE,
    tags TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT,
    item_name_tc TEXT,
    current_stock INTEGER,
    low_stock_threshold INTEGER DEFAULT 10,
    unit_cost REAL,
    last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER REFERENCES customers(id),
    direction TEXT CHECK(direction IN ('inbound','outbound')),
    message_text TEXT,
    message_type TEXT,
    tags TEXT,
    requires_followup BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# MPFCalc
# ---------------------------------------------------------------------------
MPF_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    hkid_last4 TEXT,
    employment_type TEXT CHECK(employment_type IN ('full_time','part_time','casual')),
    start_date DATE,
    mpf_enrollment_date DATE,
    mpf_scheme TEXT,
    mpf_member_number TEXT,
    monthly_salary REAL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monthly_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES employees(id),
    contribution_month DATE,
    relevant_income REAL,
    employer_mandatory REAL,
    employee_mandatory REAL,
    employer_voluntary REAL DEFAULT 0,
    employee_voluntary REAL DEFAULT 0,
    total_contribution REAL,
    payment_status TEXT CHECK(payment_status IN ('calculated','pending','paid','late')) DEFAULT 'calculated',
    payment_date DATE,
    surcharge REAL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS payroll_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER REFERENCES employees(id),
    pay_period_start DATE,
    pay_period_end DATE,
    basic_salary REAL,
    overtime REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    bonus REAL DEFAULT 0,
    other_income REAL DEFAULT 0,
    total_relevant_income REAL,
    mpf_employee_deduction REAL,
    net_pay REAL
);

CREATE TABLE IF NOT EXISTS remittance_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contribution_month DATE,
    trustee TEXT,
    total_employer REAL,
    total_employee REAL,
    total_amount REAL,
    employee_count INTEGER,
    submitted_date DATE,
    reference_number TEXT,
    status TEXT CHECK(status IN ('draft','submitted','confirmed')) DEFAULT 'draft'
);
"""

# ---------------------------------------------------------------------------
# SupplierLedger
# ---------------------------------------------------------------------------
LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_type TEXT CHECK(contact_type IN ('supplier','customer','both')),
    company_name TEXT NOT NULL,
    company_name_tc TEXT,
    contact_person TEXT,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    address TEXT,
    payment_terms_days INTEGER DEFAULT 30,
    credit_limit REAL,
    br_number TEXT,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER REFERENCES contacts(id),
    invoice_type TEXT CHECK(invoice_type IN ('payable','receivable')),
    invoice_number TEXT,
    invoice_date DATE,
    due_date DATE,
    currency TEXT DEFAULT 'HKD',
    total_amount REAL,
    paid_amount REAL DEFAULT 0,
    balance REAL,
    status TEXT CHECK(status IN ('draft','outstanding','partially_paid','paid','overdue','disputed','written_off')) DEFAULT 'outstanding',
    pdf_path TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER REFERENCES invoices(id),
    payment_date DATE,
    amount REAL,
    payment_method TEXT CHECK(payment_method IN ('cheque','bank_transfer','fps','cash','octopus','other')),
    cheque_number TEXT,
    bank_reference TEXT,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER REFERENCES contacts(id),
    statement_date DATE,
    opening_balance REAL,
    closing_balance REAL,
    pdf_path TEXT,
    sent_via TEXT,
    sent_at TIMESTAMP,
    status TEXT DEFAULT 'generated'
);

CREATE TABLE IF NOT EXISTS bank_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date DATE,
    description TEXT,
    amount REAL,
    bank_name TEXT,
    matched_invoice_id INTEGER REFERENCES invoices(id),
    match_status TEXT CHECK(match_status IN ('matched','unmatched','manual')) DEFAULT 'unmatched',
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# SocialSync
# ---------------------------------------------------------------------------
SOCIALSYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_text TEXT,
    content_text_tc TEXT,
    image_paths TEXT,
    video_path TEXT,
    hashtags TEXT,
    cta_text TEXT,
    cta_link TEXT,
    scheduled_time TIMESTAMP,
    status TEXT CHECK(status IN ('draft','scheduled','publishing','published','failed')) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS platform_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER REFERENCES posts(id),
    platform TEXT CHECK(platform IN ('instagram_feed','instagram_story','instagram_reel','facebook_page','facebook_story','whatsapp_status')),
    platform_post_id TEXT,
    publish_status TEXT CHECK(publish_status IN ('pending','published','failed')),
    published_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_post_id INTEGER REFERENCES platform_posts(id),
    impressions INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE,
    theme TEXT,
    notes TEXT,
    post_ids TEXT,
    is_hk_event BOOLEAN DEFAULT FALSE,
    event_name TEXT
);

CREATE TABLE IF NOT EXISTS hashtag_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hashtag TEXT UNIQUE,
    category TEXT,
    avg_engagement REAL,
    usage_count INTEGER DEFAULT 0,
    language TEXT DEFAULT 'en'
);
"""

# ---------------------------------------------------------------------------
# Shared (cross-tool contact linking)
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    bizowner_customer_id INTEGER,
    ledger_contact_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/solopreneur") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/solopreneur") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "bizowner": db_dir / "bizowner.db",
        "mpf": db_dir / "mpf.db",
        "ledger": db_dir / "ledger.db",
        "socialsync": db_dir / "socialsync.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["bizowner"], BIZOWNER_SCHEMA)
    run_migrations(db_paths["mpf"], MPF_SCHEMA)
    run_migrations(db_paths["ledger"], LEDGER_SCHEMA)
    run_migrations(db_paths["socialsync"], SOCIALSYNC_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
