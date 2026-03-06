"""Demo data seeder for the Accounting Dashboard."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.seed")


# ---------------------------------------------------------------------------
# InvoiceOCR Pro
# ---------------------------------------------------------------------------

SAMPLE_SUPPLIERS = [
    {"name": "Pacific Office Supplies Ltd", "br_number": "12345678-000-01-26-7",
     "default_category": "Office Supplies", "default_account_code": "5800", "currency": "HKD"},
    {"name": "CLP Power Hong Kong Ltd", "br_number": "00023456-000-01-26-2",
     "default_category": "Utilities", "default_account_code": "5700", "currency": "HKD"},
    {"name": "Sino Realty Management Ltd", "br_number": "34567890-000-01-26-5",
     "default_category": "Rent & Rates", "default_account_code": "5100", "currency": "HKD"},
    {"name": "深圳市華通科技有限公司", "br_number": None,
     "default_category": "Materials", "default_account_code": "4100", "currency": "CNH"},
    {"name": "HSBC MPF Trustee", "br_number": None,
     "default_category": "MPF Contributions", "default_account_code": "5210", "currency": "HKD"},
]

SAMPLE_INVOICES = [
    {"supplier_idx": 0, "invoice_number": "POS-2026-0142", "invoice_date": date.today() - timedelta(days=5),
     "currency": "HKD", "subtotal": 2450.00, "tax_amount": 0, "total_amount": 2450.00,
     "source": "email", "status": "approved", "confidence": 0.94, "category": "Office Supplies"},
    {"supplier_idx": 1, "invoice_number": "CLP-7891234", "invoice_date": date.today() - timedelta(days=12),
     "currency": "HKD", "subtotal": 3872.50, "tax_amount": 0, "total_amount": 3872.50,
     "source": "scan", "status": "pending_review", "confidence": 0.88, "category": "Utilities"},
    {"supplier_idx": 2, "invoice_number": "SINO-R-2026-03", "invoice_date": date.today() - timedelta(days=1),
     "currency": "HKD", "subtotal": 45000.00, "tax_amount": 0, "total_amount": 45000.00,
     "source": "email", "status": "approved", "confidence": 0.97, "category": "Rent & Rates"},
    {"supplier_idx": 3, "invoice_number": "HT-20260215-008", "invoice_date": date.today() - timedelta(days=20),
     "currency": "CNH", "subtotal": 15800.00, "tax_amount": 2054.00, "total_amount": 17854.00,
     "source": "whatsapp", "status": "pending_review", "confidence": 0.82, "category": "Materials"},
    {"supplier_idx": 0, "invoice_number": "POS-2026-0138", "invoice_date": date.today() - timedelta(days=35),
     "currency": "HKD", "subtotal": 1280.00, "tax_amount": 0, "total_amount": 1280.00,
     "source": "scan", "status": "approved", "confidence": 0.91, "category": "Office Supplies"},
    {"supplier_idx": 4, "invoice_number": "MPF-2026-02", "invoice_date": date.today() - timedelta(days=15),
     "currency": "HKD", "subtotal": 15000.00, "tax_amount": 0, "total_amount": 15000.00,
     "source": "email", "status": "approved", "confidence": 0.96, "category": "MPF Contributions"},
    {"supplier_idx": 1, "invoice_number": "CLP-7891100", "invoice_date": date.today() - timedelta(days=42),
     "currency": "HKD", "subtotal": 4105.80, "tax_amount": 0, "total_amount": 4105.80,
     "source": "scan", "status": "pushed", "confidence": 0.90, "category": "Utilities"},
    {"supplier_idx": 2, "invoice_number": "SINO-R-2026-02", "invoice_date": date.today() - timedelta(days=31),
     "currency": "HKD", "subtotal": 45000.00, "tax_amount": 0, "total_amount": 45000.00,
     "source": "email", "status": "pushed", "confidence": 0.97, "category": "Rent & Rates"},
]

SAMPLE_CATEGORY_RULES = [
    {"match_type": "supplier", "match_value": "CLP Power", "category": "Utilities", "account_code": "5700"},
    {"match_type": "supplier", "match_value": "Sino Realty", "category": "Rent & Rates", "account_code": "5100"},
    {"match_type": "supplier", "match_value": "HSBC MPF", "category": "MPF Contributions", "account_code": "5210"},
    {"match_type": "description", "match_value": "stationery", "category": "Office Supplies", "account_code": "5800"},
    {"match_type": "description", "match_value": "taxi", "category": "Travel", "account_code": "5600"},
    {"match_type": "description", "match_value": "dinner", "category": "Entertainment", "account_code": "5500"},
]


def seed_invoice_ocr(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        if existing > 0:
            logger.info("InvoiceOCR already has data, skipping seed")
            return 0

        for s in SAMPLE_SUPPLIERS:
            conn.execute(
                """INSERT INTO suppliers (name, br_number, default_category, default_account_code, currency)
                   VALUES (?,?,?,?,?)""",
                (s["name"], s["br_number"], s["default_category"], s["default_account_code"], s["currency"]),
            )
            count += 1

        supplier_ids = [r[0] for r in conn.execute("SELECT id FROM suppliers ORDER BY id").fetchall()]

        for inv in SAMPLE_INVOICES:
            sid = supplier_ids[inv["supplier_idx"]]
            supplier = SAMPLE_SUPPLIERS[inv["supplier_idx"]]
            conn.execute(
                """INSERT INTO invoices
                   (supplier_name, invoice_number, invoice_date, currency,
                    subtotal, tax_amount, total_amount, source, status,
                    ocr_confidence, category, account_code, source_file)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (supplier["name"], inv["invoice_number"], inv["invoice_date"].isoformat(),
                 inv["currency"], inv["subtotal"], inv["tax_amount"], inv["total_amount"],
                 inv["source"], inv["status"], inv["confidence"], inv["category"],
                 supplier["default_account_code"], f"/demo/{inv['invoice_number']}.pdf"),
            )
            count += 1

        for rule in SAMPLE_CATEGORY_RULES:
            conn.execute(
                """INSERT INTO category_rules (match_type, match_value, category, account_code)
                   VALUES (?,?,?,?)""",
                (rule["match_type"], rule["match_value"], rule["category"], rule["account_code"]),
            )
            count += 1

    logger.info("Seeded %d InvoiceOCR records", count)
    return count


