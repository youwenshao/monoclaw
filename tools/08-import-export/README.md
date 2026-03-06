# Import/Export Dashboard

Unified FastAPI application providing four import/export productivity tools for Hong Kong traders, accessible at `http://mona.local:8008`.

## Tools

| Tool | Purpose |
|------|---------|
| **TradeDoc AI** | HS code classification (FTS5 + LLM), strategic screening, TDEC/invoice/CO generators, and filing tracker |
| **SupplierBot** | WeChat/WeChat Work messaging, bilingual templates, auto-ping scheduler, order updates, and terminology glossary |
| **FXInvoice** | Multi-currency invoice generation, PDF export, FX rate fetcher/cache, hedging advisor, payment tracker, and aging reports |
| **StockReconcile** | Manifest, packing list, and receipt parsing; 3-pass matching engine; FCL/LCL reconciliation; discrepancy handling |

## Quick Start

### Prerequisites

- Python 3.11+

### Installation

```bash
cd tools/08-import-export
pip install -e ../shared
pip install -e .
```

### Running the Dashboard

```bash
python -m import_export.app
# Or: uvicorn import_export.app:app --host 0.0.0.0 --port 8008
```

Then open **http://localhost:8008**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### TradeDoc AI

Classify products with HS codes using full-text search and LLM fallback. Strategic screener for sensitive goods. Generate TDEC, invoices, and certificates of origin. Track TradeLink filing status and deadlines.

### SupplierBot

Handle factory communication via WeChat and WeChat Work. Bilingual message templates (CN/EN), auto-ping during working hours, order status updates, and terminology glossary for consistent translation.

### FXInvoice

Create multi-currency invoices with configurable prefixes and fiscal year. PDF export via ReportLab. FX rate fetcher with HKD peg awareness. Hedging advisor, payment tracker, bank reconciliation, and aging reports.

### StockReconcile

Parse manifests, packing lists, and receipts (OCR supported). 3-pass matching engine for FCL/LCL reconciliation. Discrepancy handler, container tracker, and claim/report generators.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `tradelink_username` | TradeLink credentials for filing |
| `extra` | `fx_rate_source` | Rate provider (e.g. exchangerate-api) |
| `extra` | `monitored_currencies` | USD, CNH, EUR, GBP, JPY |
| `extra` | `mainland_holidays` | Factory closure dates for auto-ping |
| `extra` | `tdec_filing_deadline_days` | Days before TDEC deadline |

## Architecture

```
tools/08-import-export/
├── config.yaml
├── import_export/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── trade_doc_ai/
│   ├── supplier_bot/
│   ├── fx_invoice/
│   └── stock_reconcile/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/import-export/`): `trade_doc_ai.db`, `supplier_bot.db`, `fx_invoice.db`, `stock_reconcile.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/08-import-export
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/import_export_implementation_417e498e.plan.md`
- **Shared Library**: `tools/shared/`
