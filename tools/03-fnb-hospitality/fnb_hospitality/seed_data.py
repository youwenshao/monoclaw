"""Demo data seeder for the F&B Hospitality Dashboard."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.fnb-hospitality.seed")

SAMPLE_TABLES = [
    {"table_number": "T1", "seats": 2, "section": "window", "is_combinable": True, "combine_with": "T2", "location_type": "window"},
    {"table_number": "T2", "seats": 2, "section": "window", "is_combinable": True, "combine_with": "T1", "location_type": "window"},
    {"table_number": "T3", "seats": 4, "section": "main", "is_combinable": False, "combine_with": None, "location_type": "booth"},
    {"table_number": "T4", "seats": 4, "section": "main", "is_combinable": False, "combine_with": None, "location_type": "standard"},
    {"table_number": "T5", "seats": 4, "section": "main", "is_combinable": True, "combine_with": "T6", "location_type": "standard"},
    {"table_number": "T6", "seats": 4, "section": "main", "is_combinable": True, "combine_with": "T5", "location_type": "standard"},
    {"table_number": "T7", "seats": 6, "section": "corner", "is_combinable": False, "combine_with": None, "location_type": "quiet"},
    {"table_number": "T8", "seats": 8, "section": "private", "is_combinable": False, "combine_with": None, "location_type": "private_room"},
    {"table_number": "R1", "seats": 10, "section": "private", "is_combinable": False, "combine_with": None, "location_type": "round_table"},
    {"table_number": "R2", "seats": 12, "section": "private", "is_combinable": False, "combine_with": None, "location_type": "round_table"},
]

SAMPLE_BOOKINGS = [
    {"guest_name": "陳大文", "guest_phone": "+85291234567", "party_size": 4, "days_offset": 0, "time": "19:30", "channel": "whatsapp", "status": "confirmed", "language_pref": "zh"},
    {"guest_name": "Wong Siu Ming", "guest_phone": "+85298765432", "party_size": 2, "days_offset": 0, "time": "20:00", "channel": "openrice", "status": "confirmed", "language_pref": "en"},
    {"guest_name": "李小蘭", "guest_phone": "+85261234567", "party_size": 6, "days_offset": 1, "time": "19:00", "channel": "whatsapp", "status": "pending", "language_pref": "zh"},
    {"guest_name": "張偉明", "guest_phone": "+85295551234", "party_size": 8, "days_offset": 1, "time": "19:30", "channel": "phone", "status": "pending", "language_pref": "zh"},
    {"guest_name": "Sarah Chen", "guest_phone": "+85268887777", "party_size": 2, "days_offset": 2, "time": "12:30", "channel": "instagram", "status": "pending", "language_pref": "en"},
    {"guest_name": "何家強", "guest_phone": "+85297776666", "party_size": 10, "days_offset": 3, "time": "19:00", "channel": "phone", "status": "pending", "language_pref": "zh", "special_requests": "生日晚宴，需要蛋糕"},
]

SAMPLE_GUESTS_NOSHOW = [
    {"phone": "+85291234567", "name": "陳大文", "total_bookings": 12, "completed": 11, "no_shows": 1, "late_cancellations": 0, "reliability_score": "A"},
    {"phone": "+85298765432", "name": "Wong Siu Ming", "total_bookings": 5, "completed": 5, "no_shows": 0, "late_cancellations": 0, "reliability_score": "A"},
    {"phone": "+85261234567", "name": "李小蘭", "total_bookings": 8, "completed": 6, "no_shows": 2, "late_cancellations": 0, "reliability_score": "C"},
    {"phone": "+85295551234", "name": "張偉明", "total_bookings": 3, "completed": 3, "no_shows": 0, "late_cancellations": 0, "reliability_score": "B"},
    {"phone": "+85268887777", "name": "Sarah Chen", "total_bookings": 1, "completed": 0, "no_shows": 1, "late_cancellations": 0, "reliability_score": "C"},
    {"phone": "+85297776666", "name": "何家強", "total_bookings": 20, "completed": 19, "no_shows": 0, "late_cancellations": 1, "reliability_score": "A"},
]

SAMPLE_SM_GUESTS = [
    {
        "name": "陳大文", "preferred_name": "David", "phone": "+85291234567",
        "language_pref": "cantonese", "vip_tier": "vip", "tags": "wine lover,regular",
        "total_visits": 12, "total_spend": 28000, "avg_spend_per_head": 580,
    },
    {
        "name": "何家強", "preferred_name": "何生", "phone": "+85297776666",
        "language_pref": "cantonese", "vip_tier": "vvip", "tags": "corporate,birthday March",
        "total_visits": 20, "total_spend": 120000, "avg_spend_per_head": 750,
    },
    {
        "name": "Sarah Chen", "preferred_name": "Sarah", "phone": "+85268887777",
        "language_pref": "english", "vip_tier": "regular", "tags": "vegetarian",
        "total_visits": 1, "total_spend": 680, "avg_spend_per_head": 340,
    },
]

SAMPLE_DIETARY_INFO = [
    {"guest_idx": 0, "type": "allergy", "item": "shellfish", "severity": "severe"},
    {"guest_idx": 1, "type": "preference", "item": "no MSG", "severity": None},
    {"guest_idx": 1, "type": "allergy", "item": "peanuts", "severity": "moderate"},
    {"guest_idx": 2, "type": "preference", "item": "vegetarian", "severity": None},
    {"guest_idx": 2, "type": "allergy", "item": "lactose", "severity": "mild"},
]

SAMPLE_CELEBRATIONS = [
    {"guest_idx": 1, "event_type": "birthday", "gregorian_date": "2026-03-15", "use_lunar": False},
    {"guest_idx": 0, "event_type": "anniversary", "gregorian_date": "2026-06-20", "use_lunar": False},
]

SAMPLE_PREFERENCES = [
    {"guest_idx": 0, "category": "wine", "preference": "Burgundy Pinot Noir", "strength": "love"},
    {"guest_idx": 0, "category": "seating", "preference": "window seat", "strength": "like"},
    {"guest_idx": 1, "category": "spirit", "preference": "Hennessy XO", "strength": "love"},
    {"guest_idx": 1, "category": "tea", "preference": "Pu'er", "strength": "like"},
    {"guest_idx": 1, "category": "seating", "preference": "private room R1", "strength": "like"},
    {"guest_idx": 2, "category": "wine", "preference": "Sauvignon Blanc", "strength": "like"},
]


def seed_table_master(db_path: str | Path) -> int:
    """Seed tables and bookings. Returns count of records added."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
        if existing > 0:
            logger.info("TableMaster already has data, skipping seed")
            return 0

        for t in SAMPLE_TABLES:
            conn.execute(
                """INSERT INTO tables
                   (table_number, seats, section, is_combinable, combine_with, location_type)
                   VALUES (?,?,?,?,?,?)""",
                (t["table_number"], t["seats"], t["section"],
                 t["is_combinable"], t["combine_with"], t["location_type"]),
            )
            count += 1

        table_ids = {r[0]: r[1] for r in conn.execute("SELECT table_number, id FROM tables").fetchall()}
        today = date.today()

        for b in SAMPLE_BOOKINGS:
            bdate = today + timedelta(days=b["days_offset"])
            assigned_table = None
            if b["status"] == "confirmed":
                for tn, tid in table_ids.items():
                    tbl = next((t for t in SAMPLE_TABLES if t["table_number"] == tn), None)
                    if tbl and tbl["seats"] >= b["party_size"]:
                        assigned_table = tid
                        break

            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    table_id, channel, status, special_requests, language_pref)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (b["guest_name"], b["guest_phone"], b["party_size"],
                 bdate.isoformat(), b["time"], assigned_table,
                 b["channel"], b["status"], b.get("special_requests"),
                 b["language_pref"]),
            )
            count += 1

    logger.info("Seeded %d TableMaster records", count)
    return count


