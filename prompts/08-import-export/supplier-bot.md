# SupplierBot

## Tool Name & Overview

SupplierBot is a WeChat-integrated communication agent that manages ongoing conversations with Mainland Chinese factories on behalf of Hong Kong import-export traders. It pings suppliers in the Pearl River Delta (Shenzhen, Dongguan, Guangzhou) for production updates, translates responses between Chinese (Mandarin/Cantonese) and English, and maintains a structured record of all supplier communications for easy reference. Designed to bridge the HK-Mainland supply chain communication gap.

## Target User

Hong Kong trading company sourcing managers, procurement officers, and small import-export business owners who communicate daily with Mainland Chinese factories and need to track production schedules, quality issues, and shipping timelines across multiple suppliers.

## Core Features

- **WeChat Message Management**: Sends and receives messages via WeChat Official Account or WeChat Work (企業微信) API, maintaining ongoing conversations with factory contacts
- **Automated Status Pings**: Sends scheduled production status requests to factories at configurable intervals (daily, weekly, or milestone-based) with follow-up reminders for non-responses
- **Real-Time Translation**: Translates factory responses from Simplified Chinese to English and trader messages from English to Chinese using local LLM, preserving industry terminology
- **Communication Log**: Maintains a searchable, structured record of all supplier conversations with auto-extracted key information (delivery dates, quantities, quality issues)
- **Multi-Factory Dashboard**: Overview of all active orders across suppliers with traffic-light status indicators based on latest communication
- **Template Messages**: Pre-built bilingual message templates for common requests — production schedule update, quality inspection request, shipping arrangement, payment confirmation

## Tech Stack

- **WeChat**: wechatpy library for WeChat Official Account API; WeChat Work API for enterprise messaging
- **LLM**: MLX local inference (Qwen-2.5-7B — strong Chinese language capability) for translation and information extraction
- **Database**: SQLite for supplier contacts, order tracking, conversation history, and extracted data
- **UI**: Streamlit dashboard for conversation management and order overview
- **Scheduler**: APScheduler for automated status ping scheduling

## File Structure

```
~/OpenClaw/tools/supplier-bot/
├── app.py                       # Streamlit supplier management dashboard
├── messaging/
│   ├── wechat_handler.py        # WeChat Official Account API integration
│   ├── wechat_work.py           # WeChat Work (企業微信) integration
│   ├── message_templates.py     # Bilingual message template library
│   └── auto_ping.py             # Scheduled status request automation
├── translation/
│   ├── translator.py            # CN<>EN translation via local LLM
│   ├── terminology.py           # Industry-specific term glossary
│   └── cantonese_handler.py     # Cantonese-specific translation handling
├── extraction/
│   ├── info_extractor.py        # Extract dates, quantities, issues from messages
│   └── order_updater.py         # Update order status from extracted information
├── models/
│   ├── llm_handler.py           # MLX inference wrapper
│   └── prompts.py               # Translation and extraction prompts
├── data/
│   ├── supplier.db              # SQLite database
│   └── glossary.json            # Trade terminology glossary (EN/SC/TC)
├── requirements.txt
└── README.md
```

## Key Integrations

- **WeChat Official Account API**: Primary communication channel with Mainland Chinese factory contacts
- **WeChat Work (企業微信)**: Enterprise messaging alternative for suppliers using WeChat Work
- **Local LLM (MLX)**: Translation and information extraction running entirely on-device — no sensitive order data sent to cloud translation services

## HK-Specific Requirements

