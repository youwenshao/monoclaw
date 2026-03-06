"""Demo data seeder for the Real Estate Dashboard."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.real-estate.seed")

SAMPLE_BUILDINGS = [
    {
        "name_en": "Taikoo Shing",
        "name_zh": "太古城",
        "district": "Eastern",
        "sub_district": "Quarry Bay",
        "address_en": "1 King's Road, Quarry Bay",
        "address_zh": "鰂魚涌英皇道1號",
        "year_built": 1977,
        "total_floors": 28,
        "total_units": 12698,
        "management_fee_psf": 2.8,
        "school_net": 16,
        "nearest_mtr": "Tai Koo",
        "mtr_walk_minutes": 3.0,
        "has_clubhouse": True,
        "pet_allowed": True,
    },
    {
        "name_en": "City Garden",
        "name_zh": "城市花園",
        "district": "Eastern",
        "sub_district": "North Point",
        "address_en": "233 Electric Road, North Point",
        "address_zh": "北角電氣道233號",
        "year_built": 1984,
        "total_floors": 32,
        "total_units": 2176,
        "management_fee_psf": 3.1,
        "school_net": 14,
        "nearest_mtr": "Fortress Hill",
        "mtr_walk_minutes": 5.0,
        "has_clubhouse": True,
        "pet_allowed": False,
    },
    {
        "name_en": "The Belcher's",
        "name_zh": "寶翠園",
        "district": "Central & Western",
        "sub_district": "Kennedy Town",
        "address_en": "89 Pok Fu Lam Road",
        "address_zh": "薄扶林道89號",
        "year_built": 2003,
        "total_floors": 42,
        "total_units": 1322,
        "management_fee_psf": 4.2,
        "school_net": 11,
        "nearest_mtr": "Kennedy Town",
        "mtr_walk_minutes": 8.0,
        "has_clubhouse": True,
        "pet_allowed": True,
    },
    {
        "name_en": "Mei Foo Sun Chuen",
        "name_zh": "美孚新邨",
        "district": "Sham Shui Po",
        "sub_district": "Lai Chi Kok",
        "address_en": "Lai Wan Road, Lai Chi Kok",
        "address_zh": "荔枝角荔灣道",
        "year_built": 1968,
        "total_floors": 20,
        "total_units": 13149,
        "management_fee_psf": 2.2,
        "school_net": 40,
        "nearest_mtr": "Mei Foo",
        "mtr_walk_minutes": 2.0,
        "has_clubhouse": False,
        "pet_allowed": True,
    },
    {
        "name_en": "Sham Wan Towers",
        "name_zh": "深灣軒",
        "district": "Southern",
        "sub_district": "Aberdeen",
        "address_en": "3 Ap Lei Chau Drive",
        "address_zh": "鴨脷洲徑3號",
        "year_built": 2002,
        "total_floors": 50,
        "total_units": 936,
        "management_fee_psf": 3.5,
        "school_net": 18,
        "nearest_mtr": "Lei Tung",
        "mtr_walk_minutes": 6.0,
        "has_clubhouse": True,
        "pet_allowed": False,
    },
]

SAMPLE_TRANSACTIONS = [
    {"building_idx": 0, "flat": "A", "floor": "12/F", "saleable_area_sqft": 583, "gross_area_sqft": 762, "price_hkd": 9800000, "days_ago": 5},
    {"building_idx": 0, "flat": "C", "floor": "25/F", "saleable_area_sqft": 710, "gross_area_sqft": 932, "price_hkd": 13500000, "days_ago": 12},
    {"building_idx": 1, "flat": "B", "floor": "18/F", "saleable_area_sqft": 525, "gross_area_sqft": 688, "price_hkd": 8200000, "days_ago": 8},
    {"building_idx": 2, "flat": "D", "floor": "35/F", "saleable_area_sqft": 978, "gross_area_sqft": 1243, "price_hkd": 22000000, "days_ago": 15},
    {"building_idx": 3, "flat": "E", "floor": "8/F", "saleable_area_sqft": 450, "gross_area_sqft": 585, "price_hkd": 5500000, "days_ago": 3},
    {"building_idx": 4, "flat": "A", "floor": "40/F", "saleable_area_sqft": 662, "gross_area_sqft": 854, "price_hkd": 11200000, "days_ago": 20},
]


def seed_property_gpt(db_path: str | Path) -> int:
    """Seed buildings and transactions. Returns count of records added."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        if existing > 0:
            logger.info("PropertyGPT already has data, skipping seed")
            return 0

        for b in SAMPLE_BUILDINGS:
            conn.execute(
                """INSERT INTO buildings
                   (name_en, name_zh, district, sub_district, address_en, address_zh,
                    year_built, total_floors, total_units, management_fee_psf,
                    school_net, nearest_mtr, mtr_walk_minutes, has_clubhouse, pet_allowed)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (b["name_en"], b["name_zh"], b["district"], b["sub_district"],
                 b["address_en"], b["address_zh"], b["year_built"], b["total_floors"],
                 b["total_units"], b["management_fee_psf"], b["school_net"],
                 b["nearest_mtr"], b["mtr_walk_minutes"], b["has_clubhouse"],
                 b["pet_allowed"]),
            )
            count += 1

        building_ids = [r[0] for r in conn.execute("SELECT id FROM buildings ORDER BY id").fetchall()]

        for tx in SAMPLE_TRANSACTIONS:
            bid = building_ids[tx["building_idx"]]
            tx_date = (date.today() - timedelta(days=tx["days_ago"])).isoformat()
            psf = round(tx["price_hkd"] / tx["saleable_area_sqft"], 2)
            conn.execute(
                """INSERT INTO transactions
                   (building_id, flat, floor, saleable_area_sqft, gross_area_sqft,
                    price_hkd, price_psf_saleable, transaction_date, source)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (bid, tx["flat"], tx["floor"], tx["saleable_area_sqft"],
                 tx["gross_area_sqft"], tx["price_hkd"], psf, tx_date, "demo"),
            )
            count += 1

    logger.info("Seeded %d PropertyGPT records", count)
    return count


