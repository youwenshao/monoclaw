# Accounting Dashboard

Unified FastAPI application providing four productivity tools for Hong Kong accounting firms and CPAs, accessible at `http://mona.local:8004`.

## Tools

| Tool | Purpose |
|------|---------|
| **InvoiceOCR Pro** | Invoice and receipt OCR (Vision/Tesseract), fapiao parsing, categorisation, duplicate detection, and push to Xero/ABSS/QuickBooks |
| **ReconcileAgent** | Bank statement parsing (HSBC, Hang Seng, BOC, etc.), matching engine with date/amount tolerance, FX and FPS handling, discrepancy reporting |
| **FXTracker** | HKMA rate fetching, multi-currency transaction logging, FIFO revaluation, realized/unrealized P&L, tax schedule and charts |
| **TaxCalendar Bot** | Profits tax, employers' return, MPF, BR renewal deadlines; reminder intervals; extension tracking; checklist generation |

## Quick Start

```bash
cd tools/04-accounting
pip install -e ../shared
pip install -e .
python -m accounting.app
```

The dashboard launches at `http://localhost:8004`. On first run, complete the setup wizard at `/setup/`.

## User Guide

### InvoiceOCR Pro

Watched folder for incoming invoices. Vision or Tesseract OCR with confidence thresholds. Invoice, receipt, and fapiao parsers. Auto-categorisation via chart of accounts. Duplicate detection. Push to accounting software (Xero, ABSS, QuickBooks stubs).

### ReconcileAgent

Import bank statements (CSV, OFX, PDF). Multi-bank parser support. Matching with date tolerance (days) and amount tolerance. Fuzzy matching for payee names. FX rate tolerance for multi-currency. Discrepancy report and audit trail.

### FXTracker

Active currencies (USD, CNH, EUR, GBP, JPY, SGD). Rate fetch at configurable time with retries. FIFO revaluation. Realized and unrealized P&L. Tax schedule for profits tax. Rate alerts when HKD peg band is breached.

### TaxCalendar Bot

Profits tax (D/M/N codes), employers' return, MPF contribution day, BR renewal. Reminder intervals (60, 30, 7 days). Escalation and block-extension dates. Checklist generator. HK public holidays aware.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `watched_folder` | InvoiceOCR incoming path |
| `extra` | `ocr_engine` | `vision` or `tesseract` |
| `extra` | `date_tolerance_days`, `amount_tolerance` | ReconcileAgent matching |
| `extra` | `active_currencies`, `fx_method` | FXTracker settings |
| `extra` | `reminder_intervals`, `block_extension_dates` | TaxCalendar |

## Architecture

```
tools/04-accounting/
├── config.yaml
├── accounting/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── invoice_ocr/
│   ├── reconcile_agent/
│   ├── fx_tracker/
│   ├── tax_calendar/
│   └── dashboard/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/accounting/`): `invoice_ocr.db`, `reconcile_agent.db`, `fx_tracker.db`, `tax_calendar.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/04-accounting
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/accounting_tools_implementation_74272897.plan.md`
- **Shared Library**: `tools/shared/`
