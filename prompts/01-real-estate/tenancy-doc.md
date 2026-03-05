# TenancyDoc Automator — HK Tenancy Agreement Generator

## Overview

TenancyDoc Automator generates legally compliant Hong Kong tenancy agreements, provisional agreements, and supporting documents from structured input data. It calculates stamp duty, produces inventory checklists, tracks lease renewal dates, and manages the full tenancy document lifecycle from provisional agreement through to Form CR109 filing.

## Target User

Hong Kong estate agents and small landlords managing 5-50 residential tenancy agreements who need to produce standard-form documents quickly, track renewal dates, and ensure compliance with the Landlord and Tenant (Consolidation) Ordinance.

## Core Features

- **Tenancy Agreement Generator**: Produce SAR-standard tenancy agreements from templates with auto-populated fields (names, HKID, property address, rent, term, break clause). Support both fixed-term and periodic tenancies. Output as DOCX and PDF.
- **Stamp Duty Calculator**: Calculate ad valorem stamp duty based on rent and term length per IRD rates. Generate stamp duty computation form. Handle cases with premium, rent-free periods, and options to renew.
- **Provisional Agreement Builder**: Generate the provisional agreement (臨時租約) that precedes the formal tenancy. Include standard HK clauses: deposit (typically 2 months), commission split, handover date, and special conditions.
- **Inventory Checklist Generator**: Create room-by-room inventory with condition notes, appliance serial numbers, and photo references. Output as printable PDF with signature blocks for landlord and tenant.
- **Lease Renewal Tracker**: Monitor all active tenancies with alerts at 90/60/30 days before expiry. Generate renewal offer letters with proposed rent adjustment. Track whether tenant has responded.
- **Form CR109 Preparation**: Generate the Notice of New Letting or Renewal (Form CR109) required for filing with the Rating and Valuation Department within one month of tenancy commencement.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Document generation | `python-docx`, `reportlab` |
| PDF handling | `PyPDF2`, `reportlab` |
| Template engine | `jinja2` |
| Scheduling | `APScheduler` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Notifications | Twilio WhatsApp Business API |
| Date calculations | `python-dateutil` |

## File Structure

```
/opt/openclaw/skills/local/tenancy-doc/
├── main.py                  # FastAPI entry point
├── config.yaml              # Stamp duty rates, template paths
├── generators/
│   ├── tenancy_agreement.py # Formal TA generator
│   ├── provisional.py       # Provisional agreement generator
│   ├── inventory.py         # Inventory checklist builder
│   ├── cr109.py             # Form CR109 generator
│   └── stamp_duty.py        # Stamp duty calculator
├── templates/
│   ├── tenancy_agreement.docx
│   ├── provisional_agreement.docx
│   ├── inventory_checklist.docx
│   ├── cr109_template.pdf
│   └── renewal_letter.docx
├── tracking/
│   ├── renewals.py          # Lease expiry monitoring
│   └── notifications.py     # Reminder dispatch
└── tests/
    ├── test_generators.py
    ├── test_stamp_duty.py
    └── test_renewals.py

~/OpenClawWorkspace/tenancy-doc/
├── agreements/              # Generated tenancy docs
├── templates/               # Custom user templates
├── exports/                 # Stamp duty forms, CR109s
└── backups/                 # Version history of docs
```

## Key Integrations

- **Twilio WhatsApp Business API**: Send renewal reminders to agents, landlords, and tenants. Deliver generated documents as PDF attachments.
- **Rating and Valuation Department (RVD)**: CR109 form specifications and filing requirements reference.
- **Inland Revenue Department (IRD)**: Stamp duty rate tables (updated annually in Budget).
- **Apple Calendar**: Create calendar events for renewal dates, handover dates, and filing deadlines.

## HK-Specific Requirements