def seed_queue_bot(db_path: str | Path) -> int:
    """Seed sample queue entries and turnover history."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM queue_entries").fetchone()[0]
        if existing > 0:
            return 0

        now = datetime.now()
        entries = [
            (1, "林小姐", "+85291112222", 2, "waiting", 15, now - timedelta(minutes=15)),
            (2, "黃先生", "+85293334444", 4, "waiting", 25, now - timedelta(minutes=10)),
            (3, "Tan Family", "+85295556666", 6, "waiting", 35, now - timedelta(minutes=5)),
        ]
        for q_num, name, phone, size, status, est_wait, joined in entries:
            conn.execute(
                """INSERT INTO queue_entries
                   (queue_number, guest_name, guest_phone, party_size, status,
                    estimated_wait_minutes, position_at_join, joined_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (q_num, name, phone, size, status, est_wait, q_num, joined.isoformat()),
            )
            count += 1

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        turnover_rows = [
            (yesterday, "lunch", "T3", 3, "12:15", "13:25", 70),
            (yesterday, "lunch", "T4", 4, "12:30", "13:50", 80),
            (yesterday, "dinner", "T3", 4, "19:00", "20:35", 95),
            (yesterday, "dinner", "T5", 2, "19:30", "21:00", 90),
            (yesterday, "dinner", "T7", 6, "19:15", "21:20", 125),
        ]
        for row in turnover_rows:
            conn.execute(
                """INSERT INTO table_turnover
                   (date, time_slot, table_id, party_size, seated_at, cleared_at, duration_minutes)
                   VALUES (?,?,?,?,?,?,?)""",
                row,
            )
            count += 1

    logger.info("Seeded %d QueueBot records", count)
    return count


