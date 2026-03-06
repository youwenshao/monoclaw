"""Database schema initialization for all import/export tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# TradeDoc AI
# ---------------------------------------------------------------------------
TRADE_DOC_AI_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description_en TEXT NOT NULL,
    description_tc TEXT,
    hs_code TEXT,
    hs_description TEXT,
    is_strategic BOOLEAN DEFAULT FALSE,
    strategic_category TEXT,
    is_dutiable BOOLEAN DEFAULT FALSE,
    unit_of_measurement TEXT,
    typical_origin TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_declarations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_type TEXT CHECK(declaration_type IN ('import','export','re_export')),
    reference_number TEXT UNIQUE,
    shipper TEXT,
    consignee TEXT,
    country_of_origin TEXT,
    country_of_destination TEXT,
    transport_mode TEXT,
    vessel_flight TEXT,
    total_value REAL,
    currency TEXT DEFAULT 'HKD',
    filing_status TEXT CHECK(filing_status IN ('draft','filed','accepted','rejected','amended')) DEFAULT 'draft',
    filed_date TIMESTAMP,
    filing_deadline DATE,
    linked_import_id INTEGER REFERENCES trade_declarations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS declaration_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_id INTEGER REFERENCES trade_declarations(id),
    product_id INTEGER REFERENCES products(id),
    hs_code TEXT,
    quantity REAL,
    unit TEXT,
    value REAL,
    currency TEXT DEFAULT 'HKD',
    country_of_origin TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS certificates_of_origin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_id INTEGER REFERENCES trade_declarations(id),
    co_type TEXT CHECK(co_type IN ('general','cepa','asean_hk','other_preferential')),
    application_number TEXT,
    status TEXT DEFAULT 'draft',
    issued_date DATE
);

CREATE TABLE IF NOT EXISTS filing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_id INTEGER REFERENCES trade_declarations(id),
    action TEXT,
    provider TEXT CHECK(provider IN ('tradelink','becs')),
    response_code TEXT,
    response_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS hs_code_fts USING fts5(
    code, description_en, description_tc,
    tokenize='unicode61'
);
"""

# ---------------------------------------------------------------------------
# SupplierBot
# ---------------------------------------------------------------------------
SUPPLIER_BOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name_en TEXT,
    company_name_cn TEXT NOT NULL,
    factory_location TEXT,
    contact_person TEXT,
    wechat_id TEXT,
    phone TEXT,
    product_categories TEXT,
    payment_terms TEXT,
    reliability_score REAL DEFAULT 5.0,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_reference TEXT UNIQUE,
    product_description TEXT,
    quantity INTEGER,
    unit_price REAL,
    currency TEXT DEFAULT 'USD',
    order_date DATE,
    expected_delivery DATE,
    actual_delivery DATE,
    payment_status TEXT CHECK(payment_status IN ('pending_deposit','deposit_paid','balance_pending','fully_paid')) DEFAULT 'pending_deposit',
    production_status TEXT CHECK(production_status IN ('not_started','in_production','qc_pending','qc_passed','shipping','delivered','completed')) DEFAULT 'not_started',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_id INTEGER REFERENCES orders(id),
    direction TEXT CHECK(direction IN ('outbound','inbound')),
    original_text TEXT,
    translated_text TEXT,
    original_language TEXT,
    message_type TEXT CHECK(message_type IN ('text','voice','image','file')),
    extracted_data TEXT,
    channel TEXT DEFAULT 'wechat',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS status_pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_id INTEGER REFERENCES orders(id),
    ping_type TEXT,
    scheduled_time TIMESTAMP,
    sent_time TIMESTAMP,
    response_received BOOLEAN DEFAULT FALSE,
    response_time TIMESTAMP,
    follow_up_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_en TEXT,
    term_sc TEXT,
    term_tc TEXT,
    category TEXT,
    context TEXT
);
"""

# ---------------------------------------------------------------------------
# FXInvoice
# ---------------------------------------------------------------------------
FX_INVOICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    default_currency TEXT DEFAULT 'USD',
    payment_terms_days INTEGER DEFAULT 30,
    credit_limit REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    invoice_type TEXT CHECK(invoice_type IN ('sales','purchase','debit_note','credit_note')),
    invoice_date DATE,
    due_date DATE,
    currency TEXT NOT NULL,
    subtotal REAL,
    total REAL,
    hkd_equivalent REAL,
    fx_rate_used REAL,
    fx_rate_date DATE,
    payment_method TEXT,
    status TEXT CHECK(status IN ('draft','sent','partially_paid','paid','overdue','cancelled')) DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER REFERENCES invoices(id),
    description TEXT,
    quantity REAL,
    unit_price REAL,
    amount REAL,
    hs_code TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER REFERENCES invoices(id),
    payment_date DATE,
    amount REAL,
    currency TEXT,
    fx_rate_at_payment REAL,
    hkd_equivalent REAL,
    payment_method TEXT,
    bank_reference TEXT,
    fx_gain_loss REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT,
    rate REAL,
    source TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name TEXT,
    account_number TEXT,
    currency TEXT,
    account_type TEXT,
    swift_code TEXT,
    active BOOLEAN DEFAULT TRUE
);
"""

