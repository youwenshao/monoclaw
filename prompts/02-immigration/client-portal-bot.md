# ClientPortal Bot — Immigration Application Status Bot

## Overview

ClientPortal Bot provides real-time immigration application status updates to clients via WhatsApp and Telegram. Clients can query their application progress, receive automated milestone notifications, get document submission reminders, and schedule consultation appointments — reducing the constant "what's my status?" calls that consume consultant time.

## Target User

Hong Kong immigration consultants managing 30-100 active client cases who receive frequent status inquiry calls/messages. The bot handles routine status queries autonomously, freeing consultants to focus on complex case work and client strategy.

## Core Features

- **Status Query Bot**: Clients send a message (WhatsApp or Telegram) with their case reference or name and receive an instant status update including current stage, estimated timeline, and next required action. Supports English, Traditional Chinese, and Simplified Chinese.
- **Automated Milestone Notifications**: When a case status changes (e.g., "Documents submitted to ImmD", "Approval received", "Visa label ready for collection"), automatically notify the client with a clear explanation of what happens next.
- **Document Submission Reminders**: Track outstanding documents per client. Send reminders at configurable intervals (7/3/1 days before deadline). Include specific document requirements and submission instructions.
- **Appointment Scheduling**: Clients can request consultation slots through the bot. Show available times, confirm bookings, and send calendar invitations. Handle rescheduling and cancellations.
- **FAQ Auto-Response**: Answer common immigration questions using a curated FAQ database enhanced with local LLM for natural language understanding. Topics: processing times, required documents, scheme eligibility, fee schedules.
- **Consultant Escalation**: When the bot cannot answer a query or detects client frustration, seamlessly escalate to the human consultant with full conversation context. Consultant can reply through the same channel.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| WhatsApp | Twilio WhatsApp Business API |
| Telegram | `python-telegram-bot` |
| Scheduling | `APScheduler` |
| Date/time | `python-dateutil`, `pytz` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Calendar | `icalendar` for .ics generation |

## File Structure

