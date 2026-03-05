# NoShowShield — Restaurant No-Show Prevention System

## Overview

NoShowShield combats the HK restaurant industry's 15-20% no-show rate through automated WhatsApp confirmations, intelligent waitlist management, cancellation auto-fill, and a guest reliability scoring system. It sends timely reminders, detects likely no-shows early, and automatically fills freed tables from the waitlist — recovering revenue that would otherwise be lost.

## Target User

Hong Kong restaurant owners and managers losing 10-20% of dinner revenue to no-shows, particularly fine dining and popular venues where every empty table during peak hours represents significant lost income and wasted food prep.

## Core Features

- **Automated Confirmation Sequence**: Send WhatsApp confirmations at booking time, 24 hours before, and 2 hours before the reservation. Require a reply to confirm. Escalate non-respondents: first to SMS, then flag for manual follow-up. Auto-release unconfirmed tables 1 hour before the slot.
- **Waitlist Management**: Maintain a priority-ranked waitlist per time slot. When a cancellation occurs or a no-show is detected, automatically offer the table to the next waitlisted guest via WhatsApp. First to confirm gets the table.
- **No-Show Prediction**: Score each booking's no-show risk based on: past behavior, booking lead time, party size, channel (walk-up bookings are more reliable), and confirmation response time. Flag high-risk bookings for overbooking consideration.
- **Guest Reliability Scoring**: Track each guest's history: completed reservations, no-shows, late cancellations, average party accuracy. Generate a reliability score (A/B/C/D). Share anonymized scores across restaurants in the same group.
- **Cancellation Auto-Fill**: When a cancellation is received, immediately check the waitlist. If a match exists (same party size ±1, same time window ±30min), send an offer. Track fill rate as a key metric.
- **Blacklist Management**: After 3 no-shows, auto-add guest to a soft blacklist. Blacklisted guests receive a deposit requirement message on their next booking attempt. Configurable thresholds and cooldown periods.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| WhatsApp | Twilio WhatsApp Business API |
| SMS fallback | Twilio Programmable SMS |
| Scheduling | `APScheduler` with persistent job store |
| Prediction model | `scikit-learn` (lightweight classifier) |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` |
| Analytics | `pandas` |

## File Structure

```
/opt/openclaw/skills/local/no-show-shield/
├── main.py                  # FastAPI app + scheduler
├── config.yaml              # Confirmation timings, thresholds, templates
├── confirmation/
│   ├── sequencer.py         # Multi-step confirmation flow
│   ├── messenger.py         # WhatsApp/SMS sender
│   └── templates/
│       ├── confirm_en.yaml
│       ├── confirm_zh.yaml
│       └── deposit_request.yaml
├── waitlist/
│   ├── manager.py           # Waitlist queue logic
│   └── auto_fill.py         # Cancellation → waitlist matcher
├── scoring/
│   ├── reliability.py       # Guest reliability scoring
│   ├── predictor.py         # No-show risk model
│   └── blacklist.py         # Blacklist management
├── analytics/
│   └── reports.py           # No-show rate, fill rate metrics
└── tests/
    ├── test_confirmation.py
    ├── test_waitlist.py
    └── test_scoring.py

~/OpenClawWorkspace/no-show-shield/
├── noshow.db                # SQLite database
├── models/                  # Trained prediction model
└── exports/                 # Analytics reports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Send confirmation messages, receive replies, handle deposit links. Must use approved message templates for proactive (>24hr) messages.
- **Twilio Programmable SMS**: Fallback when WhatsApp message is undelivered or unread after 2 hours.
- **TableMaster AI (sibling tool)**: Receive new bookings, push cancellations and no-show flags. Shared guest database for unified history.
- **Payment gateway (optional)**: For deposit collection from blacklisted guests. Stripe HK or PayMe deep link.

## HK-Specific Requirements

