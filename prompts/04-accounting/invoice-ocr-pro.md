# InvoiceOCR Pro — Invoice & Receipt Data Extraction

## Overview

InvoiceOCR Pro extracts structured line-item data from Chinese and English invoices, receipts, and fapiao (發票) using macOS Vision framework OCR. It handles WhatsApp-forwarded receipt photos, batch processes document folders, and integrates with ABSS (formerly MYOB), Xero, and QuickBooks to auto-create journal entries — eliminating the manual data entry bottleneck in Hong Kong accounting firms.

## Target User

Hong Kong accounting firms and bookkeepers processing 200-500 invoices per month for SME clients. Staff currently key data manually from paper invoices, WhatsApp photos, and email PDFs into accounting software — a tedious, error-prone process consuming 15-20 hours per week.

## Core Features

- **Multi-Format OCR**: Extract supplier name, invoice number, date, line items (description, quantity, unit price, amount), subtotal, tax, and total from: printed invoices (English/Chinese), handwritten receipts, mainland China fapiao (VAT invoices), and WhatsApp-compressed photos. Handle rotated, skewed, and low-resolution images.
- **Accounting Software Integration**: Map extracted data to chart of accounts and push entries to ABSS/Xero/QuickBooks via their APIs. Auto-suggest account codes based on supplier name and description using historical patterns. Support both accounts payable and expense entries.
- **WhatsApp Receipt Pipeline**: Receive receipt photos via WhatsApp from clients or staff. Auto-process on receipt, extract data, and queue for review. Reply with extracted summary for quick client confirmation.
- **Batch Processing**: Watch a designated folder for new documents. Process PDFs and images in batch mode. Generate a CSV/Excel summary of all extracted invoices for review before import into accounting software.
- **Smart Categorization**: Use historical data and supplier matching to auto-categorize expenses (rent, utilities, staff costs, materials, etc.). Learn from corrections to improve over time.
- **Duplicate Detection**: Check invoice number + supplier + amount against existing records. Flag potential duplicates before creating entries. Prevent double-booking of the same expense.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| OCR primary | macOS Vision framework via `pyobjc-framework-Vision` |
| OCR enhancement | `opencv-python-headless` for preprocessing |
| PDF processing | `pdf2image`, `pdfplumber` |
| Data extraction | `pandas` for structuring, `pydantic` for validation |
| ABSS integration | ABSS AccountRight API (REST) |
| Xero integration | `xero-python` SDK |
| QuickBooks | `python-quickbooks` SDK |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| WhatsApp | Twilio WhatsApp Business API |
| Excel output | `openpyxl` |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/invoice-ocr-pro/
├── main.py                  # FastAPI app entry
├── config.yaml              # API creds, chart of accounts, OCR settings
├── ocr/
│   ├── vision_engine.py     # macOS Vision OCR wrapper
│   ├── preprocessor.py      # Image enhancement, deskew, crop
│   ├── line_extractor.py    # Table/line-item detection
│   └── fapiao.py            # China fapiao-specific parser
├── extraction/
│   ├── invoice_parser.py    # Structured data extraction from OCR text
│   ├── receipt_parser.py    # Simplified receipt parser
│   └── validator.py         # Data validation and confidence scoring
├── accounting/
│   ├── categorizer.py       # Expense auto-categorization
│   ├── duplicate.py         # Duplicate detection
│   ├── abss.py              # ABSS integration
│   ├── xero.py              # Xero integration
│   └── quickbooks.py        # QuickBooks integration
├── messaging/
│   └── whatsapp.py          # Receipt photo receiver
├── batch/
│   └── watcher.py           # Folder watcher for batch processing
└── tests/
    ├── test_ocr.py
    ├── test_extraction.py
    ├── test_categorization.py
    └── test_integrations.py

~/OpenClawWorkspace/invoice-ocr-pro/
├── invoiceocr.db            # SQLite database
├── incoming/                # Documents to process
├── processed/               # Completed documents
├── exports/                 # CSV/Excel summaries
└── training_data/           # Categorization learning data
```

## Key Integrations

- **ABSS (formerly MYOB) AccountRight**: REST API to create purchase invoices and journal entries. Requires OAuth2 authentication. Map to HK-specific chart of accounts.
- **Xero**: `xero-python` SDK for creating bills and bank transactions. OAuth2 flow. Support multi-currency entries.
- **QuickBooks Online**: `python-quickbooks` SDK for expense entry creation. OAuth2 flow.
- **Twilio WhatsApp Business API**: Receive receipt photos, send extraction summaries for confirmation.
- **macOS Vision Framework**: On-device OCR with Chinese and English support. No cloud API needed.
- **Telegram Bot API**: Secondary channel for deadline reminders, invoice notifications, and rate alerts.

## GUI Specification

Part of the **Accounting Dashboard** (`http://mona.local:8004`) — InvoiceOCR tab.

### Views

- **Three-Column Layout**: Incoming queue (left) | OCR result editor (center) | accounting push controls (right).
- **Invoice Viewer**: Zoomable original image alongside extracted fields (supplier, date, amount, line items) as editable form fields.
- **Auto-Categorization**: Dropdown category selector pre-filled by AI; overridable. Historical pattern shown as hint text.
- **Duplicate Detection Banner**: Amber warning when invoice number + supplier matches an existing record, with link to the duplicate.
- **Batch Action Bar**: Select multiple invoices, approve all, and push to Xero/ABSS/QuickBooks in one action.
- **Processing Statistics**: Today's processed count, OCR accuracy rate, estimated time saved vs manual entry.

### Mona Integration

- Mona auto-processes invoices from the watched folder and WhatsApp receipts, populating the queue with extracted data.
- Mona auto-categorizes expenses based on supplier history and description patterns.
- Human reviews extractions, corrects any errors, and approves before data is pushed to accounting software.

