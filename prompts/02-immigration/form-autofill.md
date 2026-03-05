# FormAutoFill — Immigration Department Form Populator

## Overview

FormAutoFill automatically populates Hong Kong Immigration Department application forms (ID990A, ID990B, GEP applications, and others) from a client database. It validates field constraints, generates pre-submission checklists, tracks form version updates, and produces print-ready PDFs that match the department's exact formatting requirements.

## Target User

Hong Kong immigration consultants who prepare 5-20 visa applications per month and spend significant time manually filling repetitive government forms with data already in their client files — a process prone to transcription errors that can delay approvals.

## Core Features

- **Smart Form Population**: Map client database fields to Immigration Department form fields. Auto-fill ID990A (visa extension), ID990B (change of sponsorship), GEP (General Employment Policy), ASMTP, IANG, and QMAS application forms. Handle repeating sections (employment history, education).
- **Field Constraint Validation**: Enforce Immigration Department's field rules — character limits, required fields, date formats (DD/MM/YYYY), valid country codes, and cross-field dependencies. Flag violations before PDF generation.
- **Submission Checklist Generator**: Based on the selected scheme and client profile, produce a checklist of required supporting documents, certified copies, and photos. Check off items already in the client file.
- **Form Version Tracking**: Monitor Immigration Department's website for updated form versions. Alert when a form template changes and highlight field differences. Maintain a version history of all form templates.
- **Batch Processing**: Process multiple clients for the same scheme in one run. Useful for corporate sponsors filing multiple employment visas simultaneously.
- **PDF Overlay Generation**: Write form data directly onto the official PDF template using precise coordinate mapping, producing output indistinguishable from hand-filled forms.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| PDF manipulation | `reportlab`, `PyPDF2`, `pdfrw` |
| Form field mapping | Custom coordinate-based overlay engine |
| Data validation | `pydantic` |
| Web scraping | `httpx`, `beautifulsoup4` |
| Template diffing | `difflib` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Notifications | Twilio WhatsApp Business API |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/form-autofill/
├── main.py                  # FastAPI entry point
├── config.yaml              # Form template paths, ImmD URLs
├── forms/
│   ├── base.py              # Abstract form interface
│   ├── id990a.py            # Visa extension form
│   ├── id990b.py            # Change of sponsorship
│   ├── gep.py               # General Employment Policy
│   ├── asmtp.py             # Admission Scheme for Mainland Talents
│   ├── qmas.py              # Quality Migrant Admission Scheme
│   └── iang.py              # Immigration Arrangements for Non-local Graduates
├── engine/
│   ├── overlay.py           # PDF coordinate-based writer
│   ├── validator.py         # Field constraint engine
│   └── mapper.py            # Client data → form field mapper
├── tracking/
│   ├── version_checker.py   # Form version monitor
│   └── checklist.py         # Submission checklist generator
├── templates/
│   ├── pdf/                 # Official form PDFs
│   └── field_maps/          # JSON coordinate maps per form
└── tests/
    ├── test_overlay.py
    ├── test_validator.py
    └── test_forms.py

~/OpenClawWorkspace/form-autofill/
├── client_data/             # Client JSON profiles
├── generated/               # Filled-out form PDFs
├── form_templates/          # Downloaded official forms
└── checklists/              # Generated checklists
```

## Key Integrations

- **VisaDoc OCR (sibling tool)**: Receive extracted client data from OCR pipeline. Auto-populate client database from scanned documents.
- **Immigration Department website (immd.gov.hk)**: Download latest form templates. Monitor for form version changes.
- **Twilio WhatsApp Business API**: Notify consultants when forms are ready, deliver PDF attachments, and alert on form version updates.
- **Telegram Bot API**: Secondary messaging channel for client communication and status updates.
- **Client Portal Bot (sibling tool)**: Share submission status updates with clients.

## GUI Specification

Part of the **Immigration Dashboard** (`http://mona.local:8002`) — FormAutoFill tab.

### Views

- **Client Selector**: Dropdown with client profile summary card showing name, nationality, scheme, and completeness status.
- **Scheme/Form Selector**: Select from GEP, ASMTP, QMAS, IANG, ID990A/B with scheme-specific field requirements displayed.
- **Field-by-Field Preview**: Every form field shown with its value, validation state (green checkmark / red X), and character count vs limit.
- **PDF Preview Pane**: Live-rendered preview of the actual filled government form, updating as fields are edited.
- **Submission Checklist**: Interactive checklist of required supporting documents with check-off states and missing document alerts.
- **Batch View**: For corporate sponsors filing multiple visas — table of all applications with individual status columns.

### Mona Integration

- Mona auto-populates fields from VisaDoc OCR extractions and highlights any fields that need human verification.
- Mona monitors form version changes on the ImmD website and alerts when field maps need updating.
- Human reviews and approves every generated form before PDF output.

### Manual Mode

- Consultant can manually select clients, fill form fields, validate entries, generate PDFs, and manage checklists without Mona.

## HK-Specific Requirements

