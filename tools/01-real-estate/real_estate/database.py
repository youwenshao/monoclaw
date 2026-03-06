"""Database schema initialization for all real estate tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# PropertyGPT
# ---------------------------------------------------------------------------
PROPERTY_GPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    district TEXT NOT NULL,
    sub_district TEXT,
    address_en TEXT,
    address_zh TEXT,
    year_built INTEGER,
    total_floors INTEGER,
    total_units INTEGER,
    management_fee_psf REAL,
    school_net INTEGER,
    nearest_mtr TEXT,
    mtr_walk_minutes REAL,
    has_clubhouse BOOLEAN DEFAULT FALSE,
    pet_allowed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    building_id INTEGER REFERENCES buildings(id),
    flat TEXT,
    floor TEXT,
    saleable_area_sqft REAL,
    gross_area_sqft REAL,
    price_hkd INTEGER,
    price_psf_saleable REAL,
    transaction_date DATE,
    instrument_date DATE,
    source TEXT
);

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_phone TEXT,
    query_text TEXT,
    response_text TEXT,
    sources_cited TEXT,
    latency_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# ListingSync
# ---------------------------------------------------------------------------
LISTING_SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_code TEXT UNIQUE NOT NULL,
    title_en TEXT,
    title_zh TEXT,
    description_master TEXT,
    district TEXT,
    estate TEXT,
    address TEXT,
    saleable_area_sqft REAL,
    gross_area_sqft REAL,
    price_hkd INTEGER,
    bedrooms INTEGER,
    bathrooms INTEGER,
    floor TEXT,
    facing TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS platform_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER REFERENCES listings(id),
    platform TEXT NOT NULL,
    platform_listing_id TEXT,
    description_adapted TEXT,
    posted_at TIMESTAMP,
    status TEXT DEFAULT 'pending',
    last_checked TIMESTAMP,
    views INTEGER DEFAULT 0,
    inquiries INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER REFERENCES listings(id),
    original_path TEXT,
    processed_paths TEXT,
    watermarked BOOLEAN DEFAULT FALSE,
    sort_order INTEGER
);
"""

# ---------------------------------------------------------------------------
# TenancyDoc
# ---------------------------------------------------------------------------
TENANCY_DOC_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_address TEXT NOT NULL,
    property_address_zh TEXT,
    district TEXT,
    landlord_name TEXT NOT NULL,
    landlord_hkid TEXT,
    landlord_phone TEXT,
    tenant_name TEXT NOT NULL,
    tenant_hkid TEXT,
    tenant_phone TEXT,
    monthly_rent INTEGER NOT NULL,
    deposit_amount INTEGER,
    term_months INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    break_clause_date DATE,
    stamp_duty_amount REAL,
    cr109_filed BOOLEAN DEFAULT FALSE,
    cr109_filed_date DATE,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenancy_id INTEGER REFERENCES tenancies(id),
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS renewal_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenancy_id INTEGER REFERENCES tenancies(id),
    alert_date DATE NOT NULL,
    alert_type TEXT,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# ViewingBot
# ---------------------------------------------------------------------------
VIEWING_BOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS viewings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_ref TEXT NOT NULL,
    property_address TEXT,
    district TEXT,
    viewer_name TEXT,
    viewer_phone TEXT NOT NULL,
    landlord_phone TEXT,
    agent_phone TEXT,
    proposed_datetime TIMESTAMP NOT NULL,
    confirmed_datetime TIMESTAMP,
    status TEXT DEFAULT 'pending',
    viewer_confirmed BOOLEAN DEFAULT FALSE,
    landlord_confirmed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS availability_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_ref TEXT NOT NULL,
    day_of_week INTEGER,
    start_time TIME,
    end_time TIME,
    landlord_blackout_dates TEXT
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    viewing_id INTEGER REFERENCES viewings(id),
    sent_at TIMESTAMP,
    response TEXT,
    interest_level TEXT,
    next_action TEXT
);

CREATE TABLE IF NOT EXISTS message_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    viewing_id INTEGER REFERENCES viewings(id),
    direction TEXT,
    phone TEXT,
    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/real-estate") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/real-estate") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "property_gpt": db_dir / "property_gpt.db",
        "listing_sync": db_dir / "listing_sync.db",
        "tenancy_doc": db_dir / "tenancy_doc.db",
        "viewing_bot": db_dir / "viewing_bot.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["property_gpt"], PROPERTY_GPT_SCHEMA)
    run_migrations(db_paths["listing_sync"], LISTING_SYNC_SCHEMA)
    run_migrations(db_paths["tenancy_doc"], TENANCY_DOC_SCHEMA)
    run_migrations(db_paths["viewing_bot"], VIEWING_BOT_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
