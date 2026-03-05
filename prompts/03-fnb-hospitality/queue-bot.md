# QueueBot — Digital Queue Management System

## Overview

QueueBot replaces paper queue tickets with a digital system that lets walk-in customers join a restaurant queue via QR code scan, receive real-time wait time estimates, and get WhatsApp/SMS notifications when their table is ready. It uses historical POS data to predict wait times accurately and manages the queue with automatic table-readiness detection.

## Target User

Popular Hong Kong restaurants with consistent walk-in queues (especially dim sum, hotpot, and casual dining) that rely on paper tickets and shouting names — leading to queue-jumps, walkouts from unknown wait times, and customers unable to wait nearby because they'll miss their turn.

## Core Features

- **QR Code Queue Entry**: Customers scan a QR code at the restaurant entrance, enter party size and phone number on a mobile-optimized web form, and receive a queue position confirmation via WhatsApp. No app installation required.
- **Real-Time Wait Estimation**: Calculate estimated wait time based on current queue depth, average table turnover from historical POS data, table availability by party size, and time of day. Update estimates every 5 minutes.
- **Multi-Channel Notifications**: Send "your table is ready" alerts via WhatsApp (primary) and SMS (fallback). Give customers a 5-minute arrival window. If they don't arrive, offer the table to the next party and move them to a grace queue.
- **Walk-Away Freedom**: Customers can leave the vicinity and return when notified. Send position updates ("You are now #3 in queue") at configurable intervals so customers can gauge their return timing.
- **Queue Analytics**: Track average wait times, walkout rates (left before being seated), peak queue lengths, and optimal staffing patterns. Identify which party sizes cause bottlenecks.
- **Staff Dashboard**: Web-based real-time queue view for host staff. One-tap to seat, skip, or remove customers. Manual queue entry for phone reservations and VIPs.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Web frontend | `fastapi` + `jinja2`, responsive HTML/CSS |
| QR code | `qrcode`, `Pillow` |
| WhatsApp | Twilio WhatsApp Business API |
| SMS | Twilio Programmable SMS |
| Wait time model | `pandas`, `numpy` for statistical estimation |
| Scheduling | `APScheduler` |
| Database | `sqlite3` |
| Real-time updates | Server-Sent Events (SSE) via `sse-starlette` |

## File Structure

```
/opt/openclaw/skills/local/queue-bot/
├── main.py                  # FastAPI app entry
├── config.yaml              # Restaurant config, table map, hours
├── queue/
│   ├── manager.py           # Queue state machine
│   ├── estimator.py         # Wait time calculator
│   └── notifier.py          # WhatsApp/SMS notifications
├── web/
│   ├── routes.py            # Customer and staff web routes
│   ├── qr_generator.py      # QR code generation
│   └── templates/
│       ├── join.html         # Customer queue join form
│       ├── status.html       # Customer queue status page
│       └── dashboard.html    # Staff queue dashboard
├── analytics/
│   └── reports.py           # Queue performance metrics
├── pos/
│   └── integration.py       # POS data feed for turnover calc
└── tests/
    ├── test_queue.py
    ├── test_estimator.py
    └── test_notifications.py

~/OpenClawWorkspace/queue-bot/
├── queuebot.db              # SQLite database
├── qr_codes/                # Generated QR images
├── pos_data/                # Historical POS exports
└── exports/                 # Analytics reports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Primary notification channel. Send queue confirmations, position updates, and table-ready alerts.
- **Twilio Programmable SMS**: Fallback for customers without WhatsApp or when WhatsApp delivery fails.
- **POS System**: Import historical transaction data (seating time, table, covers) for wait time estimation. Support CSV import from common HK POS systems (e-Pos, FoodZaps, Eats365).
- **TableMaster AI (sibling tool)**: Share table status for coordinated queue-to-reservation flow. When a queue customer is seated, update the shared table inventory.

## HK-Specific Requirements

- **Peak Hour Patterns**: HK restaurants experience two sharp peaks:
  - Lunch: 12:00-2:00pm (office workers with strict 1-hour lunch)
  - Dinner: 7:00-9:00pm (family dining)
  - Weekend dim sum: 10:00-1:00pm (extended family, large parties)
  Queue wait times spike dramatically during these windows. Model must account for the bimodal distribution.
- **Hong Kong Phone Format**: +852 followed by 8 digits. Mobile numbers begin with 5, 6, 7, or 9. Validate on entry. Display as XXXX XXXX for readability.
- **Bilingual Interface**: Customer-facing web form and messages in Traditional Chinese (default) and English. Auto-detect from browser locale. All WhatsApp messages bilingual or language-matched.
- **Space Constraints**: HK restaurants are compact. Physical QR code display must be practical — a single A4 printed sign at the entrance with clear instructions in both languages.
- **Walk-Away Radius**: Unlike suburban restaurants, HK customers typically walk to nearby shops or MTR station while waiting. Design notifications to give 5-10 minutes of return time (standard for dense urban areas).
- **Cultural Queue Etiquette**: HK diners expect strict FIFO ordering. Any perceived queue-jumping causes complaints. The system must be transparently fair. Display queue position on the customer's status page.
- **Typhoon Protocol**: During T8+ signal, auto-clear the queue and notify all waiting customers.

## Data Model

```sql
CREATE TABLE queue_entries (
    id INTEGER PRIMARY KEY,
    queue_number INTEGER NOT NULL,
    guest_name TEXT,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    seating_preference TEXT,
    status TEXT DEFAULT 'waiting',
    estimated_wait_minutes INTEGER,
    actual_wait_minutes INTEGER,
    position_at_join INTEGER,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    seated_at TIMESTAMP,
    left_at TIMESTAMP,
    channel TEXT DEFAULT 'qr'
);

