"""Database schema initialization for all construction tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# PermitTracker
# ---------------------------------------------------------------------------
PERMIT_TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    address TEXT,
    lot_number TEXT,
    district TEXT,
    authorized_person TEXT,
    rse TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    bd_reference TEXT UNIQUE,
    submission_type TEXT CHECK(submission_type IN (
        'GBP','foundation','superstructure','drainage',
        'demolition','OP','minor_works','nwsc','other'
    )),
    minor_works_class TEXT,
    minor_works_category TEXT,
    description TEXT,
    submitted_date DATE,
    current_status TEXT,
    last_checked TIMESTAMP,
    expected_completion DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER REFERENCES submissions(id),
    status TEXT NOT NULL,
    status_date TIMESTAMP,
    details TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER REFERENCES submissions(id),
    alert_type TEXT CHECK(alert_type IN ('status_change','overdue','reminder','error')),
    message TEXT,
    channel TEXT,
    sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER REFERENCES submissions(id),
    document_type TEXT,
    file_path TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
"""

# ---------------------------------------------------------------------------
# SafetyForm Bot
# ---------------------------------------------------------------------------
SAFETY_FORM_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    project_type TEXT,
    contractor TEXT,
    safety_officer TEXT,
    cic_registration TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    inspection_date DATE,
    inspector TEXT,
    overall_score REAL,
    status TEXT CHECK(status IN ('in_progress','completed','reviewed')) DEFAULT 'in_progress',
    weather TEXT,
    temperature REAL,
    worker_count INTEGER,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checklist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER REFERENCES daily_inspections(id),
    category TEXT,
    item_description TEXT,
    status TEXT CHECK(status IN ('pass','fail','na','pending')) DEFAULT 'pending',
    photo_path TEXT,
    photo_lat REAL,
    photo_lng REAL,
    photo_timestamp TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS deficiencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    category TEXT,
    description TEXT,
    severity TEXT CHECK(severity IN ('critical','major','minor','observation')),
    photo_path TEXT,
    reported_date DATE,
    due_date DATE,
    resolved_date DATE,
    resolved_by TEXT,
    status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    incident_type TEXT CHECK(incident_type IN (
        'accident','near_miss','dangerous_occurrence','property_damage'
    )),
    date_time TIMESTAMP,
    location_on_site TEXT,
    description TEXT,
    persons_involved TEXT,
    injuries TEXT,
    immediate_action TEXT,
    root_cause TEXT,
    corrective_action TEXT,
    reported_to_ld BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS toolbox_talks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    talk_date DATE,
    topic TEXT,
    language TEXT,
    conductor TEXT,
    attendee_count INTEGER,
    attendee_names TEXT,
    duration_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# DefectsManager
# ---------------------------------------------------------------------------
DEFECTS_MANAGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    property_type TEXT CHECK(property_type IN (
        'residential','commercial','industrial','mixed'
    )),
    total_units INTEGER,
    building_age INTEGER,
    dmc_reference TEXT,
    management_company TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS defects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER REFERENCES properties(id),
    unit TEXT,
    floor TEXT,
    location_detail TEXT,
    category TEXT CHECK(category IN (
        'water_seepage','concrete_spalling','plumbing','electrical',
        'lift','window','common_area','structural','other'
    )),
    description TEXT,
    photo_paths TEXT,
    reported_by TEXT,
    reported_phone TEXT,
    reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority TEXT CHECK(priority IN ('emergency','urgent','normal','low')) DEFAULT 'normal',
    responsibility TEXT CHECK(responsibility IN ('owner','oc','management','pending')) DEFAULT 'pending',
    status TEXT CHECK(status IN (
        'reported','assessed','work_ordered','in_progress',
        'completed','closed','referred'
    )) DEFAULT 'reported',
    closed_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_id INTEGER REFERENCES defects(id),
    contractor_id INTEGER REFERENCES contractors(id),
    scope_of_work TEXT,
    estimated_cost REAL,
    actual_cost REAL,
    issue_date DATE,
    target_completion DATE,
    actual_completion DATE,
    completion_photos TEXT,
    status TEXT CHECK(status IN (
        'draft','issued','accepted','in_progress',
        'completed','signed_off','disputed'
    )) DEFAULT 'draft',
    sign_off_by TEXT,
    sign_off_date DATE
);

CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    trades TEXT,
    registration_numbers TEXT,
    hourly_rate REAL,
    avg_response_hours REAL,
    performance_score REAL DEFAULT 5.0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS defect_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    defect_id INTEGER REFERENCES defects(id),
    update_type TEXT,
    description TEXT,
    photo_path TEXT,
    updated_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# SiteCoordinator
# ---------------------------------------------------------------------------
SITE_COORDINATOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    latitude REAL,
    longitude REAL,
    max_daily_workers INTEGER DEFAULT 50,
    noise_permit_hours TEXT,
    site_agent TEXT,
    site_agent_phone TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    trade TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    whatsapp_number TEXT,
    team_size INTEGER DEFAULT 1,
    base_district TEXT,
    hourly_rate REAL,
    availability TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schedule_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER REFERENCES sites(id),
    contractor_id INTEGER REFERENCES contractors(id),
    assignment_date DATE,
    start_time TIME DEFAULT '08:00',
    end_time TIME DEFAULT '18:00',
    scope_of_work TEXT,
    trade TEXT,
    priority INTEGER DEFAULT 5,
    depends_on INTEGER REFERENCES schedule_assignments(id),
    status TEXT CHECK(status IN (
        'scheduled','dispatched','in_progress',
        'completed','cancelled','rescheduled'
    )) DEFAULT 'scheduled',
    dispatched_at TIMESTAMP,
    completed_at TIMESTAMP,
    completion_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contractor_id INTEGER REFERENCES contractors(id),
    route_date DATE,
    sites_sequence TEXT,
    estimated_travel_minutes INTEGER,
    route_polyline TEXT,
    total_distance_km REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    predecessor_trade TEXT NOT NULL,
    successor_trade TEXT NOT NULL,
    min_gap_days INTEGER DEFAULT 0,
    notes TEXT
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    latitude REAL,
    longitude REAL,
    permit_project_id INTEGER,
    safety_site_id INTEGER,
    defects_property_id INTEGER,
    coordinator_site_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/construction") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(
    workspace: str | Path = "~/OpenClawWorkspace/construction",
) -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "permit_tracker": db_dir / "permit_tracker.db",
        "safety_form": db_dir / "safety_form.db",
        "defects_manager": db_dir / "defects_manager.db",
        "site_coordinator": db_dir / "site_coordinator.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["permit_tracker"], PERMIT_TRACKER_SCHEMA)
    run_migrations(db_paths["safety_form"], SAFETY_FORM_SCHEMA)
    run_migrations(db_paths["defects_manager"], DEFECTS_MANAGER_SCHEMA)
    run_migrations(db_paths["site_coordinator"], SITE_COORDINATOR_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
