# Real Estate Dashboard

A unified productivity suite for Hong Kong real estate agents, combining four AI-powered tools: **PropertyGPT**, **ListingSync**, **TenancyDoc**, and **ViewingBot**. Built for Mac M4 (16GB RAM) and runs locally within the OpenClaw framework.

## Overview

| Tool | Purpose |
|------|---------|
| **PropertyGPT** | RAG-powered property search, comparable analysis, listing descriptions, floor plan OCR, and price trends |
| **ListingSync** | Multi-platform listing management (28Hse, Squarefoot, WhatsApp) with image processing, LLM description rewriting, and sync scheduling |
| **TenancyDoc** | Tenancy agreements, provisional contracts, CR109, inventory checklists, stamp duty calculator, and renewal tracking |
| **ViewingBot** | WhatsApp-based viewing coordination, scheduling engine, Apple Calendar integration, district routing, and weather alerts |

All four tools run as a single FastAPI application on **port 8001** at `http://mona.local:8001`, with tab-based navigation and a shared dashboard.

---

## Quick Start

### Prerequisites

- Python 3.11+
- macOS (ARM64 for MLX support; optional for mock LLM)

### Installation

```bash
cd tools/01-real-estate
pip install -e ".[all]"   # Full install with MLX, messaging, macOS extras
# Or minimal:
pip install -e .          # Core only (uses mock LLM)
```

### Running the Dashboard

```bash
uvicorn real_estate.app:app --host 0.0.0.0 --port 8001
```

Then open **http://localhost:8001** (or `http://mona.local:8001` if configured on your network).

### First-Run Setup

On first launch, you'll be guided through a setup wizard at `/setup/`:

1. **Business Profile** — Agency name, EAA license, office address
2. **Messaging** — Twilio (WhatsApp) and/or Telegram credentials
3. **Platform Credentials** — 28Hse, Squarefoot logins; Land Registry access
4. **Seed Demo Data** — Optional sample listings and viewings
5. **Connection Test** — Verify APIs and databases

After setup, set a **PIN** for dashboard access. The session persists for 24 hours by default.

---

## User Guide

### PropertyGPT

- **Search** — Filter by district, price range, bedrooms. Natural-language queries return ranked results with transaction history.
- **Compare** — Side-by-side comparison of selected properties with MTR proximity, school nets, and stamp duty.
- **Chat** — Ask questions about properties; responses cite source buildings and stream in real time.
- **Describe** — Generate listing descriptions from property data (Chinese-first for 28Hse, English-first for Squarefoot).
- **Floor Plan OCR** — Upload a floor plan image; extract room dimensions and areas via macOS Vision.
- **Trends** — Price trend charts and daily digest views.

### ListingSync

- **Create Listing** — Master form with image drag-drop. Add photos, details, and platform-specific notes.
- **Platform Status** — Grid view: rows = listings, columns = platforms. Green/amber/red indicators for sync status.
- **Image Processing** — Resize, watermark (EAA), and enhance before sync. Preview before/after.
- **Sync Controls** — "Sync All" or per-platform manual sync. Scheduling: 8–9am and 6–7pm HKT (configurable).
- **Performance** — Views and inquiries per platform. Weekly reports.

### TenancyDoc

- **Agreement Wizard** — Multi-step flow for tenancy agreements (fixed-term, periodic). Bilingual (EN/TC) output.
- **Provisional** — 臨時租約 with deposit, commission split, handover date.
- **Stamp Duty** — Calculator per IRD rates. Handles premium, rent-free periods, renewal options.
- **CR109** — Form CR109 (Notice of New Letting) generation and filing status.
- **Inventory** — Room-by-room checklist with condition notes and photo refs.
- **Renewals** — Calendar view of expiring tenancies. Alerts at 90/60/30 days. Renewal offer letters.

### ViewingBot

- **Calendar** — Weekly view of viewings. Color-coded by status (pending/confirmed/cancelled).
- **Route Map** — District map with today's viewings. Optimal route suggestion (nearest-neighbor).
- **Coordination Board** — Three-party status (viewer, landlord, agent). Confirm only when all accept.
- **Follow-Ups** — Interest tags (hot/warm/cold). Reminder workflow.
- **Weather** — HK Observatory alerts. Auto-cancel on T8+ or Black Rainstorm; trigger reschedule.

