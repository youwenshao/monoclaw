# HKDevKit

## Overview

HKDevKit is a collection of pre-built connectors and boilerplate generators for Hong Kong-specific API integrations. It provides ready-to-use Python modules for FPS (Faster Payment System), Octopus card merchant SDK, GovHK Open Data API, and other HK digital infrastructure — saving developers hours of reading documentation and writing integration code from scratch. Think of it as "HK-specific npm/pip packages" with code generation.

## Target User

Hong Kong software developers, startup CTOs, and freelance developers building applications that integrate with local HK payment systems, government data, and digital services — who want to skip the boilerplate and start building features immediately.

## Core Features

- **FPS Connector**: Pre-built integration module for HKMA FPS (Faster Payment System) including QR code generation, payment initiation, and payment status checking via participating bank APIs
- **Octopus API Wrapper**: Simplified Python wrapper for Octopus merchant SDK covering payment processing, transaction queries, and refund handling
- **GovHK Open Data Client**: Python client for the GovHK Open Data API with typed responses for popular datasets (weather, transport, demographic, geospatial)
- **Boilerplate Generator**: CLI tool that generates project scaffolding with selected HK integrations pre-configured (e.g., `hkdevkit init --fps --octopus --weather`)
- **Code Snippets Library**: Searchable library of HK-specific code snippets (address parsing, HKID validation, phone number formatting, bilingual string handling)
- **Documentation Generator**: Auto-generates integration docs from the boilerplate code using local LLM

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| HTTP | httpx for async API calls to HK services |
| QR Code | qrcode library for FPS QR code generation per HKMA EMV standard |
| CLI | Typer for the boilerplate generator command-line interface |
| LLM | MLX local inference for documentation generation and code snippet explanation |
| Database | SQLite for snippet library, project templates, and integration configuration |
| Templates | Jinja2 for project boilerplate code generation |
| Testing | pytest with VCR.py for recording and replaying API responses |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/hk-dev-kit/
├── app.py                        # Streamlit snippet browser and documentation
├── cli.py                        # Boilerplate generator CLI (hkdevkit command)
├── connectors/
│   ├── fps/
│   │   ├── qr_generator.py      # FPS QR code generation (EMV standard)
│   │   ├── payment_client.py    # FPS payment initiation and status
│   │   └── fps_types.py         # FPS data models and type definitions
│   ├── octopus/
│   │   ├── merchant_client.py   # Octopus merchant payment processing
│   │   ├── transaction.py       # Transaction queries and refunds
│   │   └── octopus_types.py     # Octopus data models
│   ├── govhk/
│   │   ├── open_data_client.py  # GovHK Open Data API client
│   │   ├── weather.py           # HK Observatory weather data
│   │   ├── transport.py         # Transport data (MTR, bus routes)
│   │   └── geodata.py           # HK geographic and address data
│   └── common/
│       ├── hkid_validator.py    # HKID check digit validation
│       ├── phone_formatter.py   # HK phone number formatting (+852)
│       └── address_parser.py    # HK address parsing (district, building, floor, unit)
├── generator/
│   ├── scaffolder.py            # Project boilerplate generation engine
│   ├── templates/               # Jinja2 project templates
│   └── config_builder.py        # Integration configuration generator
├── snippets/
│   ├── snippet_library.py       # Code snippet search and retrieval
│   └── snippets.json            # Curated HK-specific code snippets
├── models/
│   ├── llm_handler.py           # MLX inference for doc generation
│   └── prompts.py               # Documentation generation prompts
├── data/
│   └── hkdevkit.db              # SQLite database
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/hk-dev-kit/
├── data/
│   └── hkdevkit.db              # SQLite database
├── generated/                   # Generated boilerplate projects
└── logs/
    └── api_calls.log            # API call logs
```

## Key Integrations

- **HKMA FPS**: Faster Payment System integration via participating bank APIs (HSBC, Standard Chartered, Bank of China HK, Hang Seng)
- **Octopus Merchant SDK**: Octopus card payment processing for retail and F&B applications
- **GovHK Open Data API**: Government open data including weather, transport, demographics
- **HK Observatory API**: Real-time weather data, warnings, and forecasts
- **Local LLM (MLX)**: Documentation generation and code explanation
- **Telegram Bot API**: Secondary channel for build notifications and documentation alerts.

## GUI Specification

Part of the **Vibe Coder Dashboard** (`http://mona.local:8010`) — HKDevKit tab.

### Views

