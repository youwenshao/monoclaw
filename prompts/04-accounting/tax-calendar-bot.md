# TaxCalendar Bot — HK Tax Deadline Tracker & Reminder System

## Overview

TaxCalendar Bot tracks all Hong Kong tax filing deadlines across multiple clients — Profits Tax, Employer's Returns, MPF contributions, Business Registration renewals, and more. It sends proactive reminders at 60/30/7 days before each deadline, generates filing checklists, tracks extension applications, and ensures no filing date is missed across the firm's entire client portfolio.

## Target User

Hong Kong accounting firms managing tax compliance for 20-200 SME clients. Missing a filing deadline triggers IRD penalties (surcharges up to 10% of tax payable). Partners need confidence that every deadline across every client is tracked and actioned, even during the chaotic April-November filing season.

## Core Features

- **Multi-Client Deadline Tracking**: Maintain a centralized calendar of all tax filing deadlines per client. Auto-calculate deadlines based on financial year-end date, company type, and IRD assessment cycle. Support both individuals (BIR60) and corporations (BIR51/BIR52).
- **Proactive Reminder System**: Send reminders via WhatsApp to the assigned accountant at 60, 30, and 7 days before each deadline. Escalate to the partner at 7 days if the filing is not marked as submitted. Configurable reminder intervals.
- **Filing Checklist Generator**: For each deadline, generate a checklist of required forms, supporting schedules, computations, and documents. Track checklist completion percentage. Include IRD-specific requirements per form type.
- **Extension Application Tracker**: Track whether a block extension (via HKICPA) or individual extension has been applied for and granted. Auto-calculate the extended deadline. Alert if the extension is approaching expiry.
- **MPF Deadline Management**: Track monthly MPF contribution deadlines (contribution day of the following month). Flag late contributions which incur 5% surcharge. Handle new employee enrolment 60-day deadline.
- **Dashboard & Reporting**: Calendar view of upcoming deadlines across all clients. Traffic light status (green: filed, yellow: due within 30 days, red: overdue). Generate monthly compliance status reports for partners.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Scheduling | `APScheduler` with persistent SQLite job store |
| Calendar | `icalendar` for .ics export |
| WhatsApp | Twilio WhatsApp Business API |
| Email | `smtplib`, `email.mime` |
| PDF reports | `reportlab` |
| Date calculation | `python-dateutil`, `workalendar` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Web dashboard | `jinja2` templates, `htmx` |

## File Structure

```
/opt/openclaw/skills/local/tax-calendar-bot/
├── main.py                  # FastAPI app + scheduler
├── config.yaml              # IRD deadlines, reminder intervals, contacts
├── deadlines/
│   ├── calculator.py        # Deadline date computation engine
│   ├── profits_tax.py       # Profits Tax deadline rules
│   ├── employers_return.py  # BIR56A deadline rules
│   ├── mpf.py               # MPF contribution deadlines
│   └── business_reg.py      # BR renewal deadlines
├── reminders/
│   ├── scheduler.py         # Reminder job scheduling
│   ├── messenger.py         # WhatsApp/email dispatch
│   └── escalation.py        # Partner escalation logic
├── checklists/
│   ├── generator.py         # Filing checklist builder
│   └── templates/           # Per-form checklist templates
├── extensions/
│   └── tracker.py           # Extension application tracking
├── dashboard/
│   ├── routes.py            # Web dashboard
│   ├── calendar_view.py     # Calendar generation
│   └── templates/
│       ├── dashboard.html
│       ├── client_detail.html
│       └── calendar.html
└── tests/
    ├── test_deadlines.py
    ├── test_reminders.py
    └── test_checklists.py

~/OpenClawWorkspace/tax-calendar-bot/
├── taxcalendar.db           # SQLite database
├── checklists/              # Generated checklists
├── reports/                 # Compliance reports
└── ics_exports/             # Calendar .ics files
```

## Key Integrations

- **Twilio WhatsApp Business API**: Send deadline reminders and escalation alerts to accountants and partners.
- **SMTP Email**: Alternative/supplementary notification channel. Send filing checklists and compliance reports as PDF attachments.
- **Apple Calendar**: Export deadlines as .ics files for import into macOS Calendar. Support CalDAV subscription for live updates.
- **HKICPA Block Extension System**: Reference HKICPA's block extension dates published annually. Auto-populate extended deadlines for firms that participate.
- **IRD eTAX**: Reference IRD's published filing timetable and form versions.

## HK-Specific Requirements