# ---------------------------------------------------------------------------
# ReconcileAgent
# ---------------------------------------------------------------------------

def _sample_bank_transactions() -> list[dict]:
    """Generate sample HSBC bank transactions."""
    base = date.today() - timedelta(days=30)
    txns = []
    descriptions = [
        ("AUTOPAY-SINO REALTY", 0, 45000.00, "autopay"),
        ("FPS-PACIFIC OFFICE", 0, 2450.00, "fps"),
        ("CLP POWER HK", 0, 3872.50, "autopay"),
        ("CHQ DEP 100234", 58000.00, 0, "cheque"),
        ("TT FROM OVERSEAS CLIENT", 125000.00, 0, "tt"),
        ("FASTER PAYMENT - WONG", 8500.00, 0, "fps"),
        ("MONTHLY MAINTENANCE FEE", 0, 150.00, "charge"),
        ("FPS FEE", 0, 2.00, "charge"),
        ("INT ON CURRENT A/C", 12.35, 0, "interest"),
        ("AUTOPAY-HSBC MPF", 0, 15000.00, "autopay"),
        ("TT TO SHENZHEN HUATONG", 0, 17854.00, "tt"),
        ("FPS-ABC CONSULTING", 0, 5800.00, "fps"),
        ("CHQ DEP 100235", 35000.00, 0, "cheque"),
        ("CLP POWER HK", 0, 4105.80, "autopay"),
        ("AUTOPAY-SINO REALTY", 0, 45000.00, "autopay"),
    ]
    balance = 250000.00
    for i, (desc, cr, dr, ttype) in enumerate(descriptions):
        balance = balance + cr - dr
        txns.append({
            "bank_name": "HSBC", "transaction_date": (base + timedelta(days=i * 2)).isoformat(),
            "description": desc, "debit": dr, "credit": cr, "balance": round(balance, 2),
            "currency": "HKD", "transaction_type": ttype,
        })
    return txns