def seed_listing_sync(db_path: str | Path) -> int:
    """Seed sample listings."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        if existing > 0:
            return 0

        listings = [
            ("RE-2026-001", "Spacious 3BR at Taikoo Shing", "太古城寬敞三房",
             "Bright and spacious 3-bedroom unit with sea view. Recently renovated kitchen and bathrooms. "
             "Close to MTR and shopping. Saleable area 710 sqft.",
             "Eastern", "Taikoo Shing", "Block 3, Taikoo Shing", 710, 932, 13500000, 3, 2, "25/F", "South"),
            ("RE-2026-002", "Modern Studio at The Belcher's", "寶翠園現代開放式",
             "Modern studio with harbour view. Full gym and clubhouse facilities. "
             "Saleable area 380 sqft. Walking distance to Kennedy Town MTR.",
             "Central & Western", "The Belcher's", "Tower 2, The Belcher's", 380, 490, 7800000, 0, 1, "18/F", "West"),
            ("RE-2026-003", "Family Flat at Mei Foo", "美孚新邨家庭單位",
             "Well-maintained 2-bedroom flat. Quiet block with park view. "
             "Saleable area 450 sqft. Direct MTR access at Mei Foo station.",
             "Sham Shui Po", "Mei Foo Sun Chuen", "Phase 4, Mei Foo Sun Chuen", 450, 585, 5500000, 2, 1, "8/F", "East"),
        ]

        for l in listings:
            conn.execute(
                """INSERT INTO listings
                   (reference_code, title_en, title_zh, description_master,
                    district, estate, address, saleable_area_sqft, gross_area_sqft,
                    price_hkd, bedrooms, bathrooms, floor, facing)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                l,
            )
            count += 1

    logger.info("Seeded %d ListingSync records", count)
    return count


def seed_tenancy_doc(db_path: str | Path) -> int:
    """Seed sample tenancies."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM tenancies").fetchone()[0]
        if existing > 0:
            return 0

        today = date.today()
        tenancies = [
            ("Flat A, 12/F, Block 3, Taikoo Shing", "太古城第三座12樓A室", "Eastern",
             "Chan Tai Man", "A123456(7)", "+85291234567",
             "Wong Siu Ming", "B654321(0)", "+85298765432",
             18000, 36000, 24, today - timedelta(days=300),
             today - timedelta(days=300) + timedelta(days=730)),
            ("Unit B, 18/F, Tower 2, The Belcher's", "寶翠園第二座18樓B室", "Central & Western",
             "Lee Ka Wai", "C789012(3)", "+85261234567",
             "Cheung Wing Yan", "D345678(9)", "+85268765432",
             25000, 50000, 24, today - timedelta(days=600),
             today - timedelta(days=600) + timedelta(days=730)),
        ]

        for t in tenancies:
            start = t[11]
            end = t[12]
            conn.execute(
                """INSERT INTO tenancies
                   (property_address, property_address_zh, district,
                    landlord_name, landlord_hkid, landlord_phone,
                    tenant_name, tenant_hkid, tenant_phone,
                    monthly_rent, deposit_amount, term_months,
                    start_date, end_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8],
                 t[9], t[10], t[11], start.isoformat(), end.isoformat()),
            )
            count += 1

    logger.info("Seeded %d TenancyDoc records", count)
    return count


def seed_viewing_bot(db_path: str | Path) -> int:
    """Seed sample viewings."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM viewings").fetchone()[0]
        if existing > 0:
            return 0

        today = date.today()
        viewings = [
            ("RE-2026-001", "Block 3, Taikoo Shing", "Eastern",
             "Li Wei", "+85295551234", "+85291234567", "+85261110000",
             datetime.combine(today, datetime.min.time().replace(hour=10, minute=30)),
             "confirmed", True, True),
            ("RE-2026-002", "Tower 2, The Belcher's", "Central & Western",
             "Sarah Chen", "+85295552345", "+85261234567", "+85261110000",
             datetime.combine(today, datetime.min.time().replace(hour=14, minute=0)),
             "pending", False, False),
            ("RE-2026-003", "Phase 4, Mei Foo Sun Chuen", "Sham Shui Po",
             "Tom Ng", "+85295553456", "+85268765432", "+85261110000",
             datetime.combine(today, datetime.min.time().replace(hour=16, minute=30)),
             "pending", True, False),
        ]

        for v in viewings:
            confirmed_dt = v[7] if v[8] == "confirmed" else None
            conn.execute(
                """INSERT INTO viewings
                   (property_ref, property_address, district,
                    viewer_name, viewer_phone, landlord_phone, agent_phone,
                    proposed_datetime, status, viewer_confirmed, landlord_confirmed,
                    confirmed_datetime)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (v[0], v[1], v[2], v[3], v[4], v[5], v[6],
                 v[7].isoformat(), v[8], v[9], v[10],
                 confirmed_dt.isoformat() if confirmed_dt else None),
            )
            count += 1

    logger.info("Seeded %d ViewingBot records", count)
    return count


def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "property_gpt": seed_property_gpt(db_paths["property_gpt"]),
        "listing_sync": seed_listing_sync(db_paths["listing_sync"]),
        "tenancy_doc": seed_tenancy_doc(db_paths["tenancy_doc"]),
        "viewing_bot": seed_viewing_bot(db_paths["viewing_bot"]),
    }
