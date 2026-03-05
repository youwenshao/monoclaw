# TableMaster AI — Unified Restaurant Booking System

## Overview

TableMaster AI aggregates restaurant reservations from WhatsApp, Instagram DMs, OpenRice, phone calls (via transcription), and walk-ins into a single real-time table inventory. It detects booking conflicts, auto-confirms reservations, manages table assignments, and provides the restaurant manager with a unified dashboard — eliminating the double-booking chaos of managing 4-5 separate booking channels.

## Target User

Hong Kong restaurant owners and managers operating 30-80 seat venues who receive bookings across multiple channels (WhatsApp being dominant) and currently track reservations on paper, a shared spreadsheet, or fragmented apps — leading to frequent double-bookings and lost revenue.

## Core Features

- **Multi-Channel Booking Aggregation**: Ingest reservations from WhatsApp messages, Instagram DMs, OpenRice booking API, and manual phone/walk-in entries. Parse natural language requests ("Table for 4 this Saturday 7:30pm") using local LLM. Normalize into a unified booking format.
- **Real-Time Table Inventory**: Maintain a live map of all tables with their status (available, reserved, occupied, clearing). Account for table combinations (e.g., two 2-tops can combine for a party of 4). Calculate availability considering expected dining duration by meal type.
- **Conflict Detection & Resolution**: When a new booking conflicts with existing ones, suggest the nearest available time slot (±30 min) or an alternative table configuration. Auto-detect if a party size exceeds restaurant capacity.
- **Auto-Confirmation Flow**: Send bilingual confirmation messages via WhatsApp within 60 seconds of booking. Include date, time, party size, and any special notes. Request confirmation reply within 2 hours or release the table.
- **Smart Table Assignment**: Assign tables based on party size, guest preferences (window, quiet corner, booth), occasion flags (birthday, business dinner), and server section balancing.
- **Booking Analytics Dashboard**: Track booking volume by channel, time slot popularity, average party size, no-show rates, and revenue per table. Expose via local web dashboard.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| WhatsApp | Twilio WhatsApp Business API |
| Instagram | Instagram Graph API (webhook for DMs) |
| Web dashboard | `fastapi` + `jinja2` templates, `htmx` |
| Scheduling | `APScheduler` |
| Database | `sqlite3` |
| QR code | `qrcode` |

## File Structure

```
/opt/openclaw/skills/local/table-master/
├── main.py                  # FastAPI app entry
├── config.yaml              # Table map, business hours, API keys
├── channels/
│   ├── whatsapp.py          # Twilio webhook handler
│   ├── instagram.py         # IG Graph API handler
│   ├── openrice.py          # OpenRice integration
│   └── manual.py            # Phone/walk-in entry API
├── booking/
│   ├── parser.py            # LLM-based booking request parser
│   ├── engine.py            # Conflict detection + resolution
│   ├── confirmer.py         # Auto-confirmation flow
│   └── assigner.py          # Smart table assignment
├── inventory/
│   ├── tables.py            # Table status management
│   └── capacity.py          # Capacity calculator
├── dashboard/
│   ├── routes.py            # Dashboard web routes
│   ├── analytics.py         # Booking analytics
│   └── templates/           # HTML templates
└── tests/
    ├── test_booking.py
    ├── test_conflict.py
    └── test_channels.py

~/OpenClawWorkspace/table-master/
├── tablemaster.db           # SQLite database
├── exports/                 # Analytics reports
└── backups/                 # Daily DB snapshots
```

## Key Integrations

- **Twilio WhatsApp Business API**: Primary booking channel. Receive booking requests via webhook, send confirmations and reminders. Support media messages (menu photos, table layout).
- **Instagram Graph API**: Receive booking requests from Instagram DMs. Requires Instagram Business account linked to a Facebook Page.
- **OpenRice**: HK's dominant restaurant platform. Integrate via available API or scrape the restaurant's OpenRice booking page for new reservations. Sync confirmed bookings back.
- **NoShowShield (sibling tool)**: Share booking data for no-show prediction and prevention. Feed confirmed bookings into the confirmation pipeline.

