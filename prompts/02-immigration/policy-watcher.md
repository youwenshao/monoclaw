# PolicyWatcher — Government Gazette Immigration Monitor

## Overview

PolicyWatcher monitors the Hong Kong Government Gazette, Immigration Department announcements, and Legislative Council papers for immigration policy changes. It detects modifications to visa schemes, quota adjustments, and regulatory updates, generates plain-language change summaries, and alerts immigration consultants so they can advise clients proactively.

## Target User

Hong Kong immigration consultants and law firms who need to stay current on rapidly evolving immigration policies (e.g., Top Talent Pass Scheme updates, QMAS quota changes, new talent list professions) but lack the bandwidth to manually review government publications daily.

## Core Features

- **Gazette Scraper**: Daily automated scraping of the Hong Kong Government Gazette (gazette.gov.hk) for Legal Notices, Government Notices, and subsidiary legislation related to the Immigration Ordinance (Cap. 115).
- **Policy Change Detection**: Compare newly fetched documents against previously stored versions using semantic diffing. Identify additions, deletions, and modifications to immigration-related policies. Highlight changes in eligibility criteria, salary thresholds, quota numbers, and processing procedures.
- **AI-Powered Summarization**: Use local LLM to generate consultant-friendly summaries of policy changes. Transform legal language into actionable bullet points: what changed, who is affected, effective date, and recommended client actions.
- **Multi-Source Monitoring**: Beyond the Gazette, monitor Immigration Department press releases, LegCo panel papers on security and immigration, and Talent List updates. Consolidate all sources into a unified feed.
- **Alert System**: Push summaries via WhatsApp and email to subscribed consultants. Support per-consultant alert preferences (e.g., only GEP changes, only QMAS updates). Include urgency classification (routine / important / urgent).
- **Policy Archive**: Maintain a searchable archive of all immigration policy changes with dates, source URLs, and AI summaries. Enable consultants to search historical changes by keyword or date range.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| Web scraping | `httpx`, `beautifulsoup4`, `lxml` |
| PDF extraction | `pdfplumber`, `pdf2image` |
| Text diffing | `difflib`, custom semantic diff |
| Scheduling | `APScheduler` |
| Full-text search | `sqlite3` FTS5 |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Notifications | Twilio WhatsApp Business API, `smtplib` |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/policy-watcher/
├── main.py                  # FastAPI app + scheduler
├── config.yaml              # Source URLs, scrape schedule, alert config
├── scrapers/
│   ├── gazette.py           # Government Gazette scraper
│   ├── immd.py              # Immigration Department news scraper
│   ├── legco.py             # LegCo papers scraper
│   └── talent_list.py       # Talent List update checker
├── analysis/
│   ├── differ.py            # Text comparison engine
│   ├── summarizer.py        # LLM-based change summarizer
│   └── classifier.py        # Urgency and topic classification
├── alerts/
│   ├── dispatcher.py        # Multi-channel alert sender
│   └── preferences.py       # Per-user alert settings
├── archive/
│   └── search.py            # FTS5 search interface
└── tests/
    ├── test_scrapers.py
    ├── test_differ.py
    └── test_summarizer.py

~/OpenClawWorkspace/policy-watcher/
├── gazette_archive/         # Downloaded gazette PDFs
├── policy_snapshots/        # Point-in-time policy text
├── summaries/               # Generated change summaries
└── policy_watcher.db        # SQLite + FTS5 database
```

## Key Integrations

- **Hong Kong Government Gazette (gazette.gov.hk)**: Primary source for legal notices and subsidiary legislation. Published every Friday with extraordinary gazettes as needed.
- **Immigration Department (immd.gov.hk)**: Press releases, scheme announcements, form updates, and processing time notices.
- **Legislative Council (legco.gov.hk)**: Panel on Security papers, bills committee reports, and government responses to questions on immigration policy.
- **Talent List (talentlist.gov.hk)**: Updates to the list of professions eligible for streamlined visa processing.
- **Twilio WhatsApp Business API**: Deliver alert summaries to consultants' WhatsApp.
- **Telegram Bot API**: Secondary messaging channel for client communication and status updates.
- **SMTP**: Email delivery for formal policy change notifications.

## GUI Specification

Part of the **Immigration Dashboard** (`http://mona.local:8002`) — PolicyWatcher tab.

### Views

- **Policy Feed**: Chronological timeline of detected policy changes with severity badges (critical/important/informational).
- **Diff Viewer**: Side-by-side comparison showing previous vs new policy text with red/green highlighting for deletions/additions.
- **Alert Configuration**: Panel to select which immigration schemes to monitor, notification channels, and escalation preferences.
- **Impact Assessment**: Cards showing which active client cases are potentially affected by a policy change, with recommended actions.

### Mona Integration

- Mona scrapes the Government Gazette and ImmD website on schedule, detecting and classifying changes automatically.
- Mona cross-references changes against active client cases and generates impact assessments.
- Human reviews impact assessments and decides which clients to notify.

### Manual Mode

- Consultant can manually browse policy history, run impact assessments, and configure monitoring preferences without Mona.

## HK-Specific Requirements

