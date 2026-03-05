# VisaDoc OCR — Immigration Document Parser

## Overview

VisaDoc OCR extracts structured data from immigration-related documents including HKID cards, passports, bank statements, tax returns, and employment contracts with full bilingual (Chinese/English) support. It validates document completeness against visa application checklists and flags missing, expired, or non-compliant documents before submission.

## Target User

Hong Kong immigration consultants managing 10-30 active visa applications who manually key data from scanned documents into application forms — a process that is slow, error-prone, and involves sensitive personal data that must stay local.

## Core Features

- **Multi-Document OCR Pipeline**: Process HKID cards, passports (MRZ + visual zone), HK bank statements, IRD tax returns, employment contracts, and business registration certificates. Output structured JSON with field-level confidence scores.
- **Bilingual Text Extraction**: Handle documents with mixed Chinese and English text. Correctly segment Traditional Chinese characters, simplified Chinese (mainland documents), and English. Use macOS Vision framework as primary engine with Tesseract fallback.
- **Document Completeness Validator**: Given a visa scheme (GEP, ASMTP, QMAS, IANG), check the extracted document set against the Immigration Department's required document list. Flag missing documents, expired items, and documents approaching expiry.
- **HKID Verification**: Extract and validate HKID number format (1-2 prefix letters + 6 digits + check digit). Verify check digit algorithmically. Extract issue date, date of birth, and name from card image.
- **Passport MRZ Reader**: Decode Machine Readable Zone from passport photos. Extract nationality, document number, expiry date, name, and date of birth. Cross-validate MRZ data against visual zone OCR.
- **Bank Statement Analyzer**: Extract account holder name, account number, ending balance, and 12-month average balance from HK bank statements (HSBC, Hang Seng, Standard Chartered, BOC formats).

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| OCR primary | macOS Vision framework via `pyobjc-framework-Vision` |
| OCR fallback | `pytesseract` with chi_tra + eng models |
| MRZ decoding | `passporteye` or custom MRZ parser |
| PDF processing | `pdf2image`, `pdfplumber` |
| Image preprocessing | `Pillow`, `opencv-python-headless` |
| Data validation | `pydantic` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |

## File Structure

```
/opt/openclaw/skills/local/visa-doc-ocr/
├── main.py                  # FastAPI entry point
├── config.yaml              # OCR settings, scheme requirements
├── ocr/
│   ├── vision_engine.py     # macOS Vision framework wrapper
│   ├── tesseract_engine.py  # Tesseract fallback
│   ├── preprocessor.py      # Image enhancement, deskew, crop
│   └── confidence.py        # Field confidence scoring
├── parsers/
│   ├── hkid.py              # HKID card parser + validator
│   ├── passport.py          # Passport + MRZ decoder
│   ├── bank_statement.py    # Bank statement extractor
│   ├── tax_return.py        # IRD tax return parser
│   └── employment.py        # Employment contract parser
├── validators/
│   ├── completeness.py      # Document checklist validator
│   ├── expiry.py            # Document expiry checker
│   └── schemes.py           # Scheme-specific requirements
└── tests/
    ├── test_hkid.py
    ├── test_passport.py
    ├── test_bank_statement.py
    └── test_completeness.py

~/OpenClawWorkspace/visa-doc-ocr/
├── incoming/                # Scanned documents to process
├── processed/               # OCR results (JSON)
├── client_files/            # Per-client document folders
└── templates/               # Scheme checklists
```

## Key Integrations

- **macOS Vision Framework**: Primary OCR engine. Leverages Apple's on-device ML for text recognition. Supports Chinese (Traditional + Simplified) and English natively on ARM64.
- **Twilio WhatsApp Business API**: Receive document photos from clients via WhatsApp, process, and return extracted data summary.
- **FormAutoFill (sibling tool)**: Feed extracted document data directly into the form population pipeline for ID990A/ID990B generation.
- **Client database**: Store extracted data per client for cross-referencing across multiple application types.

## HK-Specific Requirements

- **HKID Format**: 1-2 uppercase letters + 6 digits + check digit in parentheses. Check digit algorithm: assign values A=10...Z=35, multiply each position by weights [9,8,7,6,5,4,3,2,1], sum mod 11. Remainder 0 = check digit 0, remainder 1 = check digit A.
- **IRD Tax Return Format**: Form BIR60 (individuals). Key fields: total income, salaries tax payable, net chargeable income. Returns are issued in English with Chinese annotations. Tax year runs April 1 – March 31.
- **HK Bank Statement Layouts**: Each major bank has a distinct layout. HSBC uses a specific column format with running balance. Hang Seng groups transactions by date. BOC includes Chinese and English columns side by side. Build per-bank extraction templates.
- **Passport Varieties**: Handle HKSAR passport, BN(O), mainland Chinese travel permit (回鄉證), and foreign passports. Different MRZ layouts for each type.
- **Document Age**: Immigration Department typically requires documents issued within the last 3 months (bank statements) or 1 year (tax returns). Auto-flag stale documents.
- **Personal Data Protection Ordinance (PDPO)**: All extracted data is personal and sensitive. Process and store locally only. Never transmit to cloud OCR services. Implement data retention policies (delete processed images after 90 days by default).

## Data Model

```sql
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    hkid TEXT,
    passport_number TEXT,
    nationality TEXT,
    phone TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    ocr_result TEXT,
    confidence_score REAL,
    issue_date DATE,
    expiry_date DATE,
    status TEXT DEFAULT 'pending',
    processed_at TIMESTAMP
);

CREATE TABLE scheme_applications (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    scheme TEXT NOT NULL,
    required_docs TEXT,
    submitted_docs TEXT,
    completeness_pct REAL,
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] HKID OCR extracts name, ID number, and DOB from 10 sample card images with >95% character accuracy
- [ ] HKID check digit validation correctly accepts valid IDs and rejects invalid ones (test 20 cases)
- [ ] Passport MRZ decoding returns correct nationality, name, DOB, and expiry for 5 different passport types
- [ ] Bank statement parser extracts ending balance within ±$1 for HSBC and Hang Seng test statements
- [ ] Completeness validator correctly identifies missing documents for GEP and QMAS checklists
- [ ] Documents older than 3 months are flagged as potentially stale
- [ ] Mixed Chinese/English documents are processed without garbled characters
- [ ] Full pipeline (image → structured JSON) completes in under 5 seconds per document

## Implementation Notes

- **Vision framework advantage**: macOS Vision is pre-installed, runs on the Neural Engine, and handles Chinese text natively. No need for external OCR API calls. Use `VNRecognizeTextRequest` with `.accurate` recognition level.
- **Image preprocessing**: Before OCR, apply deskew correction, adaptive thresholding, and border cropping. HKID cards benefit from perspective correction. Bank statements need row-line detection for table parsing.
- **Confidence thresholds**: Set minimum confidence at 0.85 for auto-acceptance. Fields between 0.7-0.85 should be flagged for human review. Below 0.7, reject and request re-scan.
- **Memory**: OCR processing is lightweight (<1GB). Can process documents in parallel using macOS Vision's batch API. Limit to 4 concurrent pages to stay within memory budget.
- **Privacy-first architecture**: This tool handles the most sensitive personal data in the entire MonoClaw suite. Zero cloud processing. Encrypt the SQLite database. Implement audit logging for all data access. Auto-purge scanned images per configurable retention policy.
- **Error recovery**: If Vision framework returns low confidence, automatically retry with Tesseract using `chi_tra+eng` language model. If both fail, return partial results with clear field-level error markers.