def seed_no_show_shield(db_path: str | Path) -> int:
    """Seed guest reliability data."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0]
        if existing > 0:
            return 0

        for g in SAMPLE_GUESTS_NOSHOW:
            conn.execute(
                """INSERT INTO guests
                   (phone, name, total_bookings, completed, no_shows,
                    late_cancellations, reliability_score)
                   VALUES (?,?,?,?,?,?,?)""",
                (g["phone"], g["name"], g["total_bookings"], g["completed"],
                 g["no_shows"], g["late_cancellations"], g["reliability_score"]),
            )
            count += 1

    logger.info("Seeded %d NoShowShield records", count)
    return count


def seed_sommelier_memory(db_path: str | Path) -> int:
    """Seed guest profiles, dietary info, celebrations, and preferences."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM sm_guests").fetchone()[0]
        if existing > 0:
            return 0

        for g in SAMPLE_SM_GUESTS:
            today = date.today()
            first = today - timedelta(days=g["total_visits"] * 14)
            conn.execute(
                """INSERT INTO sm_guests
                   (name, preferred_name, phone, language_pref, vip_tier, tags,
                    total_visits, total_spend, avg_spend_per_head, first_visit, last_visit)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (g["name"], g["preferred_name"], g["phone"], g["language_pref"],
                 g["vip_tier"], g["tags"], g["total_visits"], g["total_spend"],
                 g["avg_spend_per_head"], first.isoformat(), today.isoformat()),
            )
            count += 1

        guest_ids = [r[0] for r in conn.execute("SELECT id FROM sm_guests ORDER BY id").fetchall()]

        for d in SAMPLE_DIETARY_INFO:
            gid = guest_ids[d["guest_idx"]]
            conn.execute(
                "INSERT INTO dietary_info (guest_id, type, item, severity) VALUES (?,?,?,?)",
                (gid, d["type"], d["item"], d["severity"]),
            )
            count += 1

        for c in SAMPLE_CELEBRATIONS:
            gid = guest_ids[c["guest_idx"]]
            conn.execute(
                """INSERT INTO celebrations
                   (guest_id, event_type, gregorian_date, use_lunar) VALUES (?,?,?,?)""",
                (gid, c["event_type"], c["gregorian_date"], c["use_lunar"]),
            )
            count += 1

        for p in SAMPLE_PREFERENCES:
            gid = guest_ids[p["guest_idx"]]
            conn.execute(
                """INSERT INTO preferences
                   (guest_id, category, preference, strength) VALUES (?,?,?,?)""",
                (gid, p["category"], p["preference"], p["strength"]),
            )
            count += 1

    logger.info("Seeded %d SommelierMemory records", count)
    return count


def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "table_master": seed_table_master(db_paths["table_master"]),
        "queue_bot": seed_queue_bot(db_paths["queue_bot"]),
        "no_show_shield": seed_no_show_shield(db_paths["no_show_shield"]),
        "sommelier_memory": seed_sommelier_memory(db_paths["sommelier_memory"]),
    }