- **No-Show Rates**: HK restaurant no-show rates average 15-20%, higher for large party bookings (8+) and Friday/Saturday dinners. Weekend brunch no-show rates are lower (~10%). Calibrate prediction model accordingly.
- **Confirmation Message Tone**: HK dining culture values politeness but directness. Confirmation messages should be warm but clear. Chinese messages use 「」for emphasis, end with restaurant name and phone number. Avoid aggressive language about penalties.
- **Cantonese Message Templates**: Primary confirmation in Traditional Chinese (Cantonese register, not Mandarin). Example: "您好！提提你，你喺[餐廳名]嘅訂位 — [日期] [時間] [人數]位。請回覆「確認」或「取消」。多謝！🙏"
- **Deposit Culture**: Deposits are increasingly accepted for fine dining and peak times in HK but remain uncommon for casual dining. Default: no deposit for parties ≤6, optional deposit for 7+. Blacklisted guests always require deposit.
- **Phone Number Handling**: Store as +852XXXXXXXX. Match guest records by phone number (primary key for identity). Handle number recycling (HK recycles numbers) with a confidence decay after 24 months of inactivity.
- **Festive Periods**: Chinese New Year (reunion dinner), Christmas Eve, Valentine's Day, and Mother's Day have near-100% booking rates and highest no-show impact. Enforce mandatory confirmation for these dates.

## Data Model

```sql
CREATE TABLE guests (
    id INTEGER PRIMARY KEY,
    phone TEXT UNIQUE NOT NULL,
    name TEXT,
    total_bookings INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    no_shows INTEGER DEFAULT 0,
    late_cancellations INTEGER DEFAULT 0,
    reliability_score TEXT DEFAULT 'B',
    is_blacklisted BOOLEAN DEFAULT FALSE,
    blacklisted_at TIMESTAMP,
    last_visit DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE confirmations (
    id INTEGER PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    guest_phone TEXT NOT NULL,
    step INTEGER NOT NULL,
    channel TEXT DEFAULT 'whatsapp',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    response TEXT,
    responded_at TIMESTAMP,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE waitlist (
    id INTEGER PRIMARY KEY,
    guest_name TEXT,
    guest_phone TEXT NOT NULL,
    party_size INTEGER NOT NULL,
    preferred_date DATE NOT NULL,
    preferred_time TIME NOT NULL,
    flexibility_minutes INTEGER DEFAULT 30,
    offered_booking_id INTEGER,
    status TEXT DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE no_show_predictions (
    id INTEGER PRIMARY KEY,
    booking_id INTEGER NOT NULL,
    risk_score REAL,
    risk_factors TEXT,
    prediction TEXT,
    actual_outcome TEXT,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Confirmation sequence sends at booking, T-24hr, and T-2hr with correct message content
- [ ] Guest reply "確認" (confirm) marks the booking as confirmed and stops further reminders
- [ ] Unconfirmed booking auto-releases at T-1hr and triggers waitlist offer
- [ ] Waitlist auto-fill offers a freed table to the next matching guest within 2 minutes
- [ ] Reliability scoring correctly downgrades a guest to "C" after 2 no-shows in 3 months
- [ ] Blacklist triggers a deposit request message on the guest's next booking
- [ ] No-show prediction model achieves >70% precision on a test dataset of 200 bookings
- [ ] System handles festive period load (100+ bookings) without message delivery delays

## Implementation Notes

- **No LLM required**: This tool is entirely rule-based and uses a lightweight scikit-learn model for prediction. Total memory footprint <300MB. Can run alongside other tools comfortably.
- **Confirmation job scheduling**: Use `APScheduler` with SQLite-backed job store. Schedule all three confirmation steps at booking creation time. If booking is cancelled, remove pending jobs.
- **Prediction model**: Train a simple gradient boosting classifier on features: guest reliability score, party size, day of week, booking lead time, confirmation response time, channel. Retrain monthly on accumulated data. Start with rule-based heuristics until enough data accumulates (>200 bookings).
- **WhatsApp template messages**: Twilio requires pre-approved templates for messages sent >24 hours after last customer message. Register confirmation and reminder templates with Twilio. Use freeform messages only within the 24-hour window.
- **Deposit handling**: If integrating payment, generate a Stripe Checkout link or PayMe QR code. Track payment status. Release deposit 24 hours after completed dining. Non-refundable for no-shows.
- **Privacy**: Guest phone numbers and dining history are personal data under PDPO. Provide opt-out mechanism. Delete guest data after 24 months of inactivity. Never share individual guest data outside the restaurant group.