### Manual Mode

- Bookkeeper can manually upload invoices, review OCR results, categorize expenses, and push to accounting software without Mona.

## HK-Specific Requirements

- **Fapiao (發票) Format**: Mainland China VAT invoices have a standard government format with machine-printed QR code, buyer/seller tax IDs, and structured line items. Parse the standard fields: 發票代碼, 發票號碼, 開票日期, 購買方, 銷售方, 金額, 稅額, 價稅合計. Cross-border trade invoices between HK and mainland are common.
- **HK Invoice Conventions**: HK invoices have no mandated format (no GST/VAT system). Common elements: company name, BR number, invoice number, date, and line items. Amounts in HKD unless specified. No tax line for domestic invoices.
- **MPF-Related Deductions**: Identify invoices from MPF trustees (HSBC Provident Fund, Manulife, AIA, etc.) and auto-categorize as MPF contributions. Flag employer vs employee portions.
- **Multi-Currency**: HK businesses frequently receive invoices in HKD, USD, CNY/RMB, EUR, and GBP. Detect currency from invoice text or symbol. Use daily exchange rates for conversion.
- **Chart of Accounts**: Default to a standard HK SME chart of accounts. Common categories: Rent & Rates (including government rates), Staff Costs (salary, MPF, insurance), Professional Fees, Bank Charges, Entertainment, Travel, Utilities.
- **Receipt Culture**: Small HK businesses often provide handwritten receipts (single-ply paper) or thermal-printed POS receipts that fade. OCR must handle low-contrast and partially faded text.

## Data Model

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    supplier_name TEXT,
    supplier_br_number TEXT,
    invoice_number TEXT,
    invoice_date DATE,
    due_date DATE,
    currency TEXT DEFAULT 'HKD',
    subtotal REAL,
    tax_amount REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    category TEXT,
    account_code TEXT,
    source TEXT NOT NULL,
    source_file TEXT,
    ocr_confidence REAL,
    status TEXT DEFAULT 'pending_review',
    duplicate_flag BOOLEAN DEFAULT FALSE,
    accounting_ref TEXT,
    pushed_to TEXT,
    pushed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE line_items (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id),
    description TEXT,
    quantity REAL,
    unit_price REAL,
    amount REAL NOT NULL,
    account_code TEXT
);

CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    br_number TEXT,
    default_category TEXT,
    default_account_code TEXT,
    currency TEXT DEFAULT 'HKD',
    total_invoices INTEGER DEFAULT 0,
    last_invoice_date DATE
);

CREATE TABLE category_rules (
    id INTEGER PRIMARY KEY,
    match_type TEXT NOT NULL,
    match_value TEXT NOT NULL,
    category TEXT NOT NULL,
    account_code TEXT,
    confidence REAL DEFAULT 1.0
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Business Profile**: Company name, BR number, financial year-end date, base currency (HKD)
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **Accounting Software**: Connect Xero/ABSS/QuickBooks OAuth credentials and select chart of accounts
4. **OCR Settings**: Configure watched folder path, OCR accuracy level, supported document formats
5. **Expense Categories**: Import or define chart of accounts categories for auto-categorization
6. **Sample Data**: Option to seed demo invoices for testing OCR extraction and categorization
7. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] OCR extracts supplier name, invoice number, date, and total from 10 sample HK invoices with >90% accuracy
- [ ] Fapiao parser correctly extracts all standard fields from 5 mainland China VAT invoice samples
- [ ] Line-item extraction matches actual line items within ±$1 per line for tabular invoices
- [ ] WhatsApp receipt photo pipeline processes a compressed JPEG and returns extracted data within 10 seconds
- [ ] Duplicate detection catches an invoice with the same number and supplier already in the database
- [ ] Auto-categorization correctly assigns category for 80% of invoices from known suppliers
- [ ] Xero integration creates a valid bill entry with correct account mapping
- [ ] Batch processing handles a folder of 50 mixed PDF/image invoices without errors

## Implementation Notes

- **OCR pipeline order**: 1) Convert PDF pages to images via `pdf2image`. 2) Preprocess (deskew, contrast enhancement, binarization). 3) Run macOS Vision OCR at `.accurate` level. 4) Post-process: detect table structures, extract line items, parse amounts.
- **Table detection**: Invoices with tabular line items need table structure detection. Use horizontal/vertical line detection via OpenCV Hough transforms. Fall back to whitespace-based column detection if no visible lines.
- **Categorization learning**: Start with rule-based matching (supplier name → category). After 100+ manually reviewed invoices, supplement with a simple classifier trained on description text. Store corrections to improve rules.
- **Memory**: OCR processing is bursty. Peak memory during batch processing can reach 2-3GB (image buffers + OCR engine). Process sequentially, release image memory after each document.
- **Accounting API rate limits**: Xero: 60 calls/minute. QuickBooks: 500 calls/minute. ABSS: varies. Batch invoice creation where possible. Queue entries and push during off-peak hours.
- **Privacy**: Invoices contain business financial data. All processing is local. Never send invoice images to cloud OCR. Accounting API integration sends only structured data (not images) to the cloud accounting platform with client authorization.
- **Faded receipts**: Thermal receipts fade over time. Apply adaptive thresholding and contrast stretching before OCR. If confidence is below threshold, flag for manual entry rather than guessing.
- **Logging**: All operations logged to `/var/log/openclaw/invoice-ocr-pro.log` with daily rotation (7-day retention). Financial data and client details masked in log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Dashboard requires PIN authentication. Accounting API credentials stored with restricted file permissions (600). Financial data protected under PDPO.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, OCR/LLM state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all tool data for backup or audit purposes.