## HK-Specific Requirements

- **OpenRice Dominance**: OpenRice is HK's primary restaurant discovery and booking platform. Integration is essential. Handle OpenRice's booking format (party size, date, time, phone number, special requests in Chinese).
- **Dining Hours**: HK lunch rush is 12:00-2:00pm (1.5hr turnover), dinner peak is 7:00-9:30pm (2hr turnover). Weekend dim sum runs 10:00am-2:30pm (2hr turnover). Configure expected dining duration by meal period.
- **Table Turnover Expectations**: HK restaurants typically expect 2-3 turnovers per dinner service for popular venues. Table assignment should optimize for this.
- **Party Size Norms**: Average HK dining party is 4 people. Business dinners often 6-10 at round tables. Family gatherings can reach 12+ requiring private rooms. Support table combination logic for larger groups.
- **Bilingual Communication**: Booking confirmations in Traditional Chinese and English. Detect language from customer's original message. Default to Chinese for local +852 numbers.
- **Phone Format**: HK mobile numbers are 8 digits starting with 5/6/7/9. Always store with +852 prefix.
- **Public Holidays**: HK public holidays are peak dining days. Flag these in the booking engine for adjusted capacity and turnover expectations.

## Data Model

```sql
CREATE TABLE tables (
    id INTEGER PRIMARY KEY,
    table_number TEXT UNIQUE NOT NULL,
    seats INTEGER NOT NULL,
    section TEXT,
    is_combinable BOOLEAN DEFAULT FALSE,
    combine_with TEXT,
    location_type TEXT,
    status TEXT DEFAULT 'available',
    current_booking_id INTEGER
);

CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    guest_name TEXT NOT NULL,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    booking_date DATE NOT NULL,
    booking_time TIME NOT NULL,
    end_time TIME,
    table_id INTEGER REFERENCES tables(id),
    channel TEXT NOT NULL,
    channel_ref TEXT,
    status TEXT DEFAULT 'pending',
    special_requests TEXT,
    language_pref TEXT DEFAULT 'zh',
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE booking_analytics (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    total_bookings INTEGER,
    total_covers INTEGER,
    no_shows INTEGER,
    cancellations INTEGER,
    avg_party_size REAL,
    peak_channel TEXT,
    revenue_estimate REAL
);
```

## Testing Criteria

- [ ] WhatsApp booking request "4位，星期六7點半" correctly parses to party_size=4, Saturday, 19:30
- [ ] Conflict detection blocks a double-booking on the same table and suggests an alternative
- [ ] Auto-confirmation message sends within 60 seconds in the correct language
- [ ] Table combination logic correctly identifies that two 2-tops can serve a party of 4
- [ ] OpenRice booking sync imports a test reservation without duplicating existing ones
- [ ] Dashboard shows accurate real-time table status (available/reserved/occupied)
- [ ] Analytics correctly calculate no-show rate and average party size over a 7-day period
- [ ] System handles 50 concurrent bookings for a busy Saturday dinner without errors

## Implementation Notes

- **LLM for parsing only**: Use the local LLM to extract structured booking data (date, time, party size, name) from free-text messages. All booking logic (conflict detection, table assignment) is deterministic. Lazy-load LLM; unload after 5 min idle.
- **Real-time table status**: Use WebSocket (via FastAPI) for the dashboard to reflect table status changes instantly. Alternatively, use htmx polling at 10-second intervals for simplicity.
- **OpenRice integration**: OpenRice may not have a public API. If scraping is needed, use a persistent browser session via Playwright. Check for booking notifications every 2 minutes during service hours.
- **Dining duration estimation**: Default durations — Lunch: 75 min, Dinner weekday: 90 min, Dinner weekend: 120 min, Dim sum: 120 min. Allow per-booking override.
- **Memory**: LLM (~5GB) loads on demand. Steady-state with dashboard serving: <500MB. Suitable for background operation on M4 16GB.
- **Backup**: Auto-snapshot the SQLite database every night at 3am. Keep 7 days of snapshots.
