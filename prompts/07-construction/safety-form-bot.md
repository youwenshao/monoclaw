# SafetyForm Bot

## Overview

SafetyForm Bot automates daily construction site safety checks with photo evidence upload, generates SSSS (Smart Site Safety System) compliance documentation, and manages toolbox talk records. It provides a WhatsApp-based interface for site safety officers to complete checks from the field and produces audit-ready safety documentation for regulatory inspection.

## Target User

Hong Kong construction site safety officers, site agents, project managers, and safety consultants who are responsible for daily safety inspections, SSSS compliance reporting, and maintaining safety records under the Factories and Industrial Undertakings Ordinance.

## Core Features

- **Daily Safety Checklist**: Structured checklist delivered via WhatsApp each morning covering housekeeping, PPE compliance, scaffolding, excavation safety, lifting operations, and fire precautions — with photo upload for each item
- **Photo Evidence Logging**: Geotagged, timestamped photos attached to specific checklist items; auto-organized by date, site, and safety category
- **SSSS Compliance Reports**: Generates documentation aligned with CIC's Smart Site Safety System requirements, including daily safety inspection records and monthly safety statistics
- **Toolbox Talk Templates**: Library of bilingual (EN/TC) toolbox talk scripts covering common HK construction hazards; tracks attendance and completion
- **Incident Reporting**: Structured incident/near-miss reporting form with immediate notification escalation to project management
- **Monthly Safety Statistics**: Auto-generates monthly safety KPIs — accident frequency rate, incident rate, safety training hours, near-miss reporting rate

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Messaging | Twilio WhatsApp Business API |
| Image Processing | Pillow, exifread (GPS/timestamp extraction) |
| LLM | MLX local inference |
| Database | SQLite |
| UI | Streamlit |
| PDF | reportlab |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/safety-form-bot/
├── app.py                      # Streamlit safety management dashboard
├── bot/
│   ├── whatsapp_handler.py     # Twilio webhook for field submissions
│   ├── checklist_flow.py       # Daily checklist conversation flow
│   └── incident_reporter.py    # Incident/near-miss reporting flow
├── inspections/
│   ├── checklist_engine.py     # Checklist template management and scoring
│   ├── photo_processor.py      # Photo geotagging, timestamping, storage
│   └── deficiency_tracker.py   # Track open safety deficiencies to resolution
├── reporting/
│   ├── ssss_report.py          # SSSS compliance documentation generator
│   ├── monthly_stats.py        # Monthly safety KPI calculations
│   ├── toolbox_talk.py         # Toolbox talk template and attendance management
│   └── pdf_generator.py        # PDF report generation for all report types
├── data/
│   ├── safety.db               # SQLite database
│   ├── checklists/             # Checklist templates (JSON)
│   └── toolbox_talks/          # Toolbox talk scripts (EN/TC markdown)
├── requirements.txt
└── README.md
```

## Workspace Data Directory

```
~/OpenClawWorkspace/safety-form-bot/
├── safety.db                  # SQLite database (runtime data)
├── photos/                    # Uploaded inspection and deficiency photos
├── reports/                   # Generated SSSS compliance and monthly PDFs
├── checklists/                # Customized checklist templates per site
└── toolbox_talks/             # Completed toolbox talk records
```

## Key Integrations

- **Twilio WhatsApp**: Primary field interface for safety officers submitting daily checks from construction sites
- **Local LLM (MLX)**: Analyzes free-text safety observations and helps categorize deficiencies
- **Photo Storage**: Local filesystem with organized directory structure by date/site/category
- **Telegram Bot API**: Secondary channel for permit alerts, safety reminders, and subcontractor dispatch.

## GUI Specification

Part of the **Construction Dashboard** (`http://mona.local:8503`) — SafetyForm tab.

### Views

- **Daily Checklist Interface**: Interactive safety checklist with checkboxes, photo attachment per item, and text notes. Pre-populated with date, site, and weather conditions.
- **SSSS Report Generator**: One-click generation of Site Safety Supervision Scheme reports from completed checklists.
- **Toolbox Talk Records**: Form for recording toolbox talk topics, attendee names (with signature capture), and duration.
- **Compliance Calendar**: Calendar showing required inspection dates, audit deadlines, and training renewal dates.
- **Photo Evidence Gallery**: Searchable gallery of all safety-related photos organized by date and checklist item.

### Mona Integration

- Mona sends morning reminders to site supervisors to complete daily checklists via WhatsApp.
- Mona auto-generates SSSS reports from completed checklist data.
- Human conducts inspections, takes photos, and signs off on checklists.

### Manual Mode

- Supervisor can manually fill checklists, upload photos, generate reports, and manage the compliance calendar without Mona.

## HK-Specific Requirements