# ---------------------------------------------------------------------------
# StockReconcile
# ---------------------------------------------------------------------------
STOCK_RECONCILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_reference TEXT UNIQUE,
    bl_number TEXT,
    bl_type TEXT CHECK(bl_type IN ('master','house')),
    master_bl TEXT,
    vessel_name TEXT,
    voyage TEXT,
    origin_port TEXT,
    arrival_date DATE,
    container_numbers TEXT,
    load_type TEXT CHECK(load_type IN ('FCL','LCL')),
    consignee TEXT,
    status TEXT CHECK(status IN ('in_transit','arrived','gate_out','at_warehouse','reconciled','closed')) DEFAULT 'in_transit',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manifest_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER REFERENCES shipments(id),
    container_number TEXT,
    item_description TEXT,
    sku TEXT,
    quantity REAL,
    unit TEXT,
    weight_kg REAL,
    carton_count INTEGER,
    pallet_count INTEGER,
    source_document TEXT
);

CREATE TABLE IF NOT EXISTS warehouse_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER REFERENCES shipments(id),
    receipt_number TEXT,
    received_date DATE,
    warehouse TEXT,
    received_by TEXT
);

CREATE TABLE IF NOT EXISTS receipt_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER REFERENCES warehouse_receipts(id),
    item_description TEXT,
    sku TEXT,
    quantity_received REAL,
    unit TEXT,
    condition TEXT CHECK(condition IN ('good','damaged','partial')) DEFAULT 'good',
    damage_notes TEXT,
    photo_path TEXT
);

CREATE TABLE IF NOT EXISTS reconciliation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id INTEGER REFERENCES shipments(id),
    manifest_item_id INTEGER REFERENCES manifest_items(id),
    receipt_item_id INTEGER REFERENCES receipt_items(id),
    match_confidence REAL,
    quantity_manifest REAL,
    quantity_received REAL,
    variance REAL,
    status TEXT CHECK(status IN ('matched','shortage','overage','damaged','unmatched_manifest','unmatched_receipt')) DEFAULT 'matched',
    notes TEXT,
    reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT,
    name_cn TEXT,
    company TEXT,
    phone TEXT,
    email TEXT,
    contact_type TEXT CHECK(contact_type IN ('customer','supplier','both')) DEFAULT 'both',
    supplier_id INTEGER,
    customer_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/import-export") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/import-export") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "trade_doc_ai": db_dir / "trade_doc_ai.db",
        "supplier_bot": db_dir / "supplier_bot.db",
        "fx_invoice": db_dir / "fx_invoice.db",
        "stock_reconcile": db_dir / "stock_reconcile.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["trade_doc_ai"], TRADE_DOC_AI_SCHEMA)
    run_migrations(db_paths["supplier_bot"], SUPPLIER_BOT_SCHEMA)
    run_migrations(db_paths["fx_invoice"], FX_INVOICE_SCHEMA)
    run_migrations(db_paths["stock_reconcile"], STOCK_RECONCILE_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