---

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `llm` | `provider` | `mock` (dev) or `mlx` (local inference) |
| `llm` | `model_path` | MLX model path (e.g. `mlx-community/Qwen2.5-7B-Instruct-4bit`) |
| `messaging` | `whatsapp_enabled` | Enable Twilio WhatsApp |
| `messaging` | `telegram_enabled` | Enable Telegram Bot |
| `database` | `workspace_path` | Data directory (default: `~/OpenClawWorkspace/real-estate`) |
| `auth` | `session_ttl_hours` | PIN session duration |
| `extra` | `stamp_duty_rates` | IRD rates (configurable for Budget changes) |
| `extra` | `watermark_*` | EAA watermark font size, opacity, position |
| `extra` | `default_viewing_start/end` | Viewing hours (e.g. 10:00–20:00) |

---

## API Reference

### Health & Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (tool, DB, LLM, memory) |
| POST | `/api/export` | Export all data as ZIP (backup, PDPO) |

### PropertyGPT

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/property-gpt/search` | Search with filters |
| POST | `/property-gpt/chat` | Streaming chat |
| POST | `/property-gpt/describe` | Generate listing description |
| POST | `/property-gpt/compare` | Compare properties |
| POST | `/property-gpt/ocr/floor-plan` | Floor plan OCR |
| GET | `/property-gpt/trends` | Price trends |

### ListingSync

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/listing-sync/listings` | Create listing |
| PUT | `/listing-sync/listings/{id}` | Update listing |
| POST | `/listing-sync/listings/{id}/sync` | Sync to platforms |
| POST | `/listing-sync/listings/{id}/process-images` | Process images |
| GET | `/listing-sync/performance` | Platform performance |

### TenancyDoc

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tenancy-doc/agreements` | Generate tenancy agreement |
| GET | `/tenancy-doc/stamp-duty/calculate` | Stamp duty calculator |
| POST | `/tenancy-doc/cr109` | Generate CR109 |
| POST | `/tenancy-doc/inventory` | Generate inventory |
| GET | `/tenancy-doc/renewals` | Renewal alerts |
| GET | `/tenancy-doc/documents` | Document archive |

### ViewingBot

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/viewing-bot/webhook` | Twilio incoming webhook |
| POST | `/viewing-bot/viewings` | Create viewing |
| GET | `/viewing-bot/viewings/today` | Today's viewings |
| POST | `/viewing-bot/viewings/{id}/confirm` | Confirm viewing |
| GET | `/viewing-bot/route/today` | Optimal route |
| GET | `/viewing-bot/weather` | Weather alerts |

---

## Architecture

```
tools/01-real-estate/
├── config.yaml              # Configuration
├── real_estate/
│   ├── app.py               # Unified FastAPI app
│   ├── database.py          # Schema init (5 SQLite DBs)
│   ├── dashboard/           # Jinja2 + htmx + Tailwind templates
│   ├── property_gpt/        # RAG, scrapers, OCR, HK utils
│   ├── listing_sync/        # Platforms, image processing, tracking
│   ├── tenancy_doc/         # Generators, stamp duty, renewals
│   └── viewing_bot/         # Messaging, scheduling, calendar
└── tests/
```

**Shared library** (`tools/shared/openclaw_shared/`): LLM abstraction, messaging (WhatsApp/Telegram), config, database, logging, health, auth, Mona events, export.

**Databases** (in `~/OpenClawWorkspace/real-estate/`):

- `property_gpt.db` — Buildings, transactions, query log
- `listing_sync.db` — Listings, platform posts, images
- `tenancy_doc.db` — Tenancies, documents, renewal alerts
- `viewing_bot.db` — Viewings, availability, follow-ups, message log
- `shared.db` — Cross-tool data (e.g. PropertyGPT → ListingSync)
- `mona_events.db` — Activity feed and approval queue

---

## Mona Integration

When **Mona** (the AI assistant) is active:

- **Activity Feed** — Right panel shows Mona's actions in real time
- **Approval Queue** — Amber-badged items needing human review
- Mona can auto-populate fields, trigger workflows, and surface results in the GUI

In **Manual Mode**, the dashboard works standalone without Mona.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| PIN forgotten | Delete `auth.pin_hash` from `config.yaml` and restart; you'll be prompted to set a new PIN |
| MLX out of memory | Use `llm.provider: mock` or reduce model size |
| 28Hse/Squarefoot sync fails | Check credentials in config; Playwright may need `playwright install chromium` |
| Apple Calendar not syncing | Grant Calendar access in System Preferences → Privacy |
| Floor plan OCR fails | Requires macOS with `pyobjc-framework-Vision`; install `.[macos]` extra |
| Logs | Check `/var/log/openclaw/real-estate.log` (or workspace log path) |

---

## Related

- **Prompts**: `prompts/01-real-estate/` — Full tool specifications for coding agents
- **Implementation Plan**: `.cursor/plans/real_estate_tools_implementation_65678dd6.plan.md`
- **Shared Library**: `tools/shared/` — LLM, messaging, auth, health, export
