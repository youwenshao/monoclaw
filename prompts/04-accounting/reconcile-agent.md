# ReconcileAgent — Bank Reconciliation Automation

## Overview

ReconcileAgent automates the bank reconciliation process for Hong Kong SMEs by matching bank statement transactions against accounting ledger entries. It supports major HK bank formats (HSBC, Hang Seng, Bank of China, ZA, Mox, Livi), handles multi-currency matching, flags discrepancies, and generates reconciliation reports — reducing a task that takes hours to minutes.

## Target User

Hong Kong accounting firms and in-house bookkeepers who perform monthly bank reconciliation for 5-50 client accounts. Each reconciliation involves importing bank statements, matching hundreds of transactions against ledger entries, and investigating discrepancies — a tedious process that currently consumes 2-4 hours per account.

## Core Features

- **Multi-Bank Statement Parser**: Import and parse bank statements from HSBC, Hang Seng, Standard Chartered, Bank of China, ICBC, DBS, and virtual banks (ZA, Mox, Livi). Support CSV, OFX/QFX, PDF, and Excel formats. Normalize all formats into a standard transaction schema.
- **Intelligent Transaction Matching**: Match bank transactions to ledger entries using multiple strategies: exact amount match, date proximity (±3 business days), reference number matching, payee name fuzzy matching, and aggregate matching (multiple ledger entries summing to one bank transaction).
- **FPS Transaction Handling**: Faster Payment System (FPS) transactions often have cryptic references. Use amount + date + counterparty matching. Detect FPS-specific patterns in bank statements.
- **Multi-Currency Reconciliation**: Handle accounts in HKD, USD, CNH/CNY, EUR, and GBP. Match transactions across currencies using exchange rate tolerance (±1% of HKMA rate). Flag and calculate FX differences.
- **Discrepancy Management**: Categorize unmatched items: bank charges not recorded, outstanding cheques, deposits in transit, timing differences, and genuine errors. Generate a prioritized discrepancy list with suggested resolutions.
- **Reconciliation Report Generator**: Produce a standard bank reconciliation statement showing: bank balance, add outstanding deposits, less outstanding cheques, adjusted bank balance = ledger balance. Output as PDF and Excel.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Data processing | `pandas`, `numpy` |
| CSV/Excel parsing | `pandas`, `openpyxl` |
| OFX parsing | `ofxparse` |
| PDF statement parsing | `pdfplumber`, `tabula-py` |
| Fuzzy matching | `rapidfuzz` |
| PDF report generation | `reportlab` |
| Excel report | `openpyxl` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| FX rates | `httpx` for HKMA API |

## File Structure

```
/opt/openclaw/skills/local/reconcile-agent/
├── main.py                  # FastAPI entry point
├── config.yaml              # Bank format configs, matching rules
├── parsers/
│   ├── base.py              # Abstract statement parser
│   ├── hsbc.py              # HSBC format parser
│   ├── hang_seng.py         # Hang Seng format parser
│   ├── boc.py               # Bank of China parser
│   ├── standard_chartered.py
│   ├── virtual_banks.py     # ZA, Mox, Livi parsers
│   ├── ofx_parser.py        # Generic OFX/QFX parser
│   └── pdf_parser.py        # PDF statement table extractor
├── matching/
│   ├── engine.py            # Core matching algorithm
│   ├── strategies.py        # Match strategies (exact, fuzzy, aggregate)
│   ├── fx.py                # Multi-currency matching
│   └── fps.py               # FPS-specific matching logic
├── reporting/
│   ├── reconciliation.py    # Rec statement generator
│   ├── discrepancies.py     # Discrepancy report
│   └── templates/           # Report templates
└── tests/
    ├── test_parsers.py
    ├── test_matching.py
    ├── test_fx.py
    └── test_reports.py

~/OpenClawWorkspace/reconcile-agent/
├── reconcile.db             # SQLite database
├── statements/              # Imported bank statements
├── ledger_exports/          # Accounting software exports
├── reports/                 # Generated reconciliation reports
└── fx_rates/                # Cached exchange rate data
```

## Key Integrations

- **HKMA Exchange Rate API**: Fetch daily exchange rates from the Hong Kong Monetary Authority. Use as the reference rate for multi-currency matching and FX difference calculations.
- **Accounting Software Export**: Import ledger data from Xero (CSV export), ABSS (CSV), and QuickBooks (IIF/CSV). Provide a standardized import template for manual exports.
- **InvoiceOCR Pro (sibling tool)**: Cross-reference matched transactions with OCR-extracted invoice data for additional validation.
- **FXTracker (sibling tool)**: Share exchange rate data to avoid duplicate API calls.

## HK-Specific Requirements