- **IRD Filing Calendar**: The core of the HK tax year:
  - **Year of Assessment**: April 1 – March 31
  - **BIR51 (Profits Tax - Corp)**: Issued April 1. Due 1 month from issue (early May) for "N" code companies. "D" code (Dec year-end): mid-August. "M" code (Mar year-end): mid-November. Block extensions add ~1 month.
  - **BIR52 (Profits Tax - Partnership/Sole Prop)**: Same schedule as BIR51.
  - **BIR56A (Employer's Return)**: Issued April 1. Due within 1 month (early May). No extension available.
  - **BIR60 (Individual Tax Return)**: Issued May 1. Due within 1 month (early June). Extension available on request.
- **Block Extension Scheme**: HKICPA negotiates annual block extensions with IRD for member firms. Typical extensions:
  - "D" code: from mid-August to mid-November
  - "M" code: from mid-November to mid-January (next year)
  - "N" code: limited extension to end of May
  Store current year's block extension dates in config.
- **MPF Deadlines**: Employer contributions due on the contribution day (typically 10th) of the month following the wage period. Late contributions incur a 5% surcharge. New employees must be enrolled within 60 days of joining.
- **Business Registration Renewal**: Annual renewal due on anniversary of registration. 1-year fee: HK$2,250. 3-year fee: HK$5,950 (current rates, update annually). Late renewal incurs a HK$300 penalty.
- **Penalty Regime**: IRD imposes a surcharge of 5% immediately on overdue tax, rising to 10% after 6 months. Additional prosecution possible. This motivates strict deadline adherence.
- **Public Holidays**: If a deadline falls on a public holiday or Sunday, it extends to the next business day. Use `workalendar` with HK holiday calendar for accurate deadline calculation.

## Data Model

```sql
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    br_number TEXT,
    year_end_month INTEGER NOT NULL,
    ird_file_number TEXT,
    company_type TEXT DEFAULT 'corporation',
    assigned_accountant TEXT,
    accountant_phone TEXT,
    partner TEXT,
    partner_phone TEXT,
    mpf_scheme TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE deadlines (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    deadline_type TEXT NOT NULL,
    form_code TEXT,
    assessment_year TEXT,
    original_due_date DATE NOT NULL,
    extended_due_date DATE,
    extension_type TEXT,
    extension_status TEXT,
    filing_status TEXT DEFAULT 'not_started',
    submitted_date DATE,
    checklist_path TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reminders (
    id INTEGER PRIMARY KEY,
    deadline_id INTEGER REFERENCES deadlines(id),
    days_before INTEGER NOT NULL,
    scheduled_date DATE NOT NULL,
    channel TEXT DEFAULT 'whatsapp',
    recipient TEXT,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    escalated BOOLEAN DEFAULT FALSE
);

CREATE TABLE mpf_deadlines (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    period_month DATE NOT NULL,
    contribution_due_date DATE NOT NULL,
    amount_due REAL,
    paid BOOLEAN DEFAULT FALSE,
    paid_date DATE,
    surcharge_applied BOOLEAN DEFAULT FALSE
);

CREATE TABLE checklists (
    id INTEGER PRIMARY KEY,
    deadline_id INTEGER REFERENCES deadlines(id),
    total_items INTEGER,
    completed_items INTEGER DEFAULT 0,
    items TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Deadline calculator produces correct due dates for "D", "M", and "N" code companies
- [ ] Block extension correctly adjusts deadlines per HKICPA published dates
- [ ] Deadlines falling on a public holiday correctly shift to the next business day
- [ ] Reminder sends at exactly 60, 30, and 7 days before deadline via WhatsApp
- [ ] Partner escalation triggers at 7 days if filing_status is not "submitted"
- [ ] BIR56A checklist includes all required supporting schedules (IR56B, IR56E, IR56F)
- [ ] MPF monthly deadline tracker correctly flags a late contribution with 5% surcharge
- [ ] Dashboard traffic light correctly shows green/yellow/red for filed/upcoming/overdue items

## Implementation Notes

- **No LLM required**: This tool is entirely rule-based and calendar-driven. Memory footprint <200MB. Can run permanently in the background alongside other tools.
- **Deadline calculation engine**: Build a rules engine that computes deadlines from: company year-end month → IRD code category → base due date → block extension adjustment → public holiday adjustment. Codify rules from IRD's published filing timetable.
- **Annual configuration update**: Each April, the firm needs to update: block extension dates (from HKICPA), MPF contribution rates, BR renewal fees, and public holiday list. Provide a config update workflow that prompts for these values.
- **Bulk client onboarding**: Provide a CSV import for adding multiple clients at once. Required columns: company_name, br_number, year_end_month, ird_file_number, assigned_accountant.
- **Calendar subscription**: Generate an .ics file per client and a combined .ics for the firm. Support CalDAV subscription URL so macOS Calendar auto-updates when deadlines change.
- **Audit trail**: Log all status changes (reminder sent, filing marked submitted, extension applied) with timestamps. This creates a defensible record if IRD questions compliance.
- **Privacy**: Client tax information is confidential. All data stored locally. Mask BR numbers and IRD file numbers in logs. WhatsApp messages should reference client by code name, not full company name.