def _sample_ledger_entries() -> list[dict]:
    """Generate sample ledger entries (some match bank, some don't)."""
    base = date.today() - timedelta(days=30)
    entries = [
        {"entry_date": (base + timedelta(days=0)).isoformat(), "description": "Rent - March",
         "debit": 45000.00, "credit": 0, "account_code": "5100", "reference": "SINO-R-2026-03"},
        {"entry_date": (base + timedelta(days=2)).isoformat(), "description": "Office supplies",
         "debit": 2450.00, "credit": 0, "account_code": "5800", "reference": "POS-2026-0142"},
        {"entry_date": (base + timedelta(days=4)).isoformat(), "description": "Electricity",
         "debit": 3872.50, "credit": 0, "account_code": "5700", "reference": "CLP-7891234"},
        {"entry_date": (base + timedelta(days=5)).isoformat(), "description": "Sales receipt - Wong Trading",
         "debit": 0, "credit": 58000.00, "account_code": "4000", "reference": "INV-2026-045"},
        {"entry_date": (base + timedelta(days=8)).isoformat(), "description": "Overseas client payment",
         "debit": 0, "credit": 125000.00, "account_code": "4000", "reference": "INV-2026-038"},
        {"entry_date": (base + timedelta(days=10)).isoformat(), "description": "Payment from Wong",
         "debit": 0, "credit": 8500.00, "account_code": "4000", "reference": "INV-2026-050"},
        {"entry_date": (base + timedelta(days=18)).isoformat(), "description": "MPF contribution - Feb",
         "debit": 15000.00, "credit": 0, "account_code": "5210", "reference": "MPF-2026-02"},
        {"entry_date": (base + timedelta(days=20)).isoformat(), "description": "Supplier payment - Shenzhen",
         "debit": 17854.00, "credit": 0, "account_code": "4100", "reference": "HT-20260215-008"},
        {"entry_date": (base + timedelta(days=22)).isoformat(), "description": "Consulting fees",
         "debit": 5800.00, "credit": 0, "account_code": "5300", "reference": "ABC-2026-03"},
        {"entry_date": (base + timedelta(days=24)).isoformat(), "description": "Sales receipt - Lee & Partners",
         "debit": 0, "credit": 35000.00, "account_code": "4000", "reference": "INV-2026-052"},
        {"entry_date": (base + timedelta(days=26)).isoformat(), "description": "Electricity - Jan",
         "debit": 4105.80, "credit": 0, "account_code": "5700", "reference": "CLP-7891100"},
        {"entry_date": (base + timedelta(days=28)).isoformat(), "description": "Rent - Feb",
         "debit": 45000.00, "credit": 0, "account_code": "5100", "reference": "SINO-R-2026-02"},
        # Unmatched ledger entries (no corresponding bank transaction)
        {"entry_date": (base + timedelta(days=15)).isoformat(), "description": "Staff dinner",
         "debit": 2800.00, "credit": 0, "account_code": "5500", "reference": "EXP-2026-018"},
        {"entry_date": (base + timedelta(days=25)).isoformat(), "description": "Taxi - client visit",
         "debit": 350.00, "credit": 0, "account_code": "5600", "reference": "EXP-2026-022"},
    ]
    return entries


