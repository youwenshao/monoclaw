# TradeDoc AI

## Overview

TradeDoc AI automates the classification of goods under the Harmonized System (HS) code framework and generates Hong Kong trade documentation including TDEC (Trade Declaration), export/import licenses, commercial invoices, and certificates of origin. It handles Hong Kong's unique re-export documentation requirements, which account for the majority of HK's trade volume. All classification runs locally via MLX for speed and data privacy.

## Target User

Hong Kong import-export traders, customs brokers, logistics coordinators, and trade compliance officers who prepare and file trade declarations and supporting documentation for goods moving through Hong Kong.

## Core Features

- **HS Code Classification**: Analyzes product descriptions and suggests the correct 8-digit HK HS code using local LLM semantic matching against the HK Trade Classification schedule, with confidence scoring
- **TDEC Generation**: Auto-populates Trade Declaration (TDEC) forms for import, export, and re-export declarations as required under the Import and Export Ordinance
- **Commercial Invoice Generator**: Creates professional commercial invoices with all fields required for HK customs clearance (shipper, consignee, HS codes, quantities, values, Incoterms)
- **Certificate of Origin**: Generates CO applications for products qualifying under HK origin rules, supporting both CEPA and general preferential CO formats
- **Strategic Commodities Screening**: Cross-references goods descriptions against the Strategic Commodities Control List (Cap 60G) and flags items requiring an export license
- **Re-Export Documentation**: Specialized workflow for HK's dominant re-export trade, linking import and re-export declarations for the same goods

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM | MLX local inference (Qwen-2.5-7B) for HS code classification and document field extraction |
| Document Generation | python-docx for Word templates; reportlab for PDF invoices; openpyxl for Excel-format TDEC data |
| Database | SQLite for product catalog, HS code reference, trade history, and document archive |
| UI | Streamlit dashboard for document preparation and filing status tracking |
| API | httpx for electronic filing submission to TDEC service providers (Tradelink, BECS) |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/trade-doc-ai/
├── app.py                       # Streamlit trade documentation dashboard
├── classification/
│   ├── hs_classifier.py         # LLM + lookup-based HS code classification
│   ├── strategic_screener.py    # Strategic commodities control list screening
│   └── hs_database.py           # HS code reference database queries
├── documents/
│   ├── tdec_generator.py        # Trade Declaration form generation
│   ├── invoice_generator.py     # Commercial invoice creation
│   ├── co_generator.py          # Certificate of Origin application
│   └── reexport_linker.py       # Re-export documentation workflow
├── filing/
│   ├── tradelink_connector.py   # Tradelink electronic filing integration
│   └── filing_tracker.py        # Submission status tracking
├── models/
│   ├── llm_handler.py           # MLX inference wrapper
│   └── prompts.py               # HS classification and extraction prompts
├── data/
│   ├── hs_codes_hk.json         # HK Harmonized System code schedule
│   └── strategic_list.json      # Strategic Commodities Control List
├── requirements.txt
└── README.md
```

### Workspace Data Directory

```
~/OpenClawWorkspace/trade-doc-ai/
├── trade.db                     # SQLite database
├── documents/                   # Generated trade documents (TDEC, invoices, COs)
├── uploads/                     # Uploaded source documents for processing
├── templates/                   # Custom document templates
└── exports/                     # Exported reports and filed declarations
```

## Key Integrations

- **Tradelink / BECS**: Electronic TDEC filing service providers — submit declarations electronically as required by HK law
- **Local LLM (MLX)**: HS code classification and product description analysis without sending trade data to external services
- **HK Census & Statistics Department**: Reference data for HS code schedule updates
- **Telegram Bot API**: Secondary channel for filing alerts, supplier communication, and payment reminders.

## GUI Specification

Part of the **Import/Export Dashboard** (`http://mona.local:8504`) — TradeDoc AI tab.

### Views

- **HS Code Classifier**: Product description input field with suggested 8-digit HK HS codes ranked by confidence. Manual override with searchable HS code database. "Quick Classify" mode for instant lookups.
- **TDEC Form Builder**: Guided declaration form with auto-populated fields from product catalog. Supports import, export, and re-export types with linked declaration view.
- **Commercial Invoice Builder**: Professional invoice template with Incoterms dropdown, multi-currency line items, and HS code per item.
- **CO Application Form**: Certificate of Origin form with CEPA eligibility auto-check and preferential CO type selector.
- **Strategic Commodities Alert**: Prominent red warning banner when a product matches the Strategic Commodities Control List, with license requirement details.
- **Filing Status Tracker**: Dashboard showing all declarations with status (draft/filed/accepted/rejected/amended) and filing deadlines.

### Mona Integration

