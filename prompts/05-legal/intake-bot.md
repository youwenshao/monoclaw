# IntakeBot

## Tool Name & Overview

IntakeBot is a client intake automation tool that collects new client details via WhatsApp and WeChat, performs conflict-of-interest checks against the firm's existing client database, and schedules initial consultation meetings. It streamlines the first-contact-to-meeting pipeline for Hong Kong law firms, reducing manual data entry and ensuring regulatory compliance with conflict checking obligations.

## Target User

Hong Kong law firm receptionists, intake coordinators, junior solicitors, and small firm sole practitioners who need to efficiently onboard new clients while maintaining rigorous conflict-of-interest compliance per SFC and HKLS (Hong Kong Law Society) rules.

## Core Features

- **Multi-Channel Intake**: Accepts new client enquiries via WhatsApp Business API and WeChat Official Account with guided conversation flows in English, Traditional Chinese, and Simplified Chinese
- **Structured Data Collection**: Conversational bot gathers client name, HKID (last 4 digits for verification), contact details, matter type, adverse party details, and urgency level
- **Conflict of Interest Check**: Cross-references new client and adverse party names against the firm's existing client/matter database using fuzzy matching (Levenshtein distance + phonetic matching for Chinese names)
- **Meeting Scheduler**: Integrates with solicitor calendars to offer available consultation slots; sends confirmation via WhatsApp/WeChat with office address and preparation checklist
- **Intake Form Generation**: Auto-populates the firm's standard client intake form (PDF/Word) from collected data for solicitor review and client signature
- **Engagement Letter Draft**: Generates a draft engagement letter based on matter type, pre-filled with client details and standard fee arrangements

## Tech Stack

- **Messaging**: Twilio WhatsApp Business API; WeChat Official Account API (wechatpy library)
- **LLM**: MLX local inference for conversational flow management and intent classification
- **Fuzzy Matching**: rapidfuzz for name matching; pypinyin + jyutping for Chinese phonetic matching
- **Calendar**: Google Calendar API or Microsoft Graph API for availability checking
- **Database**: SQLite for client database, conflict log, and intake history
- **Document Generation**: python-docx for intake forms and engagement letters; reportlab for PDF output
- **UI**: Streamlit admin dashboard for intake queue management

## File Structure

```
~/OpenClaw/tools/intake-bot/
├── app.py                    # Streamlit admin dashboard
├── bot/
│   ├── whatsapp_handler.py   # Twilio webhook handler for WhatsApp messages
│   ├── wechat_handler.py     # WeChat Official Account message handler
│   ├── conversation_flow.py  # Guided intake conversation state machine
│   └── intent_classifier.py  # LLM-based intent detection for free-text messages
├── conflict/
│   ├── checker.py            # Conflict of interest search engine
│   ├── fuzzy_match.py        # Name matching with phonetic support
│   └── conflict_report.py    # Generates conflict check report
├── scheduling/
│   ├── calendar_sync.py      # Calendar API integration
│   └── slot_manager.py       # Available slot computation and booking
├── documents/
│   ├── intake_form.py        # Client intake form generator
│   └── engagement_letter.py  # Draft engagement letter generator
├── models/
│   ├── llm_handler.py        # MLX inference wrapper
│   └── prompts.py            # Conversation and classification prompts
├── data/
│   ├── intake.db             # SQLite database
│   └── templates/            # Document templates (intake form, engagement letter)
├── requirements.txt
└── README.md
```

## Key Integrations

- **Twilio WhatsApp Business API**: Primary client communication channel; webhook-based message handling
- **WeChat Official Account API**: Secondary channel for Mainland Chinese clients communicating via WeChat
- **Calendar API**: Google Calendar or Microsoft 365 for solicitor availability and booking
- **Local LLM (MLX)**: Conversational intent classification and freeform message understanding

## HK-Specific Requirements

- HKLS Practice Direction P on conflict of interest: Firms must check all new matters against existing clients and adverse parties before accepting instructions
- SFC licensed firms (for those also holding SFC licenses) have additional conflict rules under the SFC Code of Conduct Section 10
- PDPO (Personal Data (Privacy) Ordinance, Cap 486): Client data collected during intake must be handled in compliance — collect only necessary data, provide PICS (Personal Information Collection Statement)
- HKID handling: Only collect last 4 digits for identity verification; never store full HKID numbers
- Bilingual name matching: Must handle English names, Traditional Chinese names, Simplified Chinese names, and romanized Chinese names (multiple romanization systems: Jyutping, Yale, government romanization)
- Standard HK law firm fee arrangements: Hourly rate, fixed fee, or conditional fee (limited scope per Barristers' and Solicitors' fees rules)
- Meeting scheduling should account for HK business hours (typically 9:00-18:00 HKT, UTC+8) and public holidays

## Data Model

```sql
CREATE TABLE clients (
    id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_tc TEXT,
    hkid_last4 TEXT,
    phone TEXT,
    email TEXT,
    wechat_id TEXT,
    whatsapp_number TEXT,
    source_channel TEXT CHECK(source_channel IN ('whatsapp','wechat','walk_in','referral','website')),
    intake_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending_review'
);

CREATE TABLE matters (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    matter_type TEXT,
    description TEXT,
    adverse_party_name TEXT,
    adverse_party_name_tc TEXT,
    urgency TEXT CHECK(urgency IN ('urgent','normal','low')),
    assigned_solicitor TEXT,
    status TEXT DEFAULT 'intake',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conflict_checks (
    id INTEGER PRIMARY KEY,
    matter_id INTEGER REFERENCES matters(id),
    checked_against TEXT,
    match_score REAL,
    match_type TEXT,
    result TEXT CHECK(result IN ('clear','potential_conflict','confirmed_conflict')),
    reviewed_by TEXT,
    check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id),
    matter_id INTEGER REFERENCES matters(id),
    solicitor TEXT,
    datetime TIMESTAMP,
    duration_minutes INTEGER DEFAULT 60,
    location TEXT DEFAULT 'office',
    status TEXT CHECK(status IN ('scheduled','confirmed','completed','cancelled','no_show')),
    confirmation_sent BOOLEAN DEFAULT FALSE
);
```

## Testing Criteria

- [ ] WhatsApp intake flow collects all required fields (name, phone, matter type, adverse party) in under 8 messages
- [ ] Conflict check correctly identifies a fuzzy name match (e.g., "Chan Tai Man" vs "陳大文") with confidence score
- [ ] Returns "clear" when no conflict exists after checking against 1,000+ client records
- [ ] Successfully books a meeting slot and sends WhatsApp confirmation with office address
- [ ] Generates a pre-filled intake form PDF with all collected client data
- [ ] Handles a WeChat conversation in Simplified Chinese and maps data correctly
- [ ] HKID last-4-digit validation rejects invalid formats

## Implementation Notes

- Run the WhatsApp/WeChat webhook server as a lightweight Flask/FastAPI service alongside the Streamlit dashboard
- Use SQLite FTS5 (full-text search) for fast conflict checking across the client database
- Chinese phonetic matching: convert Traditional Chinese names to Jyutping, Simplified Chinese to Pinyin, then compare phonetically — this catches many romanization variants
- Keep the conversation state machine simple (5-7 states) to avoid confusing clients; offer a "speak to human" escape hatch at every stage
- LLM inference is needed only for freeform message understanding — structured button responses should bypass the LLM entirely
- Memory usage: the bot server + LLM should fit within ~8GB, leaving headroom for other tools on 16GB M4
- Store conversation logs for compliance but implement automatic purging after the matter's retention period expires per HKLS guidelines
