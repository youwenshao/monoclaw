# PermitTracker

## Overview

PermitTracker monitors Hong Kong Buildings Department (BD) approval status for building plans, occupation permits, and minor works submissions. It scrapes the BD online portal for status updates, sends alerts when submissions progress through approval stages, and maintains a centralized dashboard of all active permits across multiple projects. Essential for Authorized Persons (AP), Registered Structural Engineers (RSE), and construction project managers.

## Target User

Hong Kong Authorized Persons (architects), Registered Structural Engineers, construction project managers, and property developers who submit plans to the Buildings Department and need to track approval status across multiple concurrent projects.

## Core Features

- **BD Portal Monitoring**: Automated scraping of the Buildings Department online systems (BRAVO, BISNET) to check submission status at configurable intervals
- **Status Change Alerts**: WhatsApp/email notifications when a submission transitions between stages (Received → Under Examination → Amendments Required → Approved → Consent Issued)
- **Minor Works Tracking**: Monitors Minor Works Control System (MWCS) submissions across all three classes (Class I, II, III) with category-specific timelines
- **NWSC Approvals**: Tracks New Works and Street Construction (NWSC) approvals and road opening permits
- **Multi-Project Dashboard**: Streamlit dashboard showing all active submissions across projects with filterable status views, overdue alerts, and timeline visualization
- **Document Management**: Stores submission documents, correspondence with BD, and amendment records linked to each permit application

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Web Scraping | Playwright (headless browser automation of BD portal), BeautifulSoup4 |
| Scheduler | APScheduler (periodic portal checks every 4-6 hours) |
| Notifications | Twilio WhatsApp API, smtplib |
| Database | SQLite |
| UI | Streamlit, Plotly (Gantt-style timeline visualization) |
| PDF | PyPDF2 |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/permit-tracker/
├── app.py                     # Streamlit multi-project dashboard
├── scrapers/
│   ├── bd_portal.py           # Buildings Department BRAVO/BISNET scraper
│   ├── minor_works.py         # Minor Works Control System status checker
│   ├── nwsc.py                # New Works/Street Construction tracker
│   └── parser.py              # HTML response parsing and data extraction
├── monitoring/
│   ├── status_monitor.py      # Periodic check scheduler and change detection
│   ├── alert_engine.py        # Status change notification dispatch
│   └── timeline.py            # Expected timeline calculation per submission type
├── notifications/
│   ├── whatsapp.py            # Twilio WhatsApp integration
│   └── email_sender.py        # Email notification sender
├── data/
│   ├── permits.db             # SQLite database
│   ├── bd_categories.json     # BD submission types and expected timelines
│   └── minor_works_classes.json # MWCS class/category definitions
├── requirements.txt
└── README.md
```

## Workspace Data Directory

```
~/OpenClawWorkspace/permit-tracker/
├── permits.db                 # SQLite database (runtime data)
├── documents/                 # Uploaded submission documents and BD correspondence
├── scraped_cache/             # Cached BD portal HTML responses
└── logs/                      # Scraper and alert engine logs
```

## Key Integrations

- **Buildings Department Portal (BRAVO/BISNET)**: Primary data source for building plan and occupation permit status
- **Minor Works Control System**: BD's online system for Class I/II/III minor works submissions
- **Twilio WhatsApp**: Real-time status change alerts to project stakeholders
- **Email (SMTP)**: Backup notification channel and formal status update distribution
- **Telegram Bot API**: Secondary channel for permit alerts, safety reminders, and subcontractor dispatch.

## GUI Specification

Part of the **Construction Dashboard** (`http://mona.local:8503`) — PermitTracker tab.

### Views

- **Gantt Timeline**: All submissions plotted against expected BD approval timelines. Actual progress overlaid with different colors. Submissions exceeding expected timelines highlighted in red.
- **Submission Cards**: Per-submission detail cards showing BD reference, type, current status, last checked timestamp, and days elapsed vs expected.
- **Alert History**: Chronological log of all status change alerts with timestamps and notification delivery status.
- **Document Archive**: Per-submission file repository for correspondence, plans, amendment records, and BD response letters.
- **Project Filter**: Dropdown to filter all views by project, submission type, or status.