- Factories and Industrial Undertakings Ordinance (Cap 59): Governs workplace safety in construction; safety inspections must comply with subsidiary regulations
- Construction Sites (Safety) Regulations: Specific requirements for scaffolding inspection, lifting equipment, excavation, and personal protective equipment
- CIC Smart Site Safety System (SSSS): CIC-mandated safety management system for registered contractors; tool must generate SSSS-compliant inspection records
- Construction Industry Council Ordinance (CICO): CIC registration requirements for safety officers and safety supervisors
- Labour Department (LD) safety standards: Safety inspections must align with LD codes of practice and guidance notes
- Mandatory safety training: Green Card (Construction Industry Safety Training Certificate) is required for all site workers — tool should track training currency
- Bilingual requirements: All safety documentation must be available in English and Traditional Chinese for regulatory submission
- Common HK construction hazards: Working at height (bamboo scaffolding is common in HK), confined spaces, heat stress (subtropical climate), typhoon preparedness

## Data Model

```sql
CREATE TABLE sites (
    id INTEGER PRIMARY KEY,
    site_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    project_type TEXT,
    contractor TEXT,
    safety_officer TEXT,
    cic_registration TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE daily_inspections (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    inspection_date DATE,
    inspector TEXT,
    overall_score REAL,
    status TEXT CHECK(status IN ('in_progress','completed','reviewed')) DEFAULT 'in_progress',
    weather TEXT,
    temperature REAL,
    worker_count INTEGER,
    completed_at TIMESTAMP
);

CREATE TABLE checklist_items (
    id INTEGER PRIMARY KEY,
    inspection_id INTEGER REFERENCES daily_inspections(id),
    category TEXT,
    item_description TEXT,
    status TEXT CHECK(status IN ('pass','fail','na','pending')),
    photo_path TEXT,
    photo_lat REAL,
    photo_lng REAL,
    photo_timestamp TIMESTAMP,
    notes TEXT,
    deficiency_id INTEGER
);

CREATE TABLE deficiencies (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    category TEXT,
    description TEXT,
    severity TEXT CHECK(severity IN ('critical','major','minor','observation')),
    photo_path TEXT,
    reported_date DATE,
    due_date DATE,
    resolved_date DATE,
    resolved_by TEXT,
    status TEXT DEFAULT 'open'
);

CREATE TABLE incidents (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    incident_type TEXT CHECK(incident_type IN ('accident','near_miss','dangerous_occurrence','property_damage')),
    date_time TIMESTAMP,
    location_on_site TEXT,
    description TEXT,
    persons_involved TEXT,
    injuries TEXT,
    immediate_action TEXT,
    root_cause TEXT,
    corrective_action TEXT,
    reported_to_ld BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'open'
);

CREATE TABLE toolbox_talks (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    talk_date DATE,
    topic TEXT,
    language TEXT,
    conductor TEXT,
    attendee_count INTEGER,
    attendee_names TEXT,
    duration_minutes INTEGER,
    notes TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Company Profile**: Company name, CIC registration details, office address
2. **Sites**: Add active construction sites with address, district, and project type
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, SMTP email for formal notifications
4. **Safety Templates**: Upload or select standard safety checklist templates for the project type
5. **Personnel Directory**: Import safety officer and site supervisor contact list with Green Card expiry dates
6. **Sample Data**: Option to seed demo checklists and inspections for testing
7. **Connection Test**: Validates all API connections and message delivery

## Testing Criteria

- [ ] Daily checklist delivers all category items via WhatsApp and accepts photo + pass/fail responses
- [ ] Photo uploads are correctly geotagged and timestamped with EXIF data extraction
- [ ] SSSS compliance report generates a valid PDF with all required fields for a completed inspection day
- [ ] Deficiency tracker correctly transitions items from "open" to "resolved" with photo evidence
- [ ] Monthly safety statistics accurately calculate accident frequency rate from incident data
- [ ] Toolbox talk templates render correctly in both English and Traditional Chinese
- [ ] Incident report triggers immediate WhatsApp notification to project manager

## Implementation Notes

- WhatsApp photo handling: Twilio provides a URL for uploaded media; download and store locally with structured naming (`{site_id}/{date}/{category}_{item_id}.jpg`)
- EXIF GPS extraction may not work if the photo was taken with location services disabled — fall back to the site's registered GPS coordinates
- Checklist templates should be JSON-configurable so different site types (building, civil, renovation) can have customized inspection items
- SSSS report format: follow CIC's published templates closely — these are subject to audit
- Heat stress consideration: include automatic weather-based alerts when the Hong Kong Observatory issues Very Hot Weather Warning — trigger additional hydration checks
- Memory budget: ~3GB (image processing is the heaviest operation; LLM only for free-text analysis)
- Implement offline mode: safety officers may lose connectivity on site — queue submissions locally and sync when connection resumes
- **Logging**: All operations logged to `/var/log/openclaw/safety-form-bot.log` with daily rotation (7-day retention). BD credentials and personal details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. BD portal credentials stored with restricted file permissions (600). Site safety records maintained for statutory retention period (minimum 7 years for construction records).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, Playwright browser state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Safety records and permit history maintained in export for compliance.