CREATE TABLE table_turnover (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    time_slot TEXT NOT NULL,
    table_id TEXT,
    party_size INTEGER,
    seated_at TIMESTAMP,
    cleared_at TIMESTAMP,
    duration_minutes INTEGER,
    source TEXT DEFAULT 'pos'
);

CREATE TABLE queue_analytics (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    hour INTEGER NOT NULL,
    total_joined INTEGER,
    total_seated INTEGER,
    total_walkouts INTEGER,
    avg_wait_minutes REAL,
    max_wait_minutes REAL,
    max_queue_length INTEGER
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    queue_entry_id INTEGER REFERENCES queue_entries(id),
    type TEXT NOT NULL,
    channel TEXT,
    sent_at TIMESTAMP,
    delivered BOOLEAN,
    message_text TEXT
);
```

## Testing Criteria

- [ ] QR code scan opens a mobile-optimized join form that works on iOS Safari and Android Chrome
- [ ] Queue join form validates HK phone format and rejects invalid numbers
- [ ] Wait time estimate is within ±5 minutes of actual wait for 70% of test cases during peak hours
- [ ] Table-ready WhatsApp notification delivers within 30 seconds of staff marking "ready"
- [ ] SMS fallback fires if WhatsApp delivery fails after 60 seconds
- [ ] Customer status page updates position in real-time via SSE
- [ ] Staff dashboard supports seat/skip/remove with one tap and reflects changes instantly
- [ ] System handles 80 concurrent queue entries (busy Saturday dinner) without performance degradation

## Implementation Notes

- **No LLM required**: Queue management is entirely algorithmic. Total memory footprint <200MB. Can run on the same machine as other tools without contention.
- **Wait time algorithm**: Use exponential moving average of table turnover times, segmented by party size bracket (1-2, 3-4, 5-6, 7+) and time slot (lunch/dinner/weekend). Weight recent data more heavily. Fall back to static estimates for the first week until enough data accumulates.
- **QR code strategy**: Generate a single static QR code pointing to `http://localhost:PORT/join`. Print on a weatherproof A4 sign. The URL should also work via local network for the restaurant's WiFi-connected devices.
- **Server-Sent Events**: Use SSE for the customer status page and staff dashboard. More reliable than WebSocket for this use case (unidirectional updates, auto-reconnect). Use `sse-starlette` middleware with FastAPI.
- **Notification reliability**: Twilio callback webhooks confirm delivery. If undelivered after 60 seconds, escalate to SMS. If both fail, play an audio alert on the staff dashboard.
- **POS data import**: Provide a CSV import tool for historical POS data. Map columns: table, covers, open_time, close_time. Run import nightly for the previous day's data. This feeds the wait time estimator.
- **Privacy**: Phone numbers collected for queue notifications only. Auto-delete queue entries older than 24 hours. Don't build guest profiles from queue data (that's SommelierMemory's job).