def seed_reconcile_agent(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        if existing > 0:
            logger.info("ReconcileAgent already has data, skipping seed")
            return 0

        for txn in _sample_bank_transactions():
            conn.execute(
                """INSERT INTO bank_transactions
                   (bank_name, transaction_date, description, debit, credit, balance,
                    currency, transaction_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (txn["bank_name"], txn["transaction_date"], txn["description"],
                 txn["debit"], txn["credit"], txn["balance"],
                 txn["currency"], txn["transaction_type"]),
            )
            count += 1

        for entry in _sample_ledger_entries():
            conn.execute(
                """INSERT INTO ledger_entries
                   (entry_date, description, debit, credit, account_code, reference, currency)
                   VALUES (?,?,?,?,?,?,?)""",
                (entry["entry_date"], entry["description"], entry["debit"],
                 entry["credit"], entry["account_code"], entry["reference"], "HKD"),
            )
            count += 1

    logger.info("Seeded %d ReconcileAgent records", count)
    return count


# ---------------------------------------------------------------------------
# FXTracker
# ---------------------------------------------------------------------------

def _sample_exchange_rates() -> list[dict]:
    """Generate 30 days of exchange rate history."""
    rates_data = []
    base = date.today() - timedelta(days=30)
    currency_base_rates = {
        "USD": {"mid": 7.8100, "spread": 0.0050},
        "CNH": {"mid": 1.0750, "spread": 0.0080},
        "EUR": {"mid": 8.4500, "spread": 0.0200},
        "GBP": {"mid": 9.8200, "spread": 0.0250},
        "JPY": {"mid": 0.0520, "spread": 0.0005},
    }
    import random
    random.seed(42)
    for day_offset in range(30):
        d = base + timedelta(days=day_offset)
        if d.weekday() >= 5:
            continue
        for ccy, info in currency_base_rates.items():
            drift = random.uniform(-info["spread"], info["spread"])
            mid = round(info["mid"] + drift, 4)
            rates_data.append({
                "date": d.isoformat(), "target_currency": ccy,
                "buying_tt": round(mid - info["spread"] / 2, 4),
                "selling_tt": round(mid + info["spread"] / 2, 4),
                "mid_rate": mid,
            })
    return rates_data


SAMPLE_FX_TRANSACTIONS = [
    {"transaction_date": (date.today() - timedelta(days=20)).isoformat(),
     "description": "Purchase from Shenzhen Huatong", "currency": "CNH",
     "foreign_amount": 17854.00, "exchange_rate": 1.0742, "hkd_amount": 19179.42,
     "transaction_type": "payable", "nature": "revenue", "reference": "HT-20260215-008",
     "is_settled": True, "settled_date": (date.today() - timedelta(days=10)).isoformat(),
     "settlement_rate": 1.0768, "settlement_hkd": 19225.90, "realized_gain_loss": -46.48},
    {"transaction_date": (date.today() - timedelta(days=15)).isoformat(),
     "description": "Invoice to UK client - Smith & Co", "currency": "GBP",
     "foreign_amount": 5000.00, "exchange_rate": 9.8150, "hkd_amount": 49075.00,
     "transaction_type": "receivable", "nature": "revenue", "reference": "INV-UK-2026-003",
     "is_settled": False},
    {"transaction_date": (date.today() - timedelta(days=10)).isoformat(),
     "description": "USD deposit from US distributor", "currency": "USD",
     "foreign_amount": 15000.00, "exchange_rate": 7.8095, "hkd_amount": 117142.50,
     "transaction_type": "receivable", "nature": "revenue", "reference": "INV-US-2026-012",
     "is_settled": False},
    {"transaction_date": (date.today() - timedelta(days=5)).isoformat(),
     "description": "JPY payment for trade show booth", "currency": "JPY",
     "foreign_amount": 500000.00, "exchange_rate": 0.0519, "hkd_amount": 25950.00,
     "transaction_type": "payable", "nature": "revenue", "reference": "JP-EXPO-2026",
     "is_settled": False},
    {"transaction_date": (date.today() - timedelta(days=3)).isoformat(),
     "description": "EUR payment for software license", "currency": "EUR",
     "foreign_amount": 2500.00, "exchange_rate": 8.4480, "hkd_amount": 21120.00,
     "transaction_type": "payable", "nature": "revenue", "reference": "SW-LIC-2026-Q1",
     "is_settled": False},
]

SAMPLE_RATE_ALERTS = [
    {"currency_pair": "USD/HKD", "alert_type": "above", "threshold": 7.85},
    {"currency_pair": "CNH/HKD", "alert_type": "change_pct", "threshold": 0.5},
]


def seed_fx_tracker(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM exchange_rates").fetchone()[0]
        if existing > 0:
            logger.info("FXTracker already has data, skipping seed")
            return 0

        for rate in _sample_exchange_rates():
            conn.execute(
                """INSERT OR IGNORE INTO exchange_rates
                   (date, target_currency, buying_tt, selling_tt, mid_rate)
                   VALUES (?,?,?,?,?)""",
                (rate["date"], rate["target_currency"], rate["buying_tt"],
                 rate["selling_tt"], rate["mid_rate"]),
            )
            count += 1

        for tx in SAMPLE_FX_TRANSACTIONS:
            conn.execute(
                """INSERT INTO fx_transactions
                   (transaction_date, description, currency, foreign_amount,
                    exchange_rate, hkd_amount, transaction_type, nature, reference,
                    is_settled, settled_date, settlement_rate, settlement_hkd,
                    realized_gain_loss)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (tx["transaction_date"], tx["description"], tx["currency"],
                 tx["foreign_amount"], tx["exchange_rate"], tx["hkd_amount"],
                 tx["transaction_type"], tx["nature"], tx["reference"],
                 tx.get("is_settled", False), tx.get("settled_date"),
                 tx.get("settlement_rate"), tx.get("settlement_hkd"),
                 tx.get("realized_gain_loss")),
            )
            count += 1

        for alert in SAMPLE_RATE_ALERTS:
            conn.execute(
                """INSERT INTO rate_alerts (currency_pair, alert_type, threshold)
                   VALUES (?,?,?)""",
                (alert["currency_pair"], alert["alert_type"], alert["threshold"]),
            )
            count += 1

    logger.info("Seeded %d FXTracker records", count)
    return count


# ---------------------------------------------------------------------------
# TaxCalendar Bot
# ---------------------------------------------------------------------------

SAMPLE_TAX_CLIENTS = [
    {"company_name": "Golden Dragon Trading Ltd", "br_number": "45678901",
     "year_end_month": 12, "ird_file_number": "23/12345/01",
     "company_type": "corporation", "assigned_accountant": "Alice Chan",
     "accountant_phone": "+85291234567", "partner": "David Wong",
     "partner_phone": "+85298765432"},
    {"company_name": "Pacific Tech Solutions Ltd", "br_number": "56789012",
     "year_end_month": 3, "ird_file_number": "23/23456/01",
     "company_type": "corporation", "assigned_accountant": "Alice Chan",
     "accountant_phone": "+85291234567", "partner": "David Wong",
     "partner_phone": "+85298765432"},
    {"company_name": "Harbour View Consulting", "br_number": "67890123",
     "year_end_month": 6, "ird_file_number": "23/34567/01",
     "company_type": "partnership", "assigned_accountant": "Bob Lee",
     "accountant_phone": "+85292345678", "partner": "David Wong",
     "partner_phone": "+85298765432"},
    {"company_name": "Star Logistics (HK) Ltd", "br_number": "78901234",
     "year_end_month": 12, "ird_file_number": "23/45678/01",
     "company_type": "corporation", "assigned_accountant": "Bob Lee",
     "accountant_phone": "+85292345678", "partner": "Emily Lau",
     "partner_phone": "+85296543210"},
    {"company_name": "Lee Wai Man", "br_number": "89012345",
     "year_end_month": 3, "ird_file_number": "10/56789/02",
     "company_type": "sole_proprietor", "assigned_accountant": "Alice Chan",
     "accountant_phone": "+85291234567", "partner": "Emily Lau",
     "partner_phone": "+85296543210"},
    {"company_name": "Jade Garden Restaurant Ltd", "br_number": "90123456",
     "year_end_month": 3, "ird_file_number": "23/67890/01",
     "company_type": "corporation", "assigned_accountant": "Carol Ng",
     "accountant_phone": "+85293456789", "partner": "David Wong",
     "partner_phone": "+85298765432"},
    {"company_name": "Summit Engineering Ltd", "br_number": "01234567",
     "year_end_month": 9, "ird_file_number": "23/78901/01",
     "company_type": "corporation", "assigned_accountant": "Carol Ng",
     "accountant_phone": "+85293456789", "partner": "Emily Lau",
     "partner_phone": "+85296543210"},
    {"company_name": "Bright Future Education Centre", "br_number": "11223344",
     "year_end_month": 8, "ird_file_number": "23/89012/01",
     "company_type": "corporation", "assigned_accountant": "Bob Lee",
     "accountant_phone": "+85292345678", "partner": "David Wong",
     "partner_phone": "+85298765432"},
]


def _ird_code(year_end_month: int) -> str:
    """Determine IRD code category from year-end month."""
    if year_end_month == 12:
        return "D"
    elif year_end_month == 3:
        return "M"
    else:
        return "N"


def seed_tax_calendar(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        if existing > 0:
            logger.info("TaxCalendar already has data, skipping seed")
            return 0

        for c in SAMPLE_TAX_CLIENTS:
            conn.execute(
                """INSERT INTO clients
                   (company_name, br_number, year_end_month, ird_file_number,
                    company_type, assigned_accountant, accountant_phone,
                    partner, partner_phone)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (c["company_name"], c["br_number"], c["year_end_month"],
                 c["ird_file_number"], c["company_type"], c["assigned_accountant"],
                 c["accountant_phone"], c["partner"], c["partner_phone"]),
            )
            count += 1

        client_ids = [r[0] for r in conn.execute("SELECT id FROM clients ORDER BY id").fetchall()]

        # Generate sample deadlines for current assessment year
        assessment_year = "2025/26"
        for i, client in enumerate(SAMPLE_TAX_CLIENTS):
            cid = client_ids[i]
            code = _ird_code(client["year_end_month"])

            # Profits Tax (BIR51/BIR52)
            form = "BIR51" if client["company_type"] == "corporation" else "BIR52"
            if code == "D":
                original_due = date(2026, 8, 15)
                extended_due = date(2026, 11, 15)
            elif code == "M":
                original_due = date(2026, 11, 15)
                extended_due = date(2027, 1, 15)
            else:
                original_due = date(2026, 5, 3)
                extended_due = date(2026, 5, 31)

            filing_status = "not_started"
            if original_due < date.today():
                filing_status = "in_progress"

            conn.execute(
                """INSERT INTO deadlines
                   (client_id, deadline_type, form_code, assessment_year,
                    original_due_date, extended_due_date, extension_type,
                    extension_status, filing_status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, "profits_tax", form, assessment_year,
                 original_due.isoformat(), extended_due.isoformat(),
                 "block", "granted", filing_status),
            )
            count += 1

            # Employer's Return (BIR56A)
            conn.execute(
                """INSERT INTO deadlines
                   (client_id, deadline_type, form_code, assessment_year,
                    original_due_date, filing_status)
                   VALUES (?,?,?,?,?,?)""",
                (cid, "employers_return", "BIR56A", assessment_year,
                 date(2026, 5, 3).isoformat(), "not_started"),
            )
            count += 1

        # Sample MPF deadlines
        for month_offset in range(3):
            d = date.today().replace(day=1) - timedelta(days=month_offset * 30)
            mpf_month = d.replace(day=1)
            due_day = 10
            due_date = (mpf_month + timedelta(days=32)).replace(day=due_day)

            conn.execute(
                """INSERT INTO mpf_deadlines
                   (client_id, period_month, contribution_due_date, amount_due, paid)
                   VALUES (?,?,?,?,?)""",
                (client_ids[0], mpf_month.isoformat(), due_date.isoformat(),
                 15000.00, month_offset > 0),
            )
            count += 1

    logger.info("Seeded %d TaxCalendar records", count)
    return count


# ---------------------------------------------------------------------------
# Seed all
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "invoice_ocr": seed_invoice_ocr(db_paths["invoice_ocr"]),
        "reconcile_agent": seed_reconcile_agent(db_paths["reconcile_agent"]),
        "fx_tracker": seed_fx_tracker(db_paths["fx_tracker"]),
        "tax_calendar": seed_tax_calendar(db_paths["tax_calendar"]),
    }
