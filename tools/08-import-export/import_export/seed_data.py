"""Demo data seeder for the Import/Export Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.import-export.seed")


# ---------------------------------------------------------------------------
# TradeDoc AI
# ---------------------------------------------------------------------------

SAMPLE_PRODUCTS = [
    {
        "description_en": "Cotton T-shirts, knitted, for men",
        "description_tc": "男裝針織棉質T恤",
        "hs_code": "61091000",
        "hs_description": "T-shirts, singlets and other vests, of cotton, knitted or crocheted",
        "is_strategic": False,
        "is_dutiable": False,
        "unit_of_measurement": "pieces",
        "typical_origin": "China",
    },
    {
        "description_en": "Semiconductor manufacturing equipment",
        "description_tc": "半導體製造設備",
        "hs_code": "84862000",
        "hs_description": "Machines for manufacture of semiconductor devices or ICs",
        "is_strategic": True,
        "strategic_category": "Dual-use goods",
        "is_dutiable": False,
        "unit_of_measurement": "units",
        "typical_origin": "Japan",
    },
    {
        "description_en": "Red wine, Bordeaux, 750ml bottles",
        "description_tc": "波爾多紅酒 750毫升樽",
        "hs_code": "22042100",
        "hs_description": "Wine of fresh grapes, in containers holding 2L or less",
        "is_strategic": False,
        "is_dutiable": True,
        "unit_of_measurement": "litres",
        "typical_origin": "France",
    },
    {
        "description_en": "Stainless steel kitchen utensils",
        "description_tc": "不鏽鋼廚具",
        "hs_code": "82151000",
        "hs_description": "Sets of assorted articles containing at least one article plated with precious metal",
        "is_strategic": False,
        "is_dutiable": False,
        "unit_of_measurement": "sets",
        "typical_origin": "China",
    },
]

SAMPLE_DECLARATIONS = [
    {
        "declaration_type": "import",
        "reference_number": "TDEC-2026-IM-001",
        "shipper": "Guangzhou Textile Co Ltd",
        "consignee": "HK Trade House Ltd",
        "country_of_origin": "China",
        "transport_mode": "sea",
        "vessel_flight": "COSCO Shipping Galaxy V.2604",
        "total_value": 125000.00,
        "currency": "USD",
        "filing_status": "filed",
    },
    {
        "declaration_type": "re_export",
        "reference_number": "TDEC-2026-RE-001",
        "shipper": "HK Trade House Ltd",
        "consignee": "European Imports GmbH",
        "country_of_destination": "Germany",
        "transport_mode": "sea",
        "vessel_flight": "Maersk Eindhoven V.2608",
        "total_value": 145000.00,
        "currency": "EUR",
        "filing_status": "draft",
    },
]


def seed_trade_doc_ai(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if existing > 0:
            logger.info("TradeDoc AI already has data, skipping seed")
            return 0

        for p in SAMPLE_PRODUCTS:
            conn.execute(
                """INSERT INTO products (description_en, description_tc, hs_code, hs_description,
                   is_strategic, strategic_category, is_dutiable, unit_of_measurement, typical_origin)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (p["description_en"], p["description_tc"], p["hs_code"], p["hs_description"],
                 p.get("is_strategic", False), p.get("strategic_category"),
                 p.get("is_dutiable", False), p["unit_of_measurement"], p["typical_origin"]),
            )
            count += 1

        for d in SAMPLE_DECLARATIONS:
            deadline = (date.today() + timedelta(days=14)).isoformat()
            conn.execute(
                """INSERT INTO trade_declarations
                   (declaration_type, reference_number, shipper, consignee,
                    country_of_origin, country_of_destination, transport_mode,
                    vessel_flight, total_value, currency, filing_status, filing_deadline)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d["declaration_type"], d["reference_number"], d["shipper"],
                 d["consignee"], d.get("country_of_origin"), d.get("country_of_destination"),
                 d["transport_mode"], d["vessel_flight"], d["total_value"],
                 d["currency"], d["filing_status"], deadline),
            )
            count += 1

    logger.info("Seeded %d TradeDoc AI records", count)
    return count


# ---------------------------------------------------------------------------
# SupplierBot
# ---------------------------------------------------------------------------

SAMPLE_SUPPLIERS = [
    {
        "company_name_en": "Shenzhen Golden Electronics Co Ltd",
        "company_name_cn": "深圳金科電子有限公司",
        "factory_location": "Shenzhen, Guangdong",
        "contact_person": "王明",
        "wechat_id": "wang_ming_sz",
        "phone": "+8613800001111",
        "product_categories": json.dumps(["Electronics", "LED Components"]),
        "payment_terms": "30% deposit, 70% before shipping",
    },
    {
        "company_name_en": "Dongguan Great Textile Factory",
        "company_name_cn": "東莞大成紡織廠",
        "factory_location": "Dongguan, Guangdong",
        "contact_person": "李芳",
        "wechat_id": "li_fang_dg",
        "phone": "+8613900002222",
        "product_categories": json.dumps(["Textiles", "Garments"]),
        "payment_terms": "T/T 30 days",
    },
    {
        "company_name_en": "Guangzhou Precision Mould Co",
        "company_name_cn": "廣州精密模具有限公司",
        "factory_location": "Guangzhou, Guangdong",
        "contact_person": "陳偉",
        "wechat_id": "chen_wei_gz",
        "phone": "+8613600003333",
        "product_categories": json.dumps(["Moulds", "Plastic Injection"]),
        "payment_terms": "50% deposit, 50% on delivery",
    },
]

SAMPLE_ORDERS = [
    {
        "supplier_idx": 0,
        "order_reference": "PO-2026-001",
        "product_description": "LED strip lights, 5m roll, warm white",
        "quantity": 5000,
        "unit_price": 2.50,
        "currency": "USD",
        "production_status": "in_production",
        "payment_status": "deposit_paid",
    },
    {
        "supplier_idx": 1,
        "order_reference": "PO-2026-002",
        "product_description": "Cotton T-shirts, assorted colours, S-XL",
        "quantity": 10000,
        "unit_price": 3.20,
        "currency": "USD",
        "production_status": "qc_pending",
        "payment_status": "deposit_paid",
    },
]

SAMPLE_GLOSSARY = [
    ("mould", "模具", "模具", "manufacturing", "Tool used to shape materials"),
    ("sample", "样品", "樣品", "production", "Pre-production sample"),
    ("quality control", "质检", "質檢", "quality", "Inspection process"),
    ("shipping", "出货", "出貨", "logistics", "Dispatch of goods"),
    ("deposit", "定金", "訂金", "payment", "Initial payment"),
    ("balance payment", "尾款", "尾款", "payment", "Final payment before shipping"),
    ("packing list", "装箱单", "裝箱單", "logistics", "List of goods in shipment"),
    ("bill of lading", "提单", "提單", "logistics", "Shipping document"),
    ("letter of credit", "信用证", "信用證", "payment", "Bank-guaranteed payment"),
    ("telegraphic transfer", "电汇", "電匯", "payment", "Wire transfer"),
]


def seed_supplier_bot(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        if existing > 0:
            return 0

        for s in SAMPLE_SUPPLIERS:
            conn.execute(
                """INSERT INTO suppliers
                   (company_name_en, company_name_cn, factory_location, contact_person,
                    wechat_id, phone, product_categories, payment_terms)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (s["company_name_en"], s["company_name_cn"], s["factory_location"],
                 s["contact_person"], s["wechat_id"], s["phone"],
                 s["product_categories"], s["payment_terms"]),
            )
            count += 1

        supplier_ids = [r[0] for r in conn.execute("SELECT id FROM suppliers ORDER BY id").fetchall()]

        for o in SAMPLE_ORDERS:
            sid = supplier_ids[o["supplier_idx"]]
            conn.execute(
                """INSERT INTO orders
                   (supplier_id, order_reference, product_description, quantity,
                    unit_price, currency, order_date, expected_delivery,
                    production_status, payment_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (sid, o["order_reference"], o["product_description"], o["quantity"],
                 o["unit_price"], o["currency"],
                 (date.today() - timedelta(days=14)).isoformat(),
                 (date.today() + timedelta(days=21)).isoformat(),
                 o["production_status"], o["payment_status"]),
            )
            count += 1

        for en, sc, tc, cat, ctx in SAMPLE_GLOSSARY:
            conn.execute(
                "INSERT INTO glossary (term_en, term_sc, term_tc, category, context) VALUES (?,?,?,?,?)",
                (en, sc, tc, cat, ctx),
            )
            count += 1

    logger.info("Seeded %d SupplierBot records", count)
    return count


# ---------------------------------------------------------------------------
# FXInvoice
# ---------------------------------------------------------------------------

SAMPLE_CUSTOMERS = [
    {
        "company_name": "European Imports GmbH",
        "contact_person": "Hans Mueller",
        "email": "hans@euroimports.de",
        "phone": "+4930123456",
        "address": "Friedrichstrasse 100, Berlin, Germany",
        "default_currency": "EUR",
        "payment_terms_days": 60,
    },
    {
        "company_name": "USA Trading Corp",
        "contact_person": "John Smith",
        "email": "john@usatrading.com",
        "phone": "+12025551234",
        "address": "123 Commerce St, New York, NY 10001, USA",
        "default_currency": "USD",
        "payment_terms_days": 30,
    },
    {
        "company_name": "Japan Electronics Inc",
        "contact_person": "Tanaka Yuki",
        "email": "tanaka@jpelec.co.jp",
        "phone": "+81312345678",
        "address": "Chuo-ku, Tokyo, Japan",
        "default_currency": "JPY",
        "payment_terms_days": 45,
    },
]

SAMPLE_FX_RATES = [
    ("HKD", "USD", 0.1282, "exchangerate-api"),
    ("HKD", "CNH", 0.9310, "hkma"),
    ("HKD", "EUR", 0.1180, "ecb"),
    ("HKD", "GBP", 0.1015, "ecb"),
    ("HKD", "JPY", 19.45, "ecb"),
]


def seed_fx_invoice(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if existing > 0:
            return 0

        for c in SAMPLE_CUSTOMERS:
            conn.execute(
                """INSERT INTO customers
                   (company_name, contact_person, email, phone, address,
                    default_currency, payment_terms_days)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["company_name"], c["contact_person"], c["email"], c["phone"],
                 c["address"], c["default_currency"], c["payment_terms_days"]),
            )
            count += 1

        for base, target, rate, source in SAMPLE_FX_RATES:
            conn.execute(
                "INSERT INTO fx_rates (base_currency, target_currency, rate, source) VALUES (?,?,?,?)",
                (base, target, rate, source),
            )
            count += 1

        conn.execute(
            """INSERT INTO bank_accounts (bank_name, account_number, currency, account_type, swift_code)
               VALUES (?,?,?,?,?)""",
            ("HSBC Hong Kong", "400-123456-001", "HKD", "current", "HSBCHKHH"),
        )
        conn.execute(
            """INSERT INTO bank_accounts (bank_name, account_number, currency, account_type, swift_code)
               VALUES (?,?,?,?,?)""",
            ("HSBC Hong Kong", "400-123456-840", "USD", "current", "HSBCHKHH"),
        )
        count += 2

        customer_ids = [r[0] for r in conn.execute("SELECT id FROM customers ORDER BY id").fetchall()]
        conn.execute(
            """INSERT INTO invoices
               (invoice_number, customer_id, invoice_type, invoice_date, due_date,
                currency, subtotal, total, hkd_equivalent, fx_rate_used, payment_method, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("INV-2026-0001", customer_ids[0], "sales",
             (date.today() - timedelta(days=30)).isoformat(),
             (date.today() + timedelta(days=30)).isoformat(),
             "EUR", 18500.00, 18500.00, 156780.00, 8.475, "T/T", "sent"),
        )
        conn.execute(
            """INSERT INTO invoices
               (invoice_number, customer_id, invoice_type, invoice_date, due_date,
                currency, subtotal, total, hkd_equivalent, fx_rate_used, payment_method, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("INV-2026-0002", customer_ids[1], "sales",
             (date.today() - timedelta(days=7)).isoformat(),
             (date.today() + timedelta(days=23)).isoformat(),
             "USD", 52000.00, 52000.00, 405600.00, 7.80, "T/T", "sent"),
        )
        count += 2

    logger.info("Seeded %d FXInvoice records", count)
    return count


# ---------------------------------------------------------------------------
# StockReconcile
# ---------------------------------------------------------------------------

SAMPLE_SHIPMENTS = [
    {
        "shipment_reference": "SH-2026-001",
        "bl_number": "COSU6262626262",
        "bl_type": "master",
        "vessel_name": "COSCO Shipping Galaxy",
        "voyage": "V.2604",
        "origin_port": "Yantian, Shenzhen",
        "container_numbers": json.dumps(["COSU1234567", "COSU7654321"]),
        "load_type": "FCL",
        "consignee": "HK Trade House Ltd",
        "status": "at_warehouse",
    },
    {
        "shipment_reference": "SH-2026-002",
        "bl_number": "MAEU1234567890",
        "bl_type": "master",
        "vessel_name": "Maersk Eindhoven",
        "voyage": "V.2608",
        "origin_port": "Nansha, Guangzhou",
        "container_numbers": json.dumps(["MAEU9999888"]),
        "load_type": "LCL",
        "consignee": "Multiple consignees",
        "status": "arrived",
    },
]


def seed_stock_reconcile(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        if existing > 0:
            return 0

        for s in SAMPLE_SHIPMENTS:
            conn.execute(
                """INSERT INTO shipments
                   (shipment_reference, bl_number, bl_type, vessel_name, voyage,
                    origin_port, arrival_date, container_numbers, load_type, consignee, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (s["shipment_reference"], s["bl_number"], s["bl_type"], s["vessel_name"],
                 s["voyage"], s["origin_port"],
                 (date.today() - timedelta(days=3)).isoformat(),
                 s["container_numbers"], s["load_type"], s["consignee"], s["status"]),
            )
            count += 1

        shipment_ids = [r[0] for r in conn.execute("SELECT id FROM shipments ORDER BY id").fetchall()]

        manifest_data = [
            (shipment_ids[0], "COSU1234567", "Cotton T-shirts, blue, size M", "TS-BLU-M", 2000, "pieces", 600.0, 40, 2),
            (shipment_ids[0], "COSU1234567", "Cotton T-shirts, blue, size L", "TS-BLU-L", 2000, "pieces", 640.0, 40, 2),
            (shipment_ids[0], "COSU7654321", "LED strip lights, warm white, 5m", "LED-WW-5M", 5000, "rolls", 750.0, 100, 4),
        ]
        for sid, ctn, desc, sku, qty, unit, wt, cartons, pallets in manifest_data:
            conn.execute(
                """INSERT INTO manifest_items
                   (shipment_id, container_number, item_description, sku, quantity, unit, weight_kg, carton_count, pallet_count)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (sid, ctn, desc, sku, qty, unit, wt, cartons, pallets),
            )
            count += 1

    logger.info("Seeded %d StockReconcile records", count)
    return count


# ---------------------------------------------------------------------------
# Seed all
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "trade_doc_ai": seed_trade_doc_ai(db_paths["trade_doc_ai"]),
        "supplier_bot": seed_supplier_bot(db_paths["supplier_bot"]),
        "fx_invoice": seed_fx_invoice(db_paths["fx_invoice"]),
        "stock_reconcile": seed_stock_reconcile(db_paths["stock_reconcile"]),
    }
