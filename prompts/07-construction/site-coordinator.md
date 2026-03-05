# SiteCoordinator

## Overview

SiteCoordinator is a multi-agent scheduling and logistics tool for construction companies managing subcontractors across multiple Hong Kong sites. It optimizes daily contractor assignments, plans efficient routes between sites accounting for HK geography and traffic, and coordinates 15+ trade schedules to minimize conflicts and maximize site productivity. Think of it as a dispatch center for construction workforce management.

## Target User

Hong Kong construction project coordinators, site agents, and operations managers at main contractors who oversee multiple active sites with numerous subcontractor teams that need to be scheduled, dispatched, and tracked daily.

## Core Features

- **Multi-Site Scheduling**: Manages daily/weekly schedules for subcontractor teams across multiple concurrent HK construction sites, ensuring trade sequencing dependencies are respected
- **Trade Dependency Management**: Enforces construction trade sequencing rules (e.g., electrical rough-in before plastering, plumbing before tiling) to prevent scheduling conflicts
- **Route Optimization**: Calculates optimal travel routes for contractors visiting multiple sites in a day, factoring in HK traffic patterns, tunnel tolls, and public transport options
- **Resource Conflict Detection**: Identifies when the same contractor team is double-booked or when site capacity (e.g., maximum workers allowed on-site) would be exceeded
- **WhatsApp Dispatch**: Sends daily work assignments to subcontractors via WhatsApp with site address, scope of work, required tools/materials, and site contact information
- **Progress Tracking**: Subcontractors report task completion via WhatsApp; dashboard shows real-time progress across all sites

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Scheduling | Google OR-Tools, custom dependency graph |
| Routing | OSRM / Google Maps API, geopy |
| Messaging | Twilio WhatsApp Business API |
| Database | SQLite |
| UI | Streamlit (calendar view, map visualization) |
| Maps | folium |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/site-coordinator/
├── app.py                      # Streamlit coordination dashboard
├── scheduling/
│   ├── optimizer.py            # OR-Tools schedule optimization engine
│   ├── trade_dependencies.py   # Construction trade sequencing rules
│   ├── conflict_detector.py    # Resource and schedule conflict detection
│   └── calendar_manager.py     # Weekly/daily schedule management
├── routing/
│   ├── route_optimizer.py      # Multi-site route calculation
│   ├── hk_geography.py         # HK district distances, tunnel routes, ferry routes
│   └── travel_time.py          # Time-of-day travel time estimation
├── dispatch/
│   ├── whatsapp_dispatcher.py  # Daily assignment delivery via WhatsApp
│   ├── progress_collector.py   # Completion reporting via WhatsApp
│   └── assignment_generator.py # Generate daily work assignments per contractor
├── data/
│   ├── coordinator.db          # SQLite database
│   ├── hk_districts.json       # HK 18 districts with coordinates
│   └── trade_rules.json        # Trade dependency and sequencing rules
├── requirements.txt
└── README.md
```

## Workspace Data Directory

```
~/OpenClawWorkspace/site-coordinator/
├── coordinator.db             # SQLite database (runtime data)
├── routes/                    # Cached route calculations and polylines
├── schedules/                 # Exported daily/weekly schedule snapshots
└── maps/                      # Generated map visualizations
```

## Key Integrations

- **Google Maps API / OSRM**: Route calculation between HK construction sites with real-time traffic consideration
- **Twilio WhatsApp**: Dispatch work assignments and collect completion reports from subcontractors in the field
- **Google OR-Tools**: Constraint satisfaction solver for optimizing multi-site, multi-trade scheduling
- **Telegram Bot API**: Secondary channel for permit alerts, safety reminders, and subcontractor dispatch.

## GUI Specification

Part of the **Construction Dashboard** (`http://mona.local:8503`) — SiteCoordinator tab.

### Views

- **Subcontractor Schedule**: Weekly grid view with subcontractors as rows and days as columns. Color-coded by activity type (demolition, structural, MEP, finishing).
- **WhatsApp Dispatch Log**: History of all dispatched instructions with delivery/read status per subcontractor.
- **Delivery Schedule**: Expected deliveries with ETA tracking, supplier contact, and site gate assignment.
- **Site Access Log**: Digital sign-in/sign-out log for all site personnel with time tracking and company affiliation.
- **Resource Dashboard**: Overview of active subcontractor teams, equipment on-site, and material delivery status.

### Mona Integration

- Mona sends daily schedule summaries and dispatch instructions to subcontractors via WhatsApp every morning.
- Mona tracks delivery ETAs and alerts the coordinator when delays are detected.
- Human adjusts schedules, resolves conflicts, and handles ad-hoc coordination.

### Manual Mode

- Coordinator can manually create schedules, dispatch instructions, log deliveries, and manage site access without Mona.

## HK-Specific Requirements

