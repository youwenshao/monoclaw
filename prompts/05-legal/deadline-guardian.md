# DeadlineGuardian

## Overview

DeadlineGuardian is a court deadline and limitation period tracking tool purpose-built for Hong Kong litigation practice. It auto-calculates limitation periods under the Limitation Ordinance, tracks filing deadlines for CFI and DCT proceedings, and sends escalating reminders to ensure no critical date is missed. The tool integrates with the HK Judiciary's e-Litigation portal concepts for deadline synchronization.

## Target User

Hong Kong litigation solicitors, litigation clerks, and practice managers who manage multiple active cases and need reliable tracking of court deadlines, limitation periods, and procedural time limits.

## Core Features

- **Limitation Period Calculator**: Computes deadlines under Cap 347 — 6 years for contract claims, 3 years for personal injury, 1 year for defamation, with automatic adjustment for accrual date and discoverability
- **Court Filing Deadlines**: Tracks time-limited procedural steps — acknowledgment of service (14 days), defence filing (28 days), discovery compliance, and pre-trial review dates
- **Escalating Reminders**: APScheduler-driven notifications at configurable intervals (30 days, 14 days, 7 days, 3 days, 1 day) via WhatsApp, email, and desktop notification
- **Calendar Integration**: Generates .ics files for import into Outlook/Google Calendar; optional CalDAV sync
- **Dashboard View**: Streamlit dashboard showing all active deadlines color-coded by urgency (green/amber/red)
- **Audit Trail**: Full log of when deadlines were created, modified, acknowledged, and completed

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Scheduler | APScheduler with SQLite job store for persistent, crash-resilient scheduling |
| Notifications | Twilio WhatsApp API for mobile alerts; smtplib for email notifications |
| Calendar | icalendar library for .ics generation; caldav library for optional CalDAV sync |
| Database | SQLite for cases, deadlines, and reminder history |
| UI | Streamlit with calendar view and countdown timers |
| Date Handling | python-dateutil for business day calculation, HK public holiday awareness |

## File Structure

```
/opt/openclaw/skills/local/deadline-guardian/
├── app.py                    # Streamlit dashboard
├── calculator/
│   ├── limitation.py         # Cap 347 limitation period logic
│   ├── court_deadlines.py    # CFI/DCT procedural deadline rules
│   └── business_days.py      # HK business day and holiday calculator
├── scheduler/
│   ├── reminder_engine.py    # APScheduler setup and job management
│   └── escalation.py         # Multi-stage reminder escalation logic
├── notifications/
│   ├── whatsapp.py           # Twilio WhatsApp integration
│   ├── email_sender.py       # SMTP email notifications
│   └── desktop.py            # macOS native notification via osascript
├── integrations/
│   ├── calendar_export.py    # .ics file generation
│   └── e_litigation.py       # HK e-Litigation portal interface stub
├── data/
│   ├── deadlines.db          # SQLite database
│   └── hk_holidays.json      # HK public holiday schedule (updated yearly)
├── requirements.txt
└── README.md
```

### Workspace Data Directory

```
~/OpenClawWorkspace/deadline-guardian/
├── calendar_exports/         # Generated .ics files
├── reminder_logs/            # Notification delivery history
└── case_data/                # Case-specific deadline snapshots
```

## Key Integrations

- **Twilio WhatsApp**: Sends deadline reminders to solicitors' mobile devices
- **Email (SMTP)**: Backup notification channel for all deadline alerts
- **Calendar (iCal/CalDAV)**: Exports deadlines to standard calendar applications
- **HK e-Litigation**: Stub integration for future connection to Judiciary's electronic filing system
- **Telegram Bot API**: Secondary messaging channel for client intake, deadline reminders, and status updates.

## GUI Specification

Part of the **Legal Dashboard** (`http://mona.local:8501`) — DeadlineGuardian tab.

### Views

- **Matter List**: Active cases with their most urgent upcoming deadline, days remaining, and urgency indicator.
- **Calendar View**: Full calendar with deadlines color-coded by type (court filing=blue, limitation period=red, contractual=green). Click to view details.
- **Limitation Calculator**: Interactive form — select ordinance provision, enter trigger/accrual date, and instantly see the calculated deadline with business day adjustments.
- **Reminder Configuration**: Per-matter escalation settings (which channels, at what intervals, who receives).
- **Audit Trail**: Complete log of when each deadline was created, modified, reminded, acknowledged, and completed.

### Mona Integration

