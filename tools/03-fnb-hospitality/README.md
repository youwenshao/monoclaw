# F&B Hospitality Dashboard

Unified FastAPI application providing four AI-powered tools for Hong Kong F&B and hospitality operators, accessible at `http://mona.local:8003`.

## Tools

| Tool | Purpose |
|------|---------|
| **TableMaster AI** | Multi-channel booking (WhatsApp, Instagram, OpenRice, manual), table inventory, capacity planning, and booking assignment |
| **QueueBot** | Walk-in queue management, QR code generation, wait-time estimation, and table turnover analytics |
| **NoShowShield** | Confirmation sequencer (at booking, T-24hr, T-2hr), reliability scoring, blacklist management, and deposit handling for large parties |
| **SommelierMemory** | Guest profiles, preferences, visit history, VIP segmentation, briefing generation, and celebration alerts |

## Quick Start

```bash
cd tools/03-fnb-hospitality
pip install -e ../shared
pip install -e .
python -m fnb_hospitality.app
```

The dashboard launches at `http://localhost:8003`. On first run, complete the setup wizard at `/setup/`.

## User Guide

### TableMaster AI

Multi-channel booking aggregation with table assignment. Supports WhatsApp, Instagram, OpenRice, and manual entry. Dining sessions (lunch, dinner, dim sum) and durations are configurable. Integrates with NoShowShield for confirmations and QueueBot for walk-in flow.

### QueueBot

QR code generation for join-queue, wait-time estimation based on party size and turnover targets, and periodic notifications. Grace period and return window configurable. Analytics for queue length, average wait, and conversion.

### NoShowShield

Three-stage confirmation (booking, T-24hr, T-2hr). Reliability scoring and blacklist for repeat no-shows. Deposit prompts for parties of 7+. Festive dates (Valentine's, Christmas, etc.) require mandatory confirmation. Auto-release before service.

### SommelierMemory

Guest profiles with visit count and spend. VIP/VVIP thresholds configurable. Briefing generation for returning guests. Celebration lookahead (birthdays, anniversaries) for proactive service. Recommendations based on history.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `restaurant_name`, `cuisine_type` | Business profile |
| `extra` | `dining_sessions` | Lunch, dinner, dim sum times and durations |
| `extra` | `target_turnovers_per_service` | Table turnover targets |
| `extra` | `confirmation_timing_hours` | NoShowShield confirmation schedule |
| `extra` | `vip_thresholds` | SommelierMemory VIP/VVIP criteria |
| `extra` | `festive_dates` | Mandatory confirmation dates (MMDD) |

## Architecture

```
tools/03-fnb-hospitality/
├── config.yaml
├── fnb_hospitality/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── table_master/
│   ├── queue_bot/
│   ├── no_show_shield/
│   ├── sommelier_memory/
│   └── dashboard/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/fnb-hospitality/`): `table_master.db`, `queue_bot.db`, `no_show_shield.db`, `sommelier_memory.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/03-fnb-hospitality
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/f&b_hospitality_implementation_afb7e527.plan.md`
- **Shared Library**: `tools/shared/`