- Cross-border communication norms: HK traders typically communicate with Mainland factories via WeChat (not email); voice messages are common from factory side — tool should handle voice message transcription
- Pearl River Delta factory hours: Typical factory working hours 8:00-12:00, 13:30-17:30 CST (same timezone as HK); avoid sending messages outside these hours
- Language complexity: HK traders may communicate in Cantonese-flavored Chinese, Traditional Chinese, English, or a mix; Mainland factory staff respond in Simplified Chinese (Mandarin); the tool must handle all variants
- Trade terminology: Manufacturing terms (模具/mould, 样品/sample, 质检/QC, 出货/shipping) must be translated accurately with industry context
- Payment terms: Common HK-Mainland payment structures — 30% deposit, 70% before shipping; T/T (telegraphic transfer); L/C (letter of credit) — tool should track payment milestones
- Chinese public holidays: Factory closures during Chinese New Year (typically 2-4 weeks), National Day Golden Week, and other Mainland holidays significantly affect production schedules
- Quality terminology: HK traders often reference AQL (Acceptable Quality Level) inspection standards; common quality issues should be tracked with standardized categories

## Data Model

```sql
CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY,
    company_name_en TEXT,
    company_name_cn TEXT NOT NULL,
    factory_location TEXT,
    contact_person TEXT,
    wechat_id TEXT,
    phone TEXT,
    product_categories TEXT,  -- JSON array
    payment_terms TEXT,
    reliability_score REAL DEFAULT 5.0,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_reference TEXT UNIQUE,
    product_description TEXT,
    quantity INTEGER,
    unit_price REAL,
    currency TEXT DEFAULT 'USD',
    order_date DATE,
    expected_delivery DATE,
    actual_delivery DATE,
    payment_status TEXT CHECK(payment_status IN ('pending_deposit','deposit_paid','balance_pending','fully_paid')) DEFAULT 'pending_deposit',
    production_status TEXT CHECK(production_status IN ('not_started','in_production','qc_pending','qc_passed','shipping','delivered','completed')) DEFAULT 'not_started',
    notes TEXT
);

CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_id INTEGER REFERENCES orders(id),
    direction TEXT CHECK(direction IN ('outbound','inbound')),
    original_text TEXT,
    translated_text TEXT,
    original_language TEXT,
    message_type TEXT CHECK(message_type IN ('text','voice','image','file')),
    extracted_data TEXT,  -- JSON: dates, quantities, issues
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE status_pings (
    id INTEGER PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(id),
    order_id INTEGER REFERENCES orders(id),
    ping_type TEXT,
    scheduled_time TIMESTAMP,
    sent_time TIMESTAMP,
    response_received BOOLEAN DEFAULT FALSE,
    response_time TIMESTAMP,
    follow_up_count INTEGER DEFAULT 0
);

CREATE TABLE glossary (
    id INTEGER PRIMARY KEY,
    term_en TEXT,
    term_sc TEXT,
    term_tc TEXT,
    category TEXT,
    context TEXT
);
```

## Testing Criteria

- [ ] Successfully sends a WeChat message to a test contact and receives the response
- [ ] Translates a factory production update from Simplified Chinese to English with correct trade terminology
- [ ] Auto-ping sends a scheduled status request at the configured time and logs the outbound message
- [ ] Information extractor correctly identifies a delivery date change from a Chinese message
- [ ] Dashboard shows order status updated based on extracted information from supplier messages
- [ ] Follow-up reminder fires after 24 hours of no response to a status ping
- [ ] Template message sends correctly in bilingual format (English + Simplified Chinese)

## Implementation Notes

- WeChat API access: WeChat Official Account requires business verification; WeChat Work may be easier for initial setup — implement both with a common interface
- Qwen-2.5-7B is an excellent choice for CN<>EN translation as it has strong multilingual capability, especially for Chinese
- Voice message handling: download WeChat voice messages (AMR format), convert to WAV, transcribe with Whisper, then translate — this is a common factory communication pattern
- Translation caching: cache translated messages to avoid re-translating repeated phrases; build a translation memory over time
- Factory response patterns: Mainland factories often send voice messages, photo updates of production, and short text messages — handle all media types
- Memory budget: ~5GB (Qwen LLM for translation is the primary consumer; WeChat API integration is lightweight)
- Auto-ping scheduling: respect factory working hours and avoid Chinese public holidays — pre-load the Mainland public holiday calendar
- Consider implementing a "morning briefing" that summarizes overnight messages from all suppliers in a single digest
