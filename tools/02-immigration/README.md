# Immigration Dashboard

Unified FastAPI application providing four immigration productivity tools for Hong Kong immigration consultants, accessible at `http://mona.local:8002`.

## Tools

- **VisaDoc OCR** — Document parsing for HKID, passports, bank statements, tax returns, and employment contracts with bilingual OCR
- **FormAutoFill** — Automatic population of ImmD forms (ID990A/B, GEP, ASMTP, QMAS, IANG) with PDF overlay generation
- **ClientPortal Bot** — Client-facing WhatsApp/Telegram bot for status queries, document reminders, and appointment scheduling
- **PolicyWatcher** — Government Gazette and ImmD website monitor with AI-powered policy change summaries and alerts

## Quick Start

```bash
cd tools/02-immigration
pip install -e ../shared
pip install -e .
python -m immigration.app
```

The dashboard launches at `http://localhost:8002`. On first run, complete the setup wizard.

## Running Tests

```bash
cd tools/02-immigration
python -m pytest tests/ -v
```