- **HK Bank Statement Formats**:
  - **HSBC**: CSV with columns: Date, Description, Amount (single column, negative for debits). Running balance. FPS transactions labeled "FASTER PAYMENT".
  - **Hang Seng**: Grouped by date, separate debit/credit columns. Chinese descriptions common.
  - **BOC**: Bilingual columns (Chinese + English side by side). Date format DD/MM/YYYY.
  - **Virtual banks (ZA, Mox, Livi)**: Modern CSV/JSON exports. Clean formatting but newer patterns.
  Implement per-bank parsers that normalize to a common schema.
- **FPS Transaction References**: FPS transfers show minimal reference info — often just "FPS" + partial name or phone number. Match primarily on amount + date. HK phone number (8 digits) sometimes appears in the reference.
- **Multi-Currency Handling**: HK businesses commonly hold USD and CNH accounts alongside HKD. The linked exchange rate (USD/HKD 7.75-7.85) means USD transactions rarely have large FX variances. CNH transactions need wider tolerance.
- **Cheque Clearing**: Despite declining use, cheques remain common in HK business. Cheque clearing takes 2-3 business days. Outstanding cheques are a standard reconciliation item. Parse cheque numbers from bank statements.
- **Autopay/Standing Orders**: Regular payments (rent, utilities, MPF) via autopay are common. Detect recurring transaction patterns for faster matching.
- **Bank Charges**: HK banks charge monthly maintenance fees, transaction fees, and FPS fees. These are often missing from the ledger. Auto-detect common bank charge patterns and suggest ledger entries.

## Data Model

```sql
CREATE TABLE bank_transactions (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    bank_name TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    value_date DATE,
    description TEXT,
    reference TEXT,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    balance REAL,
    currency TEXT DEFAULT 'HKD',
    transaction_type TEXT,
    match_status TEXT DEFAULT 'unmatched',
    matched_ledger_id INTEGER,
    import_batch TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ledger_entries (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    entry_date DATE NOT NULL,
    description TEXT,
    reference TEXT,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    currency TEXT DEFAULT 'HKD',
    account_code TEXT,
    match_status TEXT DEFAULT 'unmatched',
    matched_bank_id INTEGER,
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reconciliations (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,
    period_start DATE,
    period_end DATE,
    bank_closing_balance REAL,
    ledger_closing_balance REAL,
    matched_count INTEGER,
    unmatched_bank INTEGER,
    unmatched_ledger INTEGER,
    difference REAL,
    status TEXT DEFAULT 'in_progress',
    report_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE fx_rates (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    base_currency TEXT DEFAULT 'HKD',
    target_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    source TEXT DEFAULT 'HKMA'
);
```

## Testing Criteria

- [ ] HSBC CSV parser correctly imports 100 transactions with correct dates, amounts, and descriptions
- [ ] Hang Seng parser handles bilingual descriptions and separate debit/credit columns
- [ ] Exact amount matching correctly pairs 80%+ of a test dataset of 200 transaction pairs
- [ ] Fuzzy payee name matching catches "HK ELECTRIC CO" ↔ "HK Electric Company Ltd"
- [ ] Aggregate matching identifies 3 ledger entries that sum to 1 bank transaction
- [ ] FPS transaction matching works with minimal reference data (amount + date only)
- [ ] Multi-currency reconciliation handles a USD account with ±1% exchange rate tolerance
- [ ] Reconciliation report balances (adjusted bank balance = adjusted ledger balance) for a clean dataset

## Implementation Notes

- **No LLM required**: Bank reconciliation is entirely algorithmic. Fuzzy matching uses `rapidfuzz` (Levenshtein distance). Total memory footprint <500MB even for large datasets. Can run alongside LLM-heavy tools.
- **Matching algorithm priority**: 1) Exact reference + amount match (highest confidence). 2) Exact amount + date within ±3 days. 3) Fuzzy payee name + approximate amount (±$1). 4) Aggregate matching (combinations of 2-4 entries). Run strategies in order; stop at first match. Flag low-confidence matches for human review.
- **Bank parser extensibility**: Use a plugin architecture. Each bank parser inherits from `BaseStatementParser` and implements `parse(file_path) → list[Transaction]`. Adding a new bank requires only a new parser class and format config.
- **Performance**: Matching 1,000 bank transactions against 1,200 ledger entries should complete in <10 seconds. Use pandas merge operations for exact matching; iterate only for fuzzy and aggregate strategies.
- **Privacy**: Bank statements contain account numbers and financial data. All processing is local. Mask account numbers in reports (show only last 4 digits). Delete imported statement files after reconciliation is complete (configurable).
- **Idempotency**: Re-importing the same bank statement should not create duplicate transactions. Use a composite key of (bank, date, description, amount, running_balance) for deduplication.