- **Immigration Ordinance (Cap. 115)**: All immigration policies derive from this ordinance and its subsidiary legislation. Monitor amendments to Cap. 115 and related regulations (Immigration Regulations, Immigration (Places of Detention) Order, etc.).
- **Key Schemes to Monitor**:
  - General Employment Policy (GEP) — salary requirements, job categories
  - Admission Scheme for Mainland Talents and Professionals (ASMTP) — quota, eligibility
  - Quality Migrant Admission Scheme (QMAS) — points thresholds, annual quota (currently ~4,000)
  - Top Talent Pass Scheme (TTPS) — university list, salary threshold (currently HK$2.5M)
  - Technology Talent Admission Scheme (TechTAS) — eligible tech parks, quota
  - Immigration Arrangements for Non-local Graduates (IANG) — eligible institutions, time limits
- **Gazette Structure**: Legal Notices are numbered sequentially (e.g., L.N. 123 of 2025). Government Notices use "G.N." prefix. Each notice has a section, number, and gazetted date. Parse these identifiers for accurate referencing.
- **Bilingual Legislation**: All HK legislation is enacted in both English and Chinese. Scrape both language versions and note any discrepancies (rare but important).
- **Policy Cycle**: Major immigration policy changes typically follow Budget season (February) and Policy Address (October). Increase scraping frequency during these periods.
- **Quota Announcements**: QMAS and some other schemes have annual quotas. Detect quota announcements and track remaining allocation if published.

## Data Model

```sql
CREATE TABLE policy_sources (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    last_scraped TIMESTAMP,
    scrape_frequency_hours INTEGER DEFAULT 24,
    enabled BOOLEAN DEFAULT TRUE
);

CREATE TABLE policy_documents (
    id INTEGER PRIMARY KEY,
    source_id INTEGER REFERENCES policy_sources(id),
    title TEXT NOT NULL,
    title_zh TEXT,
    document_url TEXT,
    local_path TEXT,
    content_text TEXT,
    content_hash TEXT,
    gazette_ref TEXT,
    published_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE policy_changes (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES policy_documents(id),
    previous_document_id INTEGER,
    change_type TEXT,
    change_summary TEXT,
    affected_schemes TEXT,
    urgency TEXT DEFAULT 'routine',
    effective_date DATE,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alert_subscriptions (
    id INTEGER PRIMARY KEY,
    consultant_name TEXT,
    phone TEXT,
    email TEXT,
    schemes_filter TEXT,
    urgency_threshold TEXT DEFAULT 'important',
    channel TEXT DEFAULT 'whatsapp'
);

CREATE TABLE alert_log (
    id INTEGER PRIMARY KEY,
    change_id INTEGER REFERENCES policy_changes(id),
    subscription_id INTEGER REFERENCES alert_subscriptions(id),
    sent_at TIMESTAMP,
    channel TEXT,
    delivery_status TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Practice Profile**: Firm name, immigration consultant registration number, office address
2. **Monitoring Sources**: Select government sources to monitor (Gazette, ImmD, LegCo, Talent List), set scrape frequency
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, SMTP credentials, default alert language
4. **Alert Preferences**: Configure alert recipients, urgency thresholds, and notification channels
5. **Sample Data**: Option to seed historical policy archive with recent gazette entries for testing
6. **Connection Test**: Validates source website access, messaging API connections, and reports any issues

## Testing Criteria

- [ ] Gazette scraper retrieves all Legal Notices from the current week's Government Gazette
- [ ] Policy differ correctly identifies text additions, deletions, and modifications between two document versions
- [ ] LLM summarizer produces 3-5 bullet point summaries in plain English from legal notice text
- [ ] Alert dispatcher sends WhatsApp notifications to subscribed consultants within 1 hour of detection
- [ ] Full-text search returns relevant archived policies for queries like "QMAS quota 2025"
- [ ] Urgency classifier correctly rates a quota change as "urgent" and a minor procedural update as "routine"
- [ ] Scraper handles gazette.gov.hk downtime gracefully with retry logic
- [ ] Historical archive stores at least 12 months of policy documents without exceeding 2GB disk

## Implementation Notes

- **Scraping ethics**: Government websites are public information. Respect `robots.txt`, use 3-second delays between requests, identify with a descriptive User-Agent string. Cache aggressively — the Gazette is published weekly and doesn't change retroactively.
- **LLM for summarization only**: Load the LLM when a new policy change is detected, generate the summary, then unload. The tool spends 99% of its time idle or scraping (no LLM needed). Steady-state RAM <500MB.
- **Change detection strategy**: First-pass uses content hash comparison (fast, catches any change). Second-pass uses `difflib.unified_diff` for structural comparison. Third-pass uses LLM for semantic interpretation of the change's significance.
- **FTS5 for search**: SQLite FTS5 extension provides fast full-text search over the policy archive. Create a virtual table covering document titles, content, and summaries. Supports Chinese tokenization with the `unicode61` tokenizer.
- **Scheduling**: Default scrape schedule: Gazette (Fridays 10am HKT), ImmD news (daily 8am), LegCo papers (Mondays 9am). Use `APScheduler` with persistent job store backed by SQLite.
- **Privacy**: This tool processes only public government documents. No personal data. The only PII is consultant contact info for alerts — store encrypted and respect unsubscribe requests.
- **Logging**: All operations logged to `/var/log/openclaw/policy-watcher.log` using Python `logging` module with daily rotation (7-day retention). PII (phone numbers, HKID, passport numbers, names) is masked in all log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Local dashboard requires PIN authentication on first access. All API credentials stored in `config.yaml` with restricted file permissions (600). Immigration data is among the most sensitive in the MonoClaw suite — zero cloud processing for document content.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/OCR engine state, and memory usage.
- **Data export**: Supports `POST /api/export` to generate a portable JSON + files archive of all tool data for backup or PDPO compliance.