- **Stamp Duty Rates**: For tenancies, ad valorem stamp duty applies based on average yearly rent × term. Current rates: not exceeding 1 year = 0.25% of total rent; exceeding 1 year but not 3 years = 0.5% of average yearly rent; exceeding 3 years = 1% of average yearly rent. Rates must be configurable for annual Budget changes.
- **Form CR109**: Mandatory filing with RVD within one month of a new letting or renewal. Requires property address, rateable value, rent, landlord details, and tenant details. Failure to file within time may result in penalties.
- **Provisional vs Formal Agreement**: HK practice uses a two-stage process. The provisional agreement (臨時租約) is binding and typically includes a deposit (usually 2 months' rent + 1 month utility deposit). The formal agreement follows within 14 days.
- **Government Rent and Rates**: Include clauses specifying responsibility for government rent and rates (typically landlord for pre-1985 leases, shared arrangements vary).
- **HKID Validation**: Validate HKID format: 1-2 letters + 6 digits + check digit in parentheses. Example: A123456(7). Use the check digit algorithm to verify.
- **Security Deposit Cap**: Standard practice is 2 months' rent as security deposit. Flag any agreements with deposits exceeding 3 months as unusual.
- **Break Clause**: Standard HK practice is a 2-year fixed term with a break clause exercisable after 12 months with 2 months' written notice.

## Data Model

```sql
CREATE TABLE tenancies (
    id INTEGER PRIMARY KEY,
    property_address TEXT NOT NULL,
    property_address_zh TEXT,
    district TEXT,
    landlord_name TEXT NOT NULL,
    landlord_hkid TEXT,
    landlord_phone TEXT,
    tenant_name TEXT NOT NULL,
    tenant_hkid TEXT,
    tenant_phone TEXT,
    monthly_rent INTEGER NOT NULL,
    deposit_amount INTEGER,
    term_months INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    break_clause_date DATE,
    stamp_duty_amount REAL,
    cr109_filed BOOLEAN DEFAULT FALSE,
    cr109_filed_date DATE,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    tenancy_id INTEGER REFERENCES tenancies(id),
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE renewal_alerts (
    id INTEGER PRIMARY KEY,
    tenancy_id INTEGER REFERENCES tenancies(id),
    alert_date DATE NOT NULL,
    alert_type TEXT,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP
);
```

## Testing Criteria

- [ ] Generated tenancy agreement contains all mandatory clauses per SAR standard form
- [ ] Stamp duty calculation matches IRD published rates for test cases: 1-year, 2-year, and 3-year terms
- [ ] HKID validation correctly accepts valid IDs and rejects invalid check digits
- [ ] CR109 form fields populate correctly and PDF output is print-ready (A4)
- [ ] Renewal tracker fires alerts at exactly 90, 60, and 30 days before lease expiry
- [ ] Provisional agreement includes deposit amount, commission, and handover date
- [ ] Inventory checklist generates a room-by-room PDF with blank signature blocks
- [ ] All documents render correctly in both English and Traditional Chinese

## Implementation Notes

- **Template management**: Store DOCX templates with Jinja2-style placeholders (e.g., `{{ landlord_name }}`). Use `python-docx` to replace placeholders while preserving formatting. Keep master templates in `/opt/openclaw/skills/local/tenancy-doc/templates/` and allow user overrides in workspace.
- **Stamp duty updates**: Store rates in `config.yaml` so they can be updated after the annual Budget without code changes. Include an effective date field.
- **PDF generation**: Use `reportlab` for CR109 (fixed-layout government form) and `python-docx` → PDF conversion for agreements. If `libreoffice` is available, use it for DOCX→PDF; otherwise, deliver DOCX with a note.
- **Privacy**: Tenancy documents contain HKID numbers and personal data protected under the PDPO. Never log full HKID numbers — mask as `A1234XX(X)` in logs. Store database encrypted at rest using SQLCipher if available.
- **Memory**: This tool is lightweight (<500MB RAM). No LLM needed for core functionality — all generation is template-based.
- **Backup**: Auto-version documents. When regenerating, increment version number and keep previous versions in `backups/`.
