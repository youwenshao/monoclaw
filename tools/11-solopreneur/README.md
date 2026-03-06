# Solopreneur Dashboard

Unified FastAPI application providing four business productivity tools for Hong Kong solopreneurs and small business owners, accessible at `http://mona.local:8506`.

## Tools

| Tool | Purpose |
|------|---------|
| **BizOwner OS** | WhatsApp inbox, POS aggregation, transaction logging, P&L, cash flow, CRM, and daily digest |
| **MPFCalc** | MPF calculation engine, remittance reports, payroll processor, and compliance reminders |
| **SupplierLedger** | Invoice management, payment tracking, aging reports, statements, and overdue reminders |
| **SocialSync** | Multi-platform publishing (Instagram, Facebook, WhatsApp Status), content optimization, scheduling, and analytics |

## Quick Start

### Prerequisites

- Python 3.11+

### Installation

```bash
cd tools/11-solopreneur
pip install -e ../shared
pip install -e .
# Or with messaging (WhatsApp/Telegram):
pip install -e ".[messaging]"
```

### Running the Dashboard

```bash
python -m solopreneur.app
```

Or with uvicorn:

```bash
uvicorn solopreneur.app:app --host 0.0.0.0 --port 8506
```

Then open **http://localhost:8506**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### BizOwner OS

- **WhatsApp Inbox** — Centralized customer messages with auto-responder and broadcast.
- **POS Integration** — Connect iChef, Lightspeed, Square, or CSV; aggregate sales and inventory.
- **Accounting** — Transaction logger, categorizer, P&L report, and cash flow projection.
- **CRM** — Customer database and engagement tracking.
- **Daily Digest** — Morning summary of key metrics and alerts.

### MPFCalc

- **MPF Engine** — HK-compliant contribution calculation with income rules and voluntary contributions.
- **Remittance** — Generate remittance reports and annual summaries.
- **Payroll** — Employee manager and contribution processor.
- **Compliance** — Reminder notifications for contribution deadlines.

### SupplierLedger

- **Invoice Manager** — Track supplier invoices, payment terms, and due dates.
- **Aging Engine** — Aging reports and collection forecasting.
- **Statements** — Generate and send supplier statements (PDF).
- **Reminders** — Overdue alerts with configurable intervals.

### SocialSync

- **Publishing** — Post to Instagram, Facebook, WhatsApp Status from one dashboard.
- **Content** — Image/video optimizer, caption optimizer, CTA generator.
- **Scheduling** — Calendar view, optimal posting times (lunch, evening, prime).
- **Analytics** — IG/FB metrics and report generation.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `pos_provider` | `ichef`, `lightspeed`, `square`, or `csv` |
| `extra` | `mpf_trustee` | `hsbc`, `aia`, `manulife`, `sunlife`, `bct` |
| `extra` | `mpf_contribution_day` | Day of month for contributions (default: 10) |
| `extra` | `default_payment_terms_days` | Supplier payment terms |
| `extra` | `instagram_access_token` | Instagram API credentials |
| `extra` | `profits_tax_rate_tier1` | HK profits tax rate (first tier) |

## Architecture

```
tools/11-solopreneur/
├── config.yaml
├── solopreneur/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── biz_owner_os/
│   ├── mpf_calc/
│   ├── supplier_ledger/
│   └── social_sync/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/solopreneur/`): `bizowner.db`, `mpf.db`, `ledger.db`, `socialsync.db`, `shared.db`, `mona_events.db`

## Running Tests

```bash
cd tools/11-solopreneur
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/solopreneur_tool_implementation_f60d27d8.plan.md`
- **Shared Library**: `tools/shared/`