- Mona auto-classifies HS codes for new products using LLM semantic matching and presents suggestions for human confirmation.
- Mona monitors TDEC filing deadlines (14-day rule) and sends alerts before they expire.
- Mona auto-fills declaration forms from the product catalog; human reviews and approves before filing.

### Manual Mode

- Trader can manually classify products, build declarations, create invoices, and track filing status without Mona.

## HK-Specific Requirements

- Import and Export Ordinance (Cap 60): All articles imported or exported from HK (except exempted articles) require a Trade Declaration (TDEC) within 14 days
- TDEC electronic filing: Mandatory electronic submission through government-approved service providers (Tradelink or DTTN); paper filing is no longer accepted for most declarations
- Re-export dominance: Over 95% of HK's total exports are re-exports — the tool must handle re-export documentation as the primary use case, not an edge case
- Strategic Commodities Control (Cap 60G): Items on the Strategic Commodities list require an export license from TID (Trade and Industry Department) — screening must be thorough
- Certificate of Origin: HK is a free port (zero tariffs on imports) but COs are needed for preferential treatment under CEPA (HK-Mainland), ASEAN-HK FTA, and other agreements
- HK HS code format: 8-digit code (international 6-digit HS + 2-digit HK suffix); must use the latest HK classification schedule
- Dutiable Commodities: Only 4 categories are dutiable in HK (liquor, tobacco, hydrocarbon oil, methyl alcohol) — flag these for duty calculation
- Bilingual documentation: Trade documents may need to be in English and Chinese; Chinese product descriptions must match the HS code schedule's Chinese text

## Data Model

```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
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

CREATE TABLE trade_declarations (
    id INTEGER PRIMARY KEY,
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
    linked_import_id INTEGER REFERENCES trade_declarations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE declaration_items (
    id INTEGER PRIMARY KEY,
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

CREATE TABLE certificates_of_origin (
    id INTEGER PRIMARY KEY,
    declaration_id INTEGER REFERENCES trade_declarations(id),
    co_type TEXT CHECK(co_type IN ('general','cepa','asean_hk','other_preferential')),
    application_number TEXT,
    status TEXT DEFAULT 'draft',
    issued_date DATE
);

CREATE TABLE filing_history (
    id INTEGER PRIMARY KEY,
    declaration_id INTEGER REFERENCES trade_declarations(id),
    action TEXT,
    provider TEXT CHECK(provider IN ('tradelink','becs')),
    response_code TEXT,
    response_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Company Profile**: Company name, BR number, principal business (import/export/re-export), base currency
2. **Trade Filing**: Tradelink/BECS account credentials for electronic TDEC filing
3. **Product Catalog**: Import existing product list with HS codes or start fresh
4. **Messaging Setup**: Telegram bot token for filing deadline alerts and status notifications
5. **Currency Configuration**: Select base currency for trade declarations and invoicing
6. **Sample Data**: Option to seed demo products, HS codes, declarations, and invoices for testing
7. **Connection Test**: Validates Tradelink/BECS connectivity, LLM availability, and reports any issues

## Testing Criteria

- [ ] HS classifier correctly identifies code for common products (e.g., "cotton t-shirt" → 6109.10) with >80% top-3 accuracy
- [ ] TDEC form generates all required fields for an import declaration
- [ ] Re-export workflow correctly links an import declaration to the corresponding re-export declaration
- [ ] Strategic commodities screener flags a known controlled item (e.g., semiconductor equipment) for license requirement
- [ ] Commercial invoice PDF includes all fields required by HK customs (Incoterms, HS codes, item values)
- [ ] Certificate of Origin application pre-fills correctly for a CEPA-eligible product
- [ ] Filing tracker updates status when Tradelink acknowledges or rejects a submission

## Implementation Notes

- HS code database: load the full HK 8-digit HS schedule (~10,000 codes) into SQLite with FTS5 for fast keyword search; use LLM only for ambiguous classifications
- Strategic commodities list is updated periodically by TID — implement a version check and prompt for updates
- Tradelink integration: if direct API is unavailable, use Playwright to automate the web portal filing workflow
- Re-export linking: match import and re-export declarations by product description, quantity, and HS code; flag partial re-exports (quantity split)
- Memory budget: ~4GB (LLM for classification + application); HS code database fits easily in SQLite
- TDEC filing deadline: 14 days for imports, 14 days for exports/re-exports — tool should auto-calculate and alert approaching deadlines
- Consider a "quick classify" mode where the user pastes a product description and gets an instant HS code suggestion without creating a full declaration
- **Logging**: All operations logged to `/var/log/openclaw/trade-doc-ai.log` with daily rotation (7-day retention). Trade values and supplier details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Trade documentation contains commercially sensitive data — zero cloud processing for classification and document generation.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Trade declarations and filing history included for audit compliance.