- **API Connector Gallery**: Visual cards for each HK-specific API (FPS, Octopus, GovHK, eTAX) with status indicator, documentation link, and "Generate Boilerplate" button.
- **Boilerplate Generator**: Select framework (Flask, FastAPI, Express, Next.js) + target APIs → generate project scaffold with pre-configured connectors. Download as ZIP or open in editor.
- **Integration Documentation Viewer**: Rendered markdown documentation for each API connector with code examples.
- **API Testing Interface**: Send test requests to configured APIs, view request/response pairs, and debug integration issues.

### Mona Integration

- Mona auto-generates boilerplate code tailored to the developer's selected tech stack and APIs.
- Mona provides contextual HK API documentation as the developer works.
- Developer reviews and customizes generated code.

### Manual Mode

- Developer can browse API documentation, generate boilerplate, and test API connections without Mona.

## HK-Specific Requirements

- FPS QR Code: Must follow HKMA's EMV QR Code Specification for Payment Systems (based on EMVCo standard with HK-specific merchant tags)
- FPS proxy types: Support FPS ID, mobile number, email address, and HK business registration number as payment proxies
- Octopus SDK: Follow Octopus Cards Limited's merchant integration specifications; handle the unique transaction flow (tap → authorize → confirm)
- HKID validation: Implement the check digit algorithm for HKID numbers (single letter prefix + 6 digits + check digit in parentheses, or dual letter prefix)
- HK address format: Parse the unique HK addressing convention — Territory > District > Estate/Building > Block > Floor > Unit (no postal/zip codes in HK)
- GovHK API rate limits: Respect rate limits on government open data endpoints; implement caching for frequently accessed datasets
- Bilingual data: GovHK APIs return data in both English and Chinese — connectors should expose both language versions
- HK phone number format: 8-digit local numbers; country code +852; mobile numbers start with 5/6/7/9

## Data Model

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT,
    integrations TEXT,  -- JSON array of enabled connectors
    created_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE snippets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    language TEXT DEFAULT 'python',
    category TEXT CHECK(category IN ('payment','validation','formatting','api','utility')),
    tags TEXT,  -- JSON array
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_configs (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL,
    base_url TEXT,
    auth_type TEXT,
    api_key TEXT,
    additional_config TEXT,  -- JSON
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE generated_docs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_type TEXT,
    content TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Developer Profile**: Name, preferred tech stack (Flask, FastAPI, Express, Next.js), and default project language
2. **HK API Keys**: Register FPS, Octopus, and GovHK API access credentials (where applicable)
3. **Project Setup**: Select default output directory for generated boilerplate projects
4. **Telegram**: Configure Telegram bot token for build notifications (optional)
5. **Sample Data**: Option to generate a demo project with pre-configured HK API connectors
6. **Connection Test**: Validates API access, LLM loading, and Telegram bot connectivity

## Testing Criteria

- [ ] FPS QR code generator produces a valid EMV QR code scannable by HSBC PayMe and Hang Seng mobile banking
- [ ] Octopus merchant client correctly formats a payment request per the SDK specification
- [ ] GovHK Open Data client retrieves current weather data with correct bilingual field names
- [ ] HKID validator correctly validates "A123456(7)" and rejects "A123456(8)"
- [ ] Boilerplate generator creates a runnable Python project with FPS integration pre-configured
- [ ] Code snippet search returns relevant results for "address validation" query
- [ ] HK phone number formatter correctly handles 8-digit numbers with and without +852 prefix

## Implementation Notes

- FPS integration: actual FPS payment APIs are bank-specific (each bank has its own API) — provide a unified interface with bank-specific adapters; start with HSBC and Standard Chartered
- Octopus SDK: the official Octopus merchant SDK may require a commercial agreement — provide the integration structure as a template that developers fill in with their merchant credentials
- GovHK API: no authentication required for most endpoints; implement request caching with configurable TTL (1 hour for weather, 24 hours for demographic data)
- HKID check digit algorithm: well-documented public algorithm — implement as a pure function with no external dependencies
- Boilerplate generator: use Jinja2 templates with conditional blocks based on selected integrations; generate requirements.txt, .env.example, and README.md alongside the code
- Memory budget: ~4GB when LLM is loaded for doc generation; ~500MB when running connectors only (no LLM needed for API calls)
- Testing: use VCR.py to record API responses for reproducible tests without hitting live endpoints
- Consider publishing the connectors as a standalone pip package (`pip install hkdevkit`) for the broader HK developer community
- **Logging**: All operations logged to `/var/log/openclaw/hk-dev-kit.log` with daily rotation (7-day retention). Code snippets truncated in logs to avoid leaking proprietary source code.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Source code never leaves the local machine — zero cloud processing for all inference.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM model state (loaded/warm/cold), and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON archive of conversation history, generated documentation, and configuration.
