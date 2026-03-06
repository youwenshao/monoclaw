"""Demo data seeder for all construction tools."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.seed")


# ---------------------------------------------------------------------------
# PermitTracker seed
# ---------------------------------------------------------------------------

SAMPLE_PROJECTS = [
    {"project_name": "The Pinnacle, Tseung Kwan O", "address": "18 Tong Chun Street, TKO", "lot_number": "TKTL 100", "district": "Sai Kung", "authorized_person": "Arch. Chan Ka Ming (AP-1234)", "rse": "Eng. Wong Tai Wai (RSE-5678)"},
    {"project_name": "Harbour View Renovation", "address": "88 Connaught Road West", "lot_number": "IL 8888", "district": "Central & Western", "authorized_person": "Arch. Lee Siu Lam (AP-2345)", "rse": "Eng. Cheung Wai (RSE-6789)"},
    {"project_name": "NT Industrial Hub", "address": "12 Dai Hei Street, Tai Po", "lot_number": "TPTL 200", "district": "Tai Po", "authorized_person": "Arch. Tam Mei Ling (AP-3456)", "rse": "Eng. Ho Chi Keung (RSE-7890)"},
]

SAMPLE_SUBMISSIONS = [
    {"project_idx": 0, "bd_reference": "BP/2026/0042", "submission_type": "GBP", "description": "General Building Plans for 28-storey residential tower", "days_ago": 45, "status": "Under Examination"},
    {"project_idx": 0, "bd_reference": "BP/2026/0043", "submission_type": "foundation", "description": "Foundation plans with piling layout", "days_ago": 30, "status": "Under Examination"},
    {"project_idx": 1, "bd_reference": "MW/2026/0101", "submission_type": "minor_works", "minor_works_class": "I", "description": "External wall repair and waterproofing", "days_ago": 20, "status": "Received"},
    {"project_idx": 1, "bd_reference": "BP/2025/0899", "submission_type": "GBP", "description": "Interior renovation for commercial podium", "days_ago": 70, "status": "Amendments Required"},
    {"project_idx": 2, "bd_reference": "BP/2026/0055", "submission_type": "drainage", "description": "Drainage plan for industrial complex", "days_ago": 15, "status": "Received"},
    {"project_idx": 2, "bd_reference": "NWSC/2026/0012", "submission_type": "nwsc", "description": "Road opening permit for utility connections", "days_ago": 10, "status": "Under Examination"},
]


def seed_permit_tracker(db_path: str | Path) -> int:
    with get_db(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] > 0:
            logger.info("PermitTracker already has data, skipping seed")
            return 0

        for p in SAMPLE_PROJECTS:
            conn.execute(
                "INSERT INTO projects (project_name, address, lot_number, district, authorized_person, rse) VALUES (?,?,?,?,?,?)",
                (p["project_name"], p["address"], p["lot_number"], p["district"], p["authorized_person"], p["rse"]),
            )
        project_ids = [r[0] for r in conn.execute("SELECT id FROM projects ORDER BY id").fetchall()]

        count = 0
        for s in SAMPLE_SUBMISSIONS:
            pid = project_ids[s["project_idx"]]
            sub_date = (date.today() - timedelta(days=s["days_ago"])).isoformat()
            conn.execute(
                "INSERT INTO submissions (project_id, bd_reference, submission_type, minor_works_class, "
                "description, submitted_date, current_status) VALUES (?,?,?,?,?,?,?)",
                (pid, s["bd_reference"], s["submission_type"], s.get("minor_works_class"),
                 s["description"], sub_date, s["status"]),
            )
            sub_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO status_history (submission_id, status, status_date) VALUES (?,?,?)",
                (sub_id, "Received", sub_date),
            )
            if s["status"] != "Received":
                conn.execute(
                    "INSERT INTO status_history (submission_id, status, status_date) VALUES (?,?,?)",
                    (sub_id, s["status"], (date.today() - timedelta(days=s["days_ago"] // 2)).isoformat()),
                )
            count += 1

    logger.info("Seeded %d PermitTracker records", count)
    return count


# ---------------------------------------------------------------------------
# SafetyForm seed
# ---------------------------------------------------------------------------

SAMPLE_SITES = [
    {"site_name": "TKO Tower A", "address": "18 Tong Chun Street, TKO", "district": "Sai Kung", "project_type": "building", "contractor": "Gammon Construction", "safety_officer": "SO Leung Man Kit", "cic_registration": "CIC-SO-12345"},
    {"site_name": "Harbour View Reno", "address": "88 Connaught Road West", "district": "Central & Western", "project_type": "renovation", "contractor": "Hip Hing Construction", "safety_officer": "SO Chan Mei Yee", "cic_registration": "CIC-SO-23456"},
    {"site_name": "Tai Po Industrial", "address": "12 Dai Hei Street, Tai Po", "district": "Tai Po", "project_type": "civil", "contractor": "China State Construction", "safety_officer": "SO Ng Wai Man", "cic_registration": "CIC-SO-34567"},
]

CHECKLIST_CATEGORIES = ["housekeeping", "ppe", "scaffolding", "excavation", "lifting", "fire_precautions"]


def seed_safety_form(db_path: str | Path) -> int:
    with get_db(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0] > 0:
            logger.info("SafetyForm already has data, skipping seed")
            return 0

        for s in SAMPLE_SITES:
            conn.execute(
                "INSERT INTO sites (site_name, address, district, project_type, contractor, safety_officer, cic_registration) VALUES (?,?,?,?,?,?,?)",
                (s["site_name"], s["address"], s["district"], s["project_type"], s["contractor"], s["safety_officer"], s["cic_registration"]),
            )
        site_ids = [r[0] for r in conn.execute("SELECT id FROM sites ORDER BY id").fetchall()]

        count = 0
        for days_back in range(7):
            for sid in site_ids:
                insp_date = (date.today() - timedelta(days=days_back)).isoformat()
                conn.execute(
                    "INSERT INTO daily_inspections (site_id, inspection_date, inspector, overall_score, status, weather, temperature, worker_count, completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (sid, insp_date, "SO Leung Man Kit", 85.0 + days_back, "completed", "Sunny", 28.5, 45, insp_date),
                )
                insp_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for cat in CHECKLIST_CATEGORIES:
                    conn.execute(
                        "INSERT INTO checklist_items (inspection_id, category, item_description, status) VALUES (?,?,?,?)",
                        (insp_id, cat, f"{cat.replace('_', ' ').title()} inspection item", "pass"),
                    )
                count += 1

        conn.execute(
            "INSERT INTO toolbox_talks (site_id, talk_date, topic, language, conductor, attendee_count, duration_minutes) VALUES (?,?,?,?,?,?,?)",
            (site_ids[0], date.today().isoformat(), "Working at Height — Bamboo Scaffolding Safety", "en", "SO Leung Man Kit", 25, 15),
        )

    logger.info("Seeded %d SafetyForm records", count)
    return count


# ---------------------------------------------------------------------------
# DefectsManager seed
# ---------------------------------------------------------------------------

SAMPLE_PROPERTIES = [
    {"property_name": "Taikoo Shing Block A", "address": "2 Tai Koo Wan Road", "district": "Eastern", "property_type": "residential", "total_units": 200, "building_age": 35, "dmc_reference": "DMC-1982-TKS-A", "management_company": "Swire Properties Management"},
    {"property_name": "Central Plaza", "address": "18 Harbour Road, Wan Chai", "district": "Wan Chai", "property_type": "commercial", "total_units": 50, "building_age": 30, "dmc_reference": "DMC-1992-CP", "management_company": "Sun Hung Kai Properties Management"},
]

SAMPLE_DEFECTS = [
    {"prop_idx": 0, "unit": "12A", "floor": "12/F", "category": "water_seepage", "description": "Water stains on ceiling, suspected from unit above bathroom", "priority": "urgent", "responsibility": "pending", "days_ago": 5},
    {"prop_idx": 0, "unit": "Common", "floor": "G/F", "category": "concrete_spalling", "description": "Concrete spalling at carpark entrance pillar", "priority": "urgent", "responsibility": "oc", "days_ago": 10},
    {"prop_idx": 0, "unit": "8B", "floor": "8/F", "category": "window", "description": "Window frame deterioration, hinges loose", "priority": "normal", "responsibility": "owner", "days_ago": 3},
    {"prop_idx": 1, "unit": "Suite 2001", "floor": "20/F", "category": "electrical", "description": "Flickering lights in corridor near lift lobby", "priority": "normal", "responsibility": "management", "days_ago": 2},
    {"prop_idx": 1, "unit": "Common", "floor": "B1", "category": "plumbing", "description": "Drain blockage in basement car park", "priority": "urgent", "responsibility": "management", "days_ago": 1},
]

SAMPLE_CONTRACTORS = [
    {"company_name": "Cheung Kee Plumbing", "contact_person": "Mr Cheung", "phone": "+85291234567", "trades": '["plumbing","water_seepage"]', "hourly_rate": 350, "performance_score": 4.2},
    {"company_name": "Wah Tat Electrical", "contact_person": "Mr Tam", "phone": "+85292345678", "trades": '["electrical"]', "hourly_rate": 400, "performance_score": 4.5},
    {"company_name": "Sun Hing Building Repair", "contact_person": "Mr Sun", "phone": "+85293456789", "trades": '["concrete_spalling","structural","window"]', "hourly_rate": 380, "performance_score": 3.8},
]


def seed_defects_manager(db_path: str | Path) -> int:
    with get_db(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0] > 0:
            logger.info("DefectsManager already has data, skipping seed")
            return 0

        for p in SAMPLE_PROPERTIES:
            conn.execute(
                "INSERT INTO properties (property_name, address, district, property_type, total_units, building_age, dmc_reference, management_company) VALUES (?,?,?,?,?,?,?,?)",
                (p["property_name"], p["address"], p["district"], p["property_type"], p["total_units"], p["building_age"], p["dmc_reference"], p["management_company"]),
            )
        prop_ids = [r[0] for r in conn.execute("SELECT id FROM properties ORDER BY id").fetchall()]

        for c in SAMPLE_CONTRACTORS:
            conn.execute(
                "INSERT INTO contractors (company_name, contact_person, phone, trades, hourly_rate, performance_score) VALUES (?,?,?,?,?,?)",
                (c["company_name"], c["contact_person"], c["phone"], c["trades"], c["hourly_rate"], c["performance_score"]),
            )

        count = 0
        for d in SAMPLE_DEFECTS:
            pid = prop_ids[d["prop_idx"]]
            reported = (date.today() - timedelta(days=d["days_ago"])).isoformat()
            conn.execute(
                "INSERT INTO defects (property_id, unit, floor, category, description, priority, responsibility, reported_date, status) VALUES (?,?,?,?,?,?,?,?,?)",
                (pid, d["unit"], d["floor"], d["category"], d["description"], d["priority"], d["responsibility"], reported, "reported"),
            )
            count += 1

    logger.info("Seeded %d DefectsManager records", count)
    return count


# ---------------------------------------------------------------------------
# SiteCoordinator seed
# ---------------------------------------------------------------------------

SC_SAMPLE_SITES = [
    {"site_name": "TKO Tower A", "address": "18 Tong Chun Street, TKO", "district": "Sai Kung", "latitude": 22.3078, "longitude": 114.2599, "max_daily_workers": 60, "site_agent": "Mr Fung", "site_agent_phone": "+85294567890"},
    {"site_name": "Harbour View Reno", "address": "88 Connaught Road West", "district": "Central & Western", "latitude": 22.2870, "longitude": 114.1450, "max_daily_workers": 30, "site_agent": "Mr Li", "site_agent_phone": "+85295678901"},
    {"site_name": "Tai Po Industrial", "address": "12 Dai Hei Street, Tai Po", "district": "Tai Po", "latitude": 22.4500, "longitude": 114.1680, "max_daily_workers": 45, "site_agent": "Ms Wong", "site_agent_phone": "+85296789012"},
]

SC_SAMPLE_CONTRACTORS = [
    {"company_name": "Strong Form Engineering", "trade": "formwork", "contact_person": "Mr Au", "phone": "+85261111111", "whatsapp_number": "+85261111111", "team_size": 8, "base_district": "Kwun Tong"},
    {"company_name": "Steel Dragon Rebar", "trade": "rebar", "contact_person": "Mr Yip", "phone": "+85262222222", "whatsapp_number": "+85262222222", "team_size": 6, "base_district": "Tsuen Wan"},
    {"company_name": "Lucky Concrete Co", "trade": "concreting", "contact_person": "Mr Lau", "phone": "+85263333333", "whatsapp_number": "+85263333333", "team_size": 10, "base_district": "Sha Tin"},
    {"company_name": "Bright Star Electrical", "trade": "electrical", "contact_person": "Ms Pang", "phone": "+85264444444", "whatsapp_number": "+85264444444", "team_size": 5, "base_district": "Wan Chai"},
    {"company_name": "Cool Air HVAC", "trade": "HVAC", "contact_person": "Mr Kwok", "phone": "+85265555555", "whatsapp_number": "+85265555555", "team_size": 4, "base_district": "Kowloon City"},
]

TRADE_DEPENDENCIES = [
    ("demolition", "formwork", 0), ("formwork", "rebar", 0), ("rebar", "concreting", 0),
    ("concreting", "plumbing", 3), ("concreting", "electrical", 3), ("concreting", "HVAC", 3),
    ("concreting", "fire_services", 3), ("plumbing", "plastering", 1), ("electrical", "plastering", 1),
    ("plastering", "tiling", 1), ("plastering", "painting", 1), ("tiling", "carpentry", 0),
    ("painting", "glazing", 0), ("glazing", "waterproofing", 0), ("waterproofing", "landscaping", 0),
]


def seed_site_coordinator(db_path: str | Path) -> int:
    with get_db(db_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0] > 0:
            logger.info("SiteCoordinator already has data, skipping seed")
            return 0

        for s in SC_SAMPLE_SITES:
            conn.execute(
                "INSERT INTO sites (site_name, address, district, latitude, longitude, max_daily_workers, site_agent, site_agent_phone) VALUES (?,?,?,?,?,?,?,?)",
                (s["site_name"], s["address"], s["district"], s["latitude"], s["longitude"], s["max_daily_workers"], s["site_agent"], s["site_agent_phone"]),
            )

        for c in SC_SAMPLE_CONTRACTORS:
            conn.execute(
                "INSERT INTO contractors (company_name, trade, contact_person, phone, whatsapp_number, team_size, base_district) VALUES (?,?,?,?,?,?,?)",
                (c["company_name"], c["trade"], c["contact_person"], c["phone"], c["whatsapp_number"], c["team_size"], c["base_district"]),
            )

        for pred, succ, gap in TRADE_DEPENDENCIES:
            conn.execute(
                "INSERT INTO trade_dependencies (predecessor_trade, successor_trade, min_gap_days) VALUES (?,?,?)",
                (pred, succ, gap),
            )

        site_ids = [r[0] for r in conn.execute("SELECT id FROM sites ORDER BY id").fetchall()]
        contractor_ids = [r[0] for r in conn.execute("SELECT id FROM contractors ORDER BY id").fetchall()]

        count = 0
        for day_offset in range(5):
            assign_date = (date.today() + timedelta(days=day_offset)).isoformat()
            for i, cid in enumerate(contractor_ids[:3]):
                sid = site_ids[i % len(site_ids)]
                conn.execute(
                    "INSERT INTO schedule_assignments (site_id, contractor_id, assignment_date, scope_of_work, trade, status) VALUES (?,?,?,?,?,?)",
                    (sid, cid, assign_date, "Standard daily works", SC_SAMPLE_CONTRACTORS[i]["trade"], "scheduled"),
                )
                count += 1

    logger.info("Seeded %d SiteCoordinator records", count)
    return count


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed all tool databases with demo data."""
    return {
        "permit_tracker": seed_permit_tracker(db_paths["permit_tracker"]),
        "safety_form": seed_safety_form(db_paths["safety_form"]),
        "defects_manager": seed_defects_manager(db_paths["defects_manager"]),
        "site_coordinator": seed_site_coordinator(db_paths["site_coordinator"]),
    }
