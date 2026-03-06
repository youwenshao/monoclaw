"""Database schema initialization for all F&B hospitality tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# TableMaster AI
# ---------------------------------------------------------------------------
TABLE_MASTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number TEXT UNIQUE NOT NULL,
    seats INTEGER NOT NULL,
    section TEXT,
    is_combinable BOOLEAN DEFAULT FALSE,
    combine_with TEXT,
    location_type TEXT,
    status TEXT DEFAULT 'available',
    current_booking_id INTEGER
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT NOT NULL,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    end_time TIME,
    table_id INTEGER REFERENCES tables(id),
    channel TEXT NOT NULL,
    channel_ref TEXT,
    status TEXT DEFAULT 'pending',
    special_requests TEXT,
    language_pref TEXT DEFAULT 'zh',
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    total_bookings INTEGER,
    total_covers INTEGER,
    no_shows INTEGER,
    cancellations INTEGER,
    avg_party_size REAL,
    peak_channel TEXT,
    revenue_estimate REAL
);
"""

# ---------------------------------------------------------------------------
# QueueBot
# ---------------------------------------------------------------------------
QUEUE_BOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_number INTEGER NOT NULL,
    guest_name TEXT,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    seating_preference TEXT,
    status TEXT DEFAULT 'waiting',
    estimated_wait_minutes INTEGER,
    actual_wait_minutes INTEGER,
    position_at_join INTEGER,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    seated_at TIMESTAMP,
    left_at TIMESTAMP,
    channel TEXT DEFAULT 'qr'
);

CREATE TABLE IF NOT EXISTS table_turnover (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    time_slot TEXT NOT NULL,
    table_id TEXT,
    party_size INTEGER,
    seated_at TIMESTAMP,
    cleared_at TIMESTAMP,
    duration_minutes INTEGER,
    source TEXT DEFAULT 'pos'
);

CREATE TABLE IF NOT EXISTS queue_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    hour INTEGER NOT NULL,
    total_joined INTEGER,
    total_seated INTEGER,
    total_walkouts INTEGER,
    avg_wait_minutes REAL,
    max_wait_minutes REAL,
    max_queue_length INTEGER
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_entry_id INTEGER REFERENCES queue_entries(id),
    type TEXT NOT NULL,
    channel TEXT,
    sent_at TIMESTAMP,
    delivered BOOLEAN,
    message_text TEXT
);
"""

# ---------------------------------------------------------------------------
# NoShowShield
# ---------------------------------------------------------------------------
NO_SHOW_SHIELD_SCHEMA = """
CREATE TABLE IF NOT EXISTS guests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    name TEXT,
    total_bookings INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    no_shows INTEGER DEFAULT 0,
    late_cancellations INTEGER DEFAULT 0,
    reliability_score TEXT DEFAULT 'B',
    is_blacklisted BOOLEAN DEFAULT FALSE,
    blacklisted_at TIMESTAMP,
    last_visit DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    guest_phone TEXT NOT NULL,
    step INTEGER NOT NULL,
    channel TEXT DEFAULT 'whatsapp',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    response TEXT,
    responded_at TIMESTAMP,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    preferred_date DATE NOT NULL,
    preferred_time TIME NOT NULL,
    flexibility_minutes INTEGER DEFAULT 30,
    offered_booking_id INTEGER,
    status TEXT DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS no_show_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    risk_score REAL,
    risk_factors TEXT,
    prediction TEXT,
    actual_outcome TEXT,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# SommelierMemory
# ---------------------------------------------------------------------------
SOMMELIER_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS sm_guests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    preferred_name TEXT,
    phone TEXT UNIQUE,
    email TEXT,
    photo_path TEXT,
    language_pref TEXT DEFAULT 'cantonese',
    vip_tier TEXT DEFAULT 'regular',
    tags TEXT,
    total_visits INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    avg_spend_per_head REAL,
    first_visit DATE,
    last_visit DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dietary_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id INTEGER REFERENCES sm_guests(id),
    type TEXT NOT NULL,
    item TEXT NOT NULL,
    severity TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS celebrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id INTEGER REFERENCES sm_guests(id),
    event_type TEXT NOT NULL,
    gregorian_date DATE,
    lunar_date TEXT,
    use_lunar BOOLEAN DEFAULT FALSE,
    notes TEXT,
    last_acknowledged DATE
);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id INTEGER REFERENCES sm_guests(id),
    visit_date DATE NOT NULL,
    party_size INTEGER,
    party_notes TEXT,
    table_number TEXT,
    total_spend REAL,
    wine_orders TEXT,
    food_highlights TEXT,
    staff_notes TEXT,
    rating INTEGER
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id INTEGER REFERENCES sm_guests(id),
    category TEXT NOT NULL,
    preference TEXT NOT NULL,
    strength TEXT DEFAULT 'like',
    notes TEXT
);
"""

# ---------------------------------------------------------------------------
# Shared (cross-tool guest linking)
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_guests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    table_master_guest_id INTEGER,
    no_show_guest_id INTEGER,
    sommelier_guest_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/fnb-hospitality") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/fnb-hospitality") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "table_master": db_dir / "table_master.db",
        "queue_bot": db_dir / "queue_bot.db",
        "no_show_shield": db_dir / "no_show_shield.db",
        "sommelier_memory": db_dir / "sommelier_memory.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["table_master"], TABLE_MASTER_SCHEMA)
    run_migrations(db_paths["queue_bot"], QUEUE_BOT_SCHEMA)
    run_migrations(db_paths["no_show_shield"], NO_SHOW_SHIELD_SCHEMA)
    run_migrations(db_paths["sommelier_memory"], SOMMELIER_MEMORY_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
