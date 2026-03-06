# Construction Dashboard

Unified FastAPI application providing four construction productivity tools for Hong Kong contractors and site managers, accessible at `http://mona.local:8503`.

## Tools

| Tool | Purpose |
|------|---------|
| **PermitTracker** | BD Portal and Minor Works permit monitoring, status alerts, timeline tracking, and document archive |
| **SafetyForm Bot** | Daily safety checklists, SSSS reports, toolbox talks, incident reporting, and compliance calendar |
| **DefectsManager** | Defect logging, DMC resolution, work order generation, contractor matching, and lifecycle tracking |
| **SiteCoordinator** | Trade scheduling, route optimization, dispatch assignments, and HK geography-aware travel time estimates |

## Quick Start

### Prerequisites

- Python 3.11+
- Playwright (for BD Portal scraping): `playwright install chromium`

### Installation

```bash
cd tools/07-construction
pip install -e ../shared
pip install -e .
```

### Running the Dashboard

```bash
python -m construction.app
# Or: uvicorn construction.app:app --host 0.0.0.0 --port 8503
```

Then open **http://localhost:8503**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### PermitTracker

Monitor BD Portal and Minor Works submissions. Gantt-style timelines, submission cards, alert history, and document archive. Scrapes permit status on a configurable interval; supports GBP, foundation, superstructure, drainage, OP, and minor works I/II/III.

### SafetyForm Bot

WhatsApp-driven daily safety inspections. Checklist engine, photo capture, deficiency tracking, SSSS reports, monthly summaries, toolbox talks, and PDF export. Heat stress threshold alerts and 4S compliance tracking.

### DefectsManager

Log defects from site photos or WhatsApp. Categorizer, priority scoring, DMC matrix, work order generation, contractor matching, and lifecycle states. Tracks response time, quality, and cost for contractor scoring.

### SiteCoordinator

Schedule trades with dependency resolution and conflict detection. Route optimizer for HK geography, travel time estimates, dispatch via WhatsApp, progress tracking, and resource dashboard. Typhoon mode for weather-based adjustments.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra.permit_tracker` | `scrape_interval_hours` | BD Portal scrape frequency |
| `extra.permit_tracker` | `expected_timelines` | Days for GBP, foundation, superstructure, etc. |
| `extra.safety_form` | `checklist_schedule` | Daily checklist time (e.g. 08:00) |
| `extra.safety_form` | `heat_stress_threshold` | Celsius threshold for heat alerts |
| `extra.defects_manager` | `contractor_scoring_weights` | Weights for response_time, quality, cost, communication |
| `extra.site_coordinator` | `working_hours` | Start/end times for scheduling |

## Architecture

```
tools/07-construction/
├── config.yaml
├── construction/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── permit_tracker/
│   ├── safety_form/
│   ├── defects_manager/
│   └── site_coordinator/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/construction/`): `permit_tracker.db`, `safety_form.db`, `defects_manager.db`, `site_coordinator.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/07-construction
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/construction_tools_implementation_c772fae6.plan.md`
- **Shared Library**: `tools/shared/`