- Mona sends escalating reminders via WhatsApp/email/desktop notification as deadlines approach.
- Mona auto-calculates procedural deadlines from case events (e.g., writ issued → AoS due in 14 days).
- Human creates and acknowledges deadlines; Mona handles the reminder pipeline.

### Manual Mode

- Solicitor can manually create deadlines, calculate limitation periods, export to calendar, and review audit trails without Mona.

## HK-Specific Requirements

- Limitation Ordinance (Cap 347): Section 4 (contract — 6 years), Section 4A (personal injury — 3 years), Section 27 (defamation — 1 year), Section 4C (latent damage — 3 years from discoverability)
- Court of First Instance (CFI) deadlines: Acknowledgment of Service (14 days), Defence (28 days from AoS), Close of Pleadings (+14 days after last pleading), Summons for Directions (within 1 month of close of pleadings)
- District Court (DCT) deadlines follow similar but not identical timelines — tool must distinguish between CFI and DCT tracks
- HK public holidays (17 statutory holidays) affect deadline computation — court deadlines falling on a holiday extend to the next business day
- Saturday handling: Saturdays are not court working days for filing deadline purposes
- Practice Direction SL10 governs electronic filing and service, relevant for deadline computation

## Data Model

```sql
CREATE TABLE cases (
    id INTEGER PRIMARY KEY,
    case_number TEXT UNIQUE,
    case_name TEXT,
    court TEXT CHECK(court IN ('CFI','DCT','Lands Tribunal','Labour Tribunal','Other')),
    case_type TEXT,
    client_name TEXT,
    solicitor_responsible TEXT,
    status TEXT DEFAULT 'active',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE deadlines (
    id INTEGER PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    deadline_type TEXT,
    description TEXT,
    due_date DATE NOT NULL,
    trigger_date DATE,
    statutory_basis TEXT,
    status TEXT CHECK(status IN ('upcoming','due_soon','overdue','completed','waived')) DEFAULT 'upcoming',
    completed_date TIMESTAMP,
    notes TEXT
);

CREATE TABLE reminders (
    id INTEGER PRIMARY KEY,
    deadline_id INTEGER REFERENCES deadlines(id),
    reminder_date TIMESTAMP,
    channel TEXT CHECK(channel IN ('whatsapp','email','desktop')),
    sent_status TEXT DEFAULT 'pending',
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Firm Profile**: Firm name, SFC/HKLS registration details, office address, practice areas
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, WeChat Official Account credentials (if applicable)
3. **Calendar Integration**: Google Calendar or Microsoft 365 API credentials for solicitor availability and deadline sync
4. **Court Configuration**: Select active court tracks (CFI, DCT, Lands Tribunal, Labour Tribunal); import existing case/deadline data
5. **HK Legal Rules**: Confirm Limitation Ordinance (Cap 347) periods and court deadline rules are current; upload updated HK public holiday schedule
6. **Sample Data**: Option to seed demo cases and contracts for testing
7. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] Correctly calculates 6-year limitation period from a given accrual date, excluding HK public holidays for the final day
- [ ] Produces accurate CFI procedural deadlines given a writ issue date (AoS, Defence, Close of Pleadings)
- [ ] Sends WhatsApp reminder via Twilio at 7-day and 1-day marks before a deadline
- [ ] Dashboard displays deadlines color-coded by urgency with correct countdown
- [ ] Generates valid .ics file importable into macOS Calendar
- [ ] Handles Saturday/Sunday/public holiday rollover correctly for court filing deadlines
- [ ] Audit trail records all deadline creation, modification, and acknowledgment events

## Implementation Notes

- Use APScheduler's SQLAlchemyJobStore backed by SQLite so scheduled reminders survive application restarts
- Pre-load the HK public holiday list as a JSON file — update annually; the government gazette publishes these by October each year
- For limitation period calculation, always work in calendar days from accrual date and only apply business-day rules for the final deadline day
- Keep the reminder engine as a background thread within the Streamlit app, or run as a separate lightweight daemon
- macOS desktop notifications use `osascript -e 'display notification'` — no additional dependencies needed on M4 Mac
- Memory footprint should remain under 500MB since this tool is primarily date computation and scheduling, not LLM-heavy
- Consider adding a "what-if" calculator that lets solicitors explore limitation scenarios before formally creating a deadline
- **Logging**: All operations logged to `/var/log/openclaw/deadline-guardian.log` with daily rotation (7-day retention). Client names, case details, and privileged content masked in log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Dashboard requires PIN authentication. Legal documents are highly sensitive — zero cloud processing. Implement audit trail for all data access.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Privilege-tagged documents must maintain their tags in the export.