```
/opt/openclaw/skills/local/client-portal-bot/
├── main.py                  # FastAPI app + bot entry
├── config.yaml              # API keys, business hours, message limits
├── bot/
│   ├── whatsapp.py          # Twilio webhook handler
│   ├── telegram.py          # Telegram bot handler
│   ├── router.py            # Intent detection and routing
│   └── escalation.py        # Human handoff logic
├── status/
│   ├── tracker.py           # Case status management
│   ├── milestones.py        # Milestone notification engine
│   └── timeline.py          # Processing time estimator
├── reminders/
│   ├── documents.py         # Document deadline tracker
│   └── scheduler.py         # Reminder scheduling
├── faq/
│   ├── engine.py            # FAQ matching with LLM fallback
│   └── knowledge_base.yaml  # Curated Q&A pairs
├── appointments/
│   └── booking.py           # Consultation scheduling
├── templates/
│   ├── en/                  # English message templates
│   └── zh/                  # Chinese message templates
└── tests/
    ├── test_status.py
    ├── test_bot.py
    └── test_faq.py

~/OpenClawWorkspace/client-portal-bot/
├── portal.db                # SQLite database
├── conversation_log/        # Message archives
└── exports/                 # Status reports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Primary client communication channel. Handle inbound webhooks and outbound message templates. Support media messages (document photos, PDF receipts).
- **Telegram Bot API**: Secondary channel for clients who prefer Telegram. Mirror functionality from WhatsApp bot.
- **VisaDoc OCR (sibling tool)**: When clients send document photos via WhatsApp, route to VisaDoc OCR for extraction and auto-update their document checklist.
- **FormAutoFill (sibling tool)**: Pull client data from the shared client database for form generation.
- **PolicyWatcher (sibling tool)**: When policy changes affect active cases, trigger proactive client notifications.

## HK-Specific Requirements

- **Immigration Department Processing Times**: Maintain a reference table of typical processing times by scheme:
  - GEP: 4-6 weeks
  - ASMTP: 4-6 weeks
  - QMAS: 9-12 months
  - TTPS: 4 weeks
  - IANG: 2-4 weeks
  - Dependant visa: 4-6 weeks
  Update estimates based on reported actual times.
- **Common Application Statuses**: Use standard status labels that map to ImmD's actual process: `Documents Gathering` → `Application Submitted` → `Acknowledgement Received` → `Additional Documents Requested` → `Under Processing` → `Approval in Principle` → `Visa Label Issued` → `Entry Made` → `HKID Applied`.
- **Bilingual Responses**: All bot messages must be available in English (default for foreign applicants) and Traditional Chinese. Detect language from client's message. Support Simplified Chinese for mainland applicants.
- **Business Hours**: Bot operates 24/7 for status queries and FAQ. Appointment scheduling limited to business hours (Mon-Fri 9am-6pm, Sat 9am-1pm HKT). Escalation to consultant only during business hours; queue messages outside hours.
- **Phone Number Formats**: Support HK (+852), mainland China (+86), and international numbers. Parse and normalize all formats for database consistency.
- **Public Holidays**: HK has 17 public holidays. Exclude from appointment availability. Account for holidays when estimating processing times (ImmD is closed).

## Data Model

```sql
CREATE TABLE cases (
    id INTEGER PRIMARY KEY,
    reference_code TEXT UNIQUE NOT NULL,
    client_id INTEGER,
    client_name TEXT NOT NULL,
    client_phone TEXT,
    client_telegram_id TEXT,
    scheme TEXT NOT NULL,
    current_status TEXT DEFAULT 'documents_gathering',
    status_updated_at TIMESTAMP,
    submitted_date DATE,
    estimated_completion DATE,
    consultant_name TEXT,
    consultant_phone TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE status_history (
    id INTEGER PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    status TEXT NOT NULL,
    notes TEXT,
    notified_client BOOLEAN DEFAULT FALSE,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE outstanding_documents (
    id INTEGER PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    document_type TEXT NOT NULL,
    description TEXT,
    deadline DATE,
    received BOOLEAN DEFAULT FALSE,
    received_date DATE,
    last_reminder_sent TIMESTAMP
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    datetime TIMESTAMP NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    type TEXT DEFAULT 'consultation',
    status TEXT DEFAULT 'confirmed',
    notes TEXT
);

CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    case_id INTEGER,
    channel TEXT NOT NULL,
    sender TEXT NOT NULL,
    message_text TEXT,
    intent TEXT,
    escalated BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Status query returns correct case information when client provides valid reference code
- [ ] Bot correctly handles queries in English, Traditional Chinese, and Simplified Chinese
- [ ] Milestone notification fires within 5 minutes of a status change in the database
- [ ] Document reminder sends at exactly 7, 3, and 1 day before deadline
- [ ] Appointment booking shows only available slots (respecting business hours and public holidays)
- [ ] Escalation to human consultant includes full conversation history and case context
- [ ] FAQ engine answers top 20 common immigration questions accurately
- [ ] Bot gracefully handles unknown queries with a helpful "I'll connect you with your consultant" response

## Implementation Notes

- **Dual-channel architecture**: Abstract the messaging layer so WhatsApp and Telegram share the same router, status engine, and FAQ logic. Only the transport layer (webhook format, message sending API) differs.
- **LLM for intent and FAQ only**: Use the LLM for intent classification (status query, document question, appointment request, FAQ, other) and FAQ answer generation. All status lookups and scheduling are deterministic database queries. LLM can be lazy-loaded.
- **Conversation context**: Maintain a sliding window of the last 10 messages per client for context. Pass this context to the LLM when generating FAQ responses. Clear context after 24 hours of inactivity.
- **Rate limiting**: Cap outbound messages at 1 per second per channel. Twilio WhatsApp Business has template message requirements for messages sent >24 hours after last client message — use approved templates for proactive notifications.
- **Memory**: Steady-state <500MB without LLM. With LLM loaded for active conversation, ~5.5GB. Unload LLM after 5 minutes of no incoming messages.
- **Privacy**: Client case data is highly sensitive. All data stays local. Mask case reference codes in logs. Implement message retention policy: conversation logs auto-delete after 180 days. Client can request data deletion via the bot.