- HK district geography: 18 districts across Hong Kong Island, Kowloon, and New Territories; sites in different regions may require cross-harbour tunnel travel (significant time/cost factor)
- Traffic patterns: Peak hours 7:30-9:30 and 17:30-19:30; Cross Harbour Tunnel consistently congested; Western Harbour Crossing as alternative; Tuen Mun Highway bottleneck for NT sites
- Public holidays: 17 statutory general holidays; construction sites may operate on some holidays with penalty rates — scheduling must be aware of this
- Typhoon contingency: When T8 or above signal is hoisted, all outdoor construction work stops — tool should have a typhoon mode that reschedules affected assignments
- Typical HK construction trades (15+): demolition, formwork, rebar, concreting, plumbing, electrical, HVAC, fire services, plastering, tiling, painting, carpentry, glazing, waterproofing, landscaping
- Site capacity: HK construction sites are often space-constrained — maximum worker count per site per day must be enforced
- Working hours: Standard HK construction site hours 8:00-18:00; some sites have noise permit restrictions (7:00-19:00 weekdays only for powered mechanical equipment under NCO)
- Noise Control Ordinance (Cap 400): Construction noise permits restrict operating hours in residential areas — scheduling must respect these constraints

## Data Model

```sql
CREATE TABLE sites (
    id INTEGER PRIMARY KEY,
    site_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    latitude REAL,
    longitude REAL,
    max_daily_workers INTEGER DEFAULT 50,
    noise_permit_hours TEXT,  -- JSON: {"start":"07:00","end":"19:00"}
    site_agent TEXT,
    site_agent_phone TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE contractors (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    trade TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    whatsapp_number TEXT,
    team_size INTEGER DEFAULT 1,
    base_district TEXT,
    hourly_rate REAL,
    availability TEXT,  -- JSON: days of week available
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE schedule_assignments (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    contractor_id INTEGER REFERENCES contractors(id),
    assignment_date DATE,
    start_time TIME DEFAULT '08:00',
    end_time TIME DEFAULT '18:00',
    scope_of_work TEXT,
    trade TEXT,
    priority INTEGER DEFAULT 5,
    depends_on INTEGER REFERENCES schedule_assignments(id),
    status TEXT CHECK(status IN ('scheduled','dispatched','in_progress','completed','cancelled','rescheduled')) DEFAULT 'scheduled',
    dispatched_at TIMESTAMP,
    completed_at TIMESTAMP,
    completion_notes TEXT
);

CREATE TABLE daily_routes (
    id INTEGER PRIMARY KEY,
    contractor_id INTEGER REFERENCES contractors(id),
    route_date DATE,
    sites_sequence TEXT,  -- JSON array of site_ids in visit order
    estimated_travel_minutes INTEGER,
    route_polyline TEXT,
    total_distance_km REAL
);

CREATE TABLE trade_dependencies (
    id INTEGER PRIMARY KEY,
    predecessor_trade TEXT NOT NULL,
    successor_trade TEXT NOT NULL,
    min_gap_days INTEGER DEFAULT 0,
    notes TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Company Profile**: Company name, contractor registration details, office address
2. **Sites**: Add active construction sites with address, district, coordinates, and maximum worker capacity
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token, SMTP email for formal notifications
4. **Subcontractor Directory**: Import subcontractor contact list with trade classifications
5. **Trade Dependencies**: Review and customize trade sequencing rules
6. **Maps API**: Google Maps API key or OSRM endpoint for route calculation
7. **Sample Data**: Option to seed demo schedules and assignments for testing
8. **Connection Test**: Validates all API connections, Maps API access, and message delivery

## Testing Criteria

- [ ] Scheduler assigns 5 contractor teams across 3 sites without any double-booking conflicts
- [ ] Trade dependency engine prevents scheduling tiling before plumbing rough-in on the same site
- [ ] Route optimizer produces a sensible multi-site visit sequence that minimizes total travel time
- [ ] WhatsApp dispatch sends correct daily assignment with site address and scope to each contractor
- [ ] Progress reporting via WhatsApp updates the dashboard in near-real-time
- [ ] Typhoon mode reschedules all outdoor work when activated and notifies all affected contractors
- [ ] Site capacity constraint prevents over-scheduling beyond maximum worker count

## Implementation Notes

- OR-Tools CP-SAT solver handles the constraint satisfaction problem; model each assignment as an interval variable with site, trade, and contractor constraints
- HK geography: pre-compute a distance/time matrix between the 18 districts for fast routing lookups; update with real-time traffic only when generating today's routes
- WhatsApp dispatch timing: send assignments at 18:00 the evening before (HK construction workers plan the next day the night before); send a morning reminder at 7:00
- Typhoon handling: integrate with Hong Kong Observatory RSS feed for typhoon signal checks; auto-trigger rescheduling when T8+ signal is raised
- Trade dependency rules: store as a directed acyclic graph in JSON; validate at schedule creation time that no cycles exist
- Memory budget: ~2GB (OR-Tools is CPU-intensive but memory-light; no LLM needed for this tool)
- For the map visualization, use folium with HK-centric default zoom level (~11) centered on Victoria Harbour
- Consider adding a daily summary report that shows schedule utilization rate (hours assigned / hours available) per contractor
- **Logging**: All operations logged to `/var/log/openclaw/site-coordinator.log` with daily rotation (7-day retention). BD credentials and personal details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. BD portal credentials stored with restricted file permissions (600). Site safety records maintained for statutory retention period (minimum 7 years for construction records).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, Playwright browser state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Safety records and permit history maintained in export for compliance.
