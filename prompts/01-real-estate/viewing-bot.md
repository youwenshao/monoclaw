# ViewingBot — Automated Property Viewing Coordinator

## Overview

ViewingBot automates the scheduling and coordination of property viewings between landlords, tenants, and agents via WhatsApp. It handles viewing requests, checks calendar availability, detects scheduling conflicts, manages confirmations and reminders, and provides post-viewing follow-up — replacing the agent's manual back-and-forth messaging.

## Target User

Hong Kong estate agents who coordinate 5-15 property viewings daily across multiple properties and need to manage availability windows for landlords, schedule around existing appointments, and send bilingual confirmations — all through WhatsApp, the dominant communication channel in HK real estate.

## Core Features

- **WhatsApp Viewing Requests**: Parse incoming WhatsApp messages for viewing intent (e.g., "Can I see the flat at Taikoo Shing tomorrow at 3pm?"). Extract property reference, preferred date/time, and party size using local LLM.
- **Calendar Conflict Detection**: Check agent's calendar and property-specific availability windows. Detect double-bookings, travel time conflicts between viewings at different locations, and landlord blackout periods. Suggest the next 3 available slots.
- **Automated Three-Way Scheduling**: Coordinate between tenant (viewer), landlord (or current occupant), and agent. Send proposed times to all parties and confirm only when all accept. Handle rescheduling and cancellations gracefully.
- **Confirmation & Reminder System**: Send automated confirmations upon booking, reminders 24 hours and 2 hours before viewing, and day-of logistics (building access instructions, parking info). Include property photos and key details.
- **Post-Viewing Follow-Up**: Send a follow-up message 4 hours after viewing asking for feedback/interest. Log responses and flag hot leads for agent attention.
- **District-Based Routing**: Group viewings by district to minimize agent travel. Suggest optimal viewing order based on geographic proximity and time slots.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| WhatsApp | Twilio WhatsApp Business API |
| Calendar | `icalendar`, Apple Calendar via `pyobjc-framework-EventKit` |
| Scheduling | `APScheduler` |
| NLP date parsing | `dateparser` (multilingual) |
| Geolocation | Haversine distance calculation for district routing |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/viewing-bot/
├── main.py                  # FastAPI app + webhook receiver
├── config.yaml              # Twilio creds, working hours, district map
├── messaging/
│   ├── whatsapp.py          # Twilio send/receive handlers
│   ├── parser.py            # LLM-based intent extraction
│   └── templates/           # Message templates (EN + ZH)
│       ├── confirmation.yaml
│       ├── reminder.yaml
│       ├── follow_up.yaml
│       └── reschedule.yaml
├── scheduling/
│   ├── calendar.py          # Apple Calendar integration
│   ├── conflict.py          # Conflict detection engine
│   ├── optimizer.py         # District-based route optimizer
│   └── slots.py             # Available slot calculator
├── models/
│   └── intent.py            # Viewing request data model
└── tests/
    ├── test_parser.py
    ├── test_scheduling.py
    └── test_messaging.py

~/OpenClawWorkspace/viewing-bot/
├── viewing_data.db          # SQLite database
├── message_log/             # Archived conversations
└── exports/                 # Viewing reports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Bidirectional messaging for all viewing coordination. Webhook endpoint receives incoming messages, API sends responses and scheduled reminders.
- **Apple Calendar (EventKit)**: Read/write agent's macOS Calendar to check availability and create viewing appointments. Support multiple calendars (personal + work).
- **Google Maps / Apple Maps**: Distance and travel time estimation between viewing locations (optional, can use straight-line Haversine as fallback).
- **Property database**: Cross-reference with PropertyGPT's building database for property details, access instructions, and landlord contacts.
- **Telegram Bot API**: Secondary messaging channel for client communication. Supports the same booking/notification flows as WhatsApp.

## GUI Specification

Part of the **Real Estate Dashboard** (`http://mona.local:8001`) — ViewingBot tab.

### Views

- **Viewing Calendar**: Weekly calendar view with viewing appointments color-coded by status (pending=yellow, confirmed=green, completed=blue, cancelled=grey).
- **District Route Map**: Map showing today's viewings as pins with suggested route optimization lines and estimated travel times between locations.
- **Coordination Board**: Three-party status board for each viewing — viewer confirmed? landlord confirmed? agent available? — with quick-action buttons to send reminders.
- **Follow-Up Tracker**: Post-viewing response log with interest level tags (hot/warm/cold) and next-action suggestions.
- **Weather Alert Banner**: Live typhoon/rainstorm warning banner from HK Observatory API. Auto-cancellation controls for affected viewings.

### Mona Integration

- Mona parses incoming WhatsApp viewing requests and presents parsed data for human confirmation before scheduling.
- Mona handles the three-way confirmation flow automatically, showing progress in real-time on the Coordination Board.
- Mona sends reminders and follow-ups on schedule; human can override or add personal notes before sending.

### Manual Mode

- Agent can manually create viewings, manage confirmations, optimize routes, and track follow-ups without Mona.