### Mona Integration

- Mona scrapes BD portals on schedule and updates submission statuses automatically.
- Mona sends WhatsApp/email alerts when status changes are detected, showing in the Alert History.
- Human reviews and files BD correspondence; Mona tracks and organizes it.

### Manual Mode

- Project manager can manually add submissions, check status, upload documents, and review timelines without Mona.

## HK-Specific Requirements

- Buildings Ordinance (Cap 123): Governs the plan submission and approval process; tool must reflect the statutory approval workflow
- Building plan approval timeline: BD targets 60 days for first response on general building plans; tool should flag submissions exceeding this
- Minor Works Control System categories: Class I (requires prior approval from BD), Class II (requires prior notification to BD), Class III (requires only post-completion notification) — each has different tracking requirements
- Authorized Person (AP) and Registered Structural Engineer (RSE) registration numbers should be associated with submissions
- BD reference numbers: Format varies by submission type (e.g., BP/YYYY/XXXX for building plans); tool must correctly parse and store these
- Common BD submission types: General Building Plans (GBP), Foundation Plans, Superstructure Plans, Drainage Plans, Demolition Plans, Occupation Permits
- BD portal access: Some services require registered professional login; tool should support credential management for authorized users

## Data Model

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT NOT NULL,
    address TEXT,
    lot_number TEXT,
    district TEXT,
    authorized_person TEXT,
    rse TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    bd_reference TEXT UNIQUE,
    submission_type TEXT CHECK(submission_type IN ('GBP','foundation','superstructure','drainage','demolition','OP','minor_works','nwsc','other')),
    minor_works_class TEXT,
    minor_works_category TEXT,
    description TEXT,
    submitted_date DATE,
    current_status TEXT,
    last_checked TIMESTAMP,
    expected_completion DATE,
    notes TEXT
);

CREATE TABLE status_history (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    status TEXT NOT NULL,
    status_date TIMESTAMP,
    details TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    alert_type TEXT CHECK(alert_type IN ('status_change','overdue','reminder','error')),
    message TEXT,
    channel TEXT,
    sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    document_type TEXT,
    file_path TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Company Profile**: Company name, BD registered AP/RSE details, office address
2. **Projects**: Add active projects with address, lot number, district, and submission types
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, SMTP email for formal notifications
4. **BD Portal Credentials**: Login credentials for BRAVO/BISNET portal access (for authorized users)
5. **Sample Data**: Option to seed demo submissions for testing
6. **Connection Test**: Validates all API connections, BD portal access, and email delivery

## Testing Criteria

- [ ] Successfully scrapes BD portal and extracts current status for a known submission reference number
- [ ] Detects a status change from "Under Examination" to "Amendments Required" and sends WhatsApp alert
- [ ] Dashboard correctly displays all submissions for a project with color-coded status indicators
- [ ] Minor works tracking distinguishes between Class I, II, and III requirements
- [ ] Timeline visualization shows expected vs actual approval durations
- [ ] Overdue alert fires when a submission exceeds the expected BD response timeline
- [ ] Handles BD portal downtime gracefully with retry logic and error notifications

## Implementation Notes

- BD portal scraping with Playwright: use headless Chromium; implement random delays between requests (2-5 seconds) to avoid rate limiting
- Check portal every 4-6 hours during business hours (Mon-Fri 9:00-18:00 HKT); reduce to once daily on weekends/holidays
- Cache portal responses and compare against previous check to detect changes — only trigger alerts on actual status transitions
- Store raw HTML responses for debugging when parsing fails
- Expected timelines are estimates based on BD service pledges — allow project managers to customize expected durations per submission
- Memory budget: ~2GB (Playwright headless browser is the primary resource consumer; no LLM needed for this tool)
- Implement credential rotation if multiple BD portal accounts are needed for different AP registrations
- **Logging**: All operations logged to `/var/log/openclaw/permit-tracker.log` with daily rotation (7-day retention). BD credentials and personal details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. BD portal credentials stored with restricted file permissions (600). Site safety records maintained for statutory retention period (minimum 7 years for construction records).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, Playwright browser state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Safety records and permit history maintained in export for compliance.