- **Form Specifications**: Immigration Department forms use specific field sizes, date format (DD/MM/YYYY), and require BLOCK CAPITALS for English text. Chinese names follow surname-first convention. All forms are available at immd.gov.hk.
- **Scheme-Specific Requirements**:
  - **GEP**: Requires salary ≥ HK market median for the role. Employer must demonstrate genuine job vacancy. Minimum qualifications: degree + relevant experience.
  - **ASMTP**: Mainland Chinese talent. Requires confirmed HK employment offer. No minimum salary but must be commensurate with market.
  - **QMAS**: Points-based (General Points Test or Achievement-based Points Test). Applicant must score ≥80 points under GPT. Annual quota applies.
  - **IANG**: Non-local graduates of HK institutions. Must apply within 6 months of graduation (first application). No minimum salary.
- **Salary Thresholds**: GEP applicants must demonstrate salary at or above the median for their profession. Store and update professional salary benchmarks from Census & Statistics Department data.
- **Photo Requirements**: Passport-style photo 40mm × 50mm, white background, taken within 6 months. Include photo spec in checklist.
- **Processing Times**: Reference processing times vary by scheme (GEP ~4 weeks, QMAS ~9-12 months). Include in generated checklist as client expectation setting.

## Data Model

```sql
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_zh TEXT,
    surname_en TEXT,
    given_name_en TEXT,
    hkid TEXT,
    passport_number TEXT,
    passport_expiry DATE,
    nationality TEXT,
    date_of_birth DATE,
    gender TEXT,
    marital_status TEXT,
    phone TEXT,
    email TEXT,
    address_hk TEXT,
    address_overseas TEXT,
    education_level TEXT,
    current_employer TEXT,
    current_position TEXT,
    monthly_salary INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    scheme TEXT NOT NULL,
    form_type TEXT NOT NULL,
    form_version TEXT,
    generated_pdf_path TEXT,
    checklist_path TEXT,
    status TEXT DEFAULT 'draft',
    submitted_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE form_templates (
    id INTEGER PRIMARY KEY,
    form_type TEXT NOT NULL,
    version TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    field_map_path TEXT,
    downloaded_at TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE TABLE field_maps (
    id INTEGER PRIMARY KEY,
    form_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    page_number INTEGER,
    x REAL,
    y REAL,
    width REAL,
    height REAL,
    font_size REAL DEFAULT 10,
    max_chars INTEGER,
    field_type TEXT DEFAULT 'text',
    required BOOLEAN DEFAULT FALSE
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Practice Profile**: Firm name, immigration consultant registration number, office address
2. **Form Templates**: Download latest ImmD form PDFs, configure field map source, select active schemes
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, default message language
4. **Client Database**: Import existing client records from CSV or start fresh
5. **Sample Data**: Option to seed demo client profiles and sample form outputs for testing
6. **Connection Test**: Validates ImmD website access, API connections, and reports any issues

## Testing Criteria

- [ ] ID990A form populates all mandatory fields from client database and produces valid PDF
- [ ] Field validation catches: missing required fields, dates in wrong format, HKID format errors
- [ ] Generated PDF overlays align precisely with the printed form (verify by overlaying on official template)
- [ ] GEP checklist includes all 9 required supporting documents per ImmD specifications
- [ ] Batch processing generates correct forms for 5 clients without cross-contamination of data
- [ ] Form version checker detects when ImmD updates a form template
- [ ] BLOCK CAPITALS enforcement works for all English text fields
- [ ] Chinese character fields handle both Traditional and Simplified input correctly

## Implementation Notes

- **Coordinate mapping precision**: Use the official PDF form as a background layer. Map each fillable field to exact (x, y, width, height) coordinates in points. Create field maps using a visual tool — overlay a grid on the PDF and record positions. Store maps as JSON.
- **PDF overlay technique**: Use `reportlab` to create a transparent overlay with positioned text, then merge with the background form using `PyPDF2.PageObject.merge_page()`. This produces output identical to handwritten forms.
- **Font handling**: Use a Unicode-compatible font that includes CJK characters (e.g., Noto Sans CJK). For English fields in BLOCK CAPITALS, use `text.upper()` before rendering.
- **No LLM needed**: This tool is entirely rule-based. All intelligence comes from the field mapping and validation logic. Memory footprint <500MB.
- **Privacy**: Client data includes HKID, passport numbers, salary, and immigration history. Encrypt database at rest. Mask sensitive fields in all logs. Implement access audit trail.
- **Form updates**: Immigration Department updates forms periodically. The version checker should scrape the download page monthly and compare file hashes. When a new version is detected, alert the consultant and invalidate the old field map until a new one is created.
- **Logging**: All operations logged to `/var/log/openclaw/form-autofill.log` using Python `logging` module with daily rotation (7-day retention). PII (phone numbers, HKID, passport numbers, names) is masked in all log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Local dashboard requires PIN authentication on first access. All API credentials stored in `config.yaml` with restricted file permissions (600). Immigration data is among the most sensitive in the MonoClaw suite — zero cloud processing for document content.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/OCR engine state, and memory usage.
- **Data export**: Supports `POST /api/export` to generate a portable JSON + files archive of all tool data for backup or PDPO compliance.