## HK-Specific Requirements

- **Viewing Hours**: Standard HK property viewing window is 10:00am–8:00pm daily including weekends. Some luxury properties restrict viewings to weekdays only. Configured per property.
- **Cantonese/English Bilingual**: All message templates must exist in both Traditional Chinese and English. Detect language preference from incoming messages. Default to Chinese if ambiguous.
- **WhatsApp Dominance**: HK real estate communication runs almost entirely on WhatsApp. Support voice message transcription (Twilio media → Whisper-compatible transcription) as secondary input.
- **District Geography**: HK districts have distinct boundaries affecting travel time. Island Line ↔ Kowloon requires cross-harbour tunnel (add 20 min). NT properties may need 30+ min travel from urban areas. Use district-to-district travel time matrix.
- **Building Access**: Many HK buildings require visitor registration at the management office. Include standard access instructions in confirmation messages (e.g., "Register at G/F management office with HKID").
- **Phone Format**: All HK phone numbers are +852 followed by 8 digits. Mobile numbers start with 5, 6, 7, or 9.
- **Typhoon/Rainstorm Protocol**: Auto-cancel and reschedule viewings when T8+ signal or Black Rainstorm warning is active. Poll HK Observatory API for weather warnings.

## Data Model

```sql
CREATE TABLE viewings (
    id INTEGER PRIMARY KEY,
    property_ref TEXT NOT NULL,
    property_address TEXT,
    district TEXT,
    viewer_name TEXT,
    viewer_phone TEXT NOT NULL,
    landlord_phone TEXT,
    agent_phone TEXT,
    proposed_datetime TIMESTAMP NOT NULL,
    confirmed_datetime TIMESTAMP,
    status TEXT DEFAULT 'pending',
    viewer_confirmed BOOLEAN DEFAULT FALSE,
    landlord_confirmed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE availability_windows (
    id INTEGER PRIMARY KEY,
    property_ref TEXT NOT NULL,
    day_of_week INTEGER,
    start_time TIME,
    end_time TIME,
    landlord_blackout_dates TEXT
);

CREATE TABLE follow_ups (
    id INTEGER PRIMARY KEY,
    viewing_id INTEGER REFERENCES viewings(id),
    sent_at TIMESTAMP,
    response TEXT,
    interest_level TEXT,
    next_action TEXT
);

CREATE TABLE message_log (
    id INTEGER PRIMARY KEY,
    viewing_id INTEGER REFERENCES viewings(id),
    direction TEXT,
    phone TEXT,
    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Business Profile**: Agency name, EAA license number, office address, operating hours
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, default message language (EN/TC)
3. **Platform Credentials**: Apple Calendar access, Google Maps/Apple Maps API key, and HK Observatory weather API endpoint (where applicable)
4. **Sample Data**: Option to seed demo data for testing before going live
5. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] Intent parser correctly extracts property, date, and time from 10 sample WhatsApp messages in both English and Chinese
- [ ] Conflict detection identifies double-bookings and suggests alternative slots
- [ ] Three-way confirmation flow completes: viewer requests → agent confirms → landlord confirms → all notified
- [ ] Reminder messages fire at exactly 24 hours and 2 hours before the viewing time
- [ ] Post-viewing follow-up sends 4 hours after scheduled time and logs response
- [ ] District routing groups 3 viewings in the same area and suggests optimal order
- [ ] Typhoon T8 signal triggers automatic cancellation and rescheduling of affected viewings
- [ ] Message templates render correctly in both Traditional Chinese and English

## Implementation Notes

- **LLM for parsing only**: The LLM is used exclusively for intent extraction from natural language messages. All scheduling logic is deterministic. If LLM fails to parse, reply with a structured form requesting the information.
- **Webhook architecture**: Twilio webhooks POST to the FastAPI endpoint. Process asynchronously — acknowledge within 1 second, then handle scheduling in a background task.
- **Calendar permissions**: macOS EventKit requires user approval for calendar access. Handle the permission dialog gracefully on first run. Fall back to SQLite-only scheduling if calendar access is denied.
- **Memory**: LLM loads only when parsing is needed, then can be unloaded. Steady-state memory <1GB without LLM loaded.
- **Rate limiting**: Twilio WhatsApp has a per-number rate limit. Queue outgoing messages with 1-second spacing to avoid throttling.
- **Privacy**: Phone numbers and viewing history are sensitive. Store in local SQLite only. Mask phone numbers in logs (`+852 9XXX XX89`). Never share viewer details with other viewers.
- **Logging**: All operations logged to `/var/log/openclaw/viewing-bot.log` using Python `logging` module with daily rotation (7-day retention). PII (phone numbers, HKID, names) is masked in all log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Local dashboard requires PIN authentication on first access. All API credentials stored in `config.yaml` with restricted file permissions (600).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM model state, and memory usage. Consumed by the Mona Hub launcher.
- **Data export**: Supports `POST /api/export` to generate a portable JSON + files archive of all tool data for backup or migration.
