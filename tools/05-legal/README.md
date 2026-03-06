# Legal Dashboard

Unified FastAPI application providing four productivity tools for Hong Kong law firms, accessible at `http://mona.local:8005`.

## Tools

| Tool | Purpose |
|------|---------|
| **LegalDoc Analyzer** | Clause extraction, anomaly detection, employment contract (Cap 57) checker, NDA checker, and comparison view |
| **DeadlineGuardian** | Limitation periods (Cap 347), court deadlines (CFI, DCT, Lands Tribunal, Labour Tribunal), business-day calculation, reminder engine, and .ics export |
| **DiscoveryAssistant** | Email ingestion (.eml/.mbox), privilege detection, relevance scoring, keyword search (Whoosh), deduplication, and privilege log export |
| **IntakeBot** | Conflict checking (FTS5 + fuzzy), client intake via WhatsApp/Telegram, conversation flow state machine, engagement letter generation |

## Quick Start

```bash
cd tools/05-legal
pip install -e ../shared
pip install -e .
python -m legal.app
```

The dashboard launches at `http://localhost:8005`. On first run, complete the setup wizard at `/setup/`.

## User Guide

### LegalDoc Analyzer

Upload contracts for clause extraction. Anomaly scoring for unusual terms. Employment contract checker for Cap 57 compliance. NDA-specific checks. Side-by-side comparison of documents. Confidence thresholds configurable.

### DeadlineGuardian

Matter-based deadline tracking. Limitation calculator (Cap 347). Court-specific timelines (CFI, DCT, Lands Tribunal, Labour Tribunal). HK public holidays for business-day calculation. Reminder intervals (30, 14, 7, 3, 1 days). Calendar export (.ics).

### DiscoveryAssistant

Import emails (eml, mbox). Privilege detection with configurable threshold. Relevance scoring. Keyword search with Whoosh. Deduplication. Privilege log export to Excel. Document preview and timeline.

### IntakeBot

Conflict check against existing clients (FTS5 + rapidfuzz + pypinyin). HKID last-4-only option. Intake conversation flow (state machine). Engagement letter generation. WhatsApp and Telegram bot handlers.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `clause_confidence_threshold` | LegalDoc Analyzer |
| `extra` | `reminder_intervals_days`, `active_court_tracks` | DeadlineGuardian |
| `extra` | `privilege_confidence_threshold` | DiscoveryAssistant |
| `extra` | `conflict_match_threshold`, `hkid_last4_only` | IntakeBot |

## Architecture

```
tools/05-legal/
├── config.yaml
├── legal/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── doc_analyzer/
│   ├── deadline_guardian/
│   ├── discovery_assistant/
│   ├── intake_bot/
│   └── dashboard/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/legal/`): `doc_analyzer.db`, `deadline_guardian.db`, `discovery_assistant.db`, `intake_bot.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/05-legal
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/legal_tools_implementation_933d57a3.plan.md`
- **Shared Library**: `tools/shared/`
