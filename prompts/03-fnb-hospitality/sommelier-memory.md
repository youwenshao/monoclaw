# SommelierMemory — Customer Preference CRM for Restaurants

## Overview

SommelierMemory is a lightweight restaurant CRM that captures and recalls guest preferences, dietary requirements, allergies, celebration dates, favorite tables, and spending history. It enables front-of-house staff to deliver personalized service — greeting regulars by name, remembering their usual wine, and proactively noting upcoming birthdays — transforming a good restaurant into one that feels like home.

## Target User

Hong Kong fine dining restaurants, high-end casual venues, and members' clubs where repeat customers expect personalized service. Front-of-house managers, sommeliers, and senior waitstaff use it to log and retrieve guest intelligence before each service.

## Core Features

- **Guest Profile Management**: Create and maintain rich guest profiles including preferred name, dietary restrictions, allergies (critical: severity levels), beverage preferences, seating preferences, and communication style notes. Support photo attachment for face recognition by staff.
- **Dietary & Allergy Tracking**: Log allergies (severity: mild/moderate/severe/anaphylactic), dietary preferences (vegetarian, halal, gluten-free, no MSG, no peanuts), and dislikes. Flag allergens in the kitchen ticket when the guest is seated. Critical for liability management.
- **Celebration Calendar**: Track birthdays, anniversaries, and other celebration dates. Auto-generate a 7-day lookahead report for the manager. Suggest appropriate gestures (complimentary dessert, flowers, personalized card).
- **Visit History & Spending**: Log each visit with date, party composition, orders (if POS-integrated), total spend, and wine/beverage selections. Calculate lifetime value, visit frequency, and average spend per head.
- **Preference-Based Recommendations**: When a guest makes a reservation, generate a briefing card for the serving team: name, last visit date, favorite dishes, wine preferences, allergies, and any special notes. Uses local LLM for natural language summaries.
- **VIP Tagging & Segmentation**: Classify guests into tiers (Regular, VIP, VVIP) based on visit frequency and spend. Define per-tier service protocols (e.g., VVIPs get amuse-bouche on arrival). Support custom tags (media, food critic, corporate account).

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit) |
| API layer | `fastapi`, `uvicorn` |
| Web dashboard | `jinja2` templates, `htmx` |
| Database | `sqlite3` |
| PDF reports | `reportlab` |
| Notifications | Twilio WhatsApp Business API |
| Data analysis | `pandas` |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/sommelier-memory/
├── main.py                  # FastAPI app entry
├── config.yaml              # VIP thresholds, celebration config
├── guests/
│   ├── profiles.py          # Guest CRUD operations
│   ├── preferences.py       # Dietary/allergy management
│   ├── history.py           # Visit and spending tracker
│   └── segments.py          # VIP tagging and tier logic
├── intelligence/
│   ├── briefing.py          # Pre-service briefing card generator
│   ├── celebrations.py      # Birthday/anniversary tracker
│   └── recommendations.py   # LLM preference summarizer
├── dashboard/
│   ├── routes.py            # Web dashboard routes
│   └── templates/
│       ├── guest_profile.html
│       ├── briefing_card.html
│       ├── celebration_report.html
│       └── dashboard.html
├── integrations/
│   └── pos.py               # POS data import for spending
└── tests/
    ├── test_profiles.py
    ├── test_allergies.py
    └── test_briefings.py

~/OpenClawWorkspace/sommelier-memory/
├── sommelier.db             # SQLite database
├── guest_photos/            # Guest photos (encrypted)
├── briefing_cards/          # Generated briefing PDFs
└── exports/                 # Spending reports
```

## Key Integrations

- **Twilio WhatsApp Business API**: Send celebration reminders to manager 7 days in advance. Optionally send personalized birthday greetings to guests (with opt-in).
- **POS System**: Import order history for spending tracking and preference inference. Support CSV/API integration with Eats365, e-Pos, and FoodZaps.
- **TableMaster AI (sibling tool)**: When a reservation is confirmed, pull guest profile and generate a briefing card. Attach VIP tag to the booking for special treatment.
- **NoShowShield (sibling tool)**: Share guest reliability scores. VIP guests should never be blacklisted without manager override.
- **Telegram Bot API**: Secondary channel for booking confirmations, queue updates, and guest communication.

## GUI Specification

Part of the **F&B Dashboard** (`http://mona.local:8003`) — SommelierMemory tab.

### Views

- **Guest CRM Cards**: Expandable cards with guest photo (optional), dietary restrictions, favorite dishes, wine/drink preferences, celebration dates, and visit history.
- **Celebrations Calendar**: Monthly calendar view highlighting upcoming birthdays, anniversaries, and special occasions for regular guests.
- **Guest Tagging & Search**: Tag guests with custom labels (VIP, wine lover, vegetarian, etc.) and search/filter by any attribute.
- **Visit Timeline**: Per-guest chronological log of visits with order details and special requests noted.

### Mona Integration

- Mona auto-captures guest preferences from WhatsApp conversations and booking notes.
- Mona sends celebration reminders to the restaurant team before upcoming guest occasions.
- Human adds personal observations and preference notes after service.

### Manual Mode

- Staff can manually create guest profiles, record preferences, manage celebrations, and browse the CRM without Mona.

## HK-Specific Requirements

- **Common HK Dietary Preferences**: High prevalence of MSG sensitivity, shellfish allergies, peanut allergies, and lactose intolerance in the HK population. Track these prominently. "No MSG" (走味精) is one of the most common requests in HK dining.
- **Celebration Culture**: HK dining culture places great importance on birthday dinners, Chinese New Year reunion dinners, Mid-Autumn Festival, and wedding anniversaries. Lunar calendar dates should be supported alongside Gregorian. Complimentary birthday cake/dessert is a common VIP gesture.
- **VIP Handling Norms**: HK high-end restaurants maintain "regular" tables — specific tables informally reserved for top clients. Log table preferences as part of the VIP profile. Corporate account guests may use a company name rather than personal name.
- **Wine and Spirits Preferences**: HK is a major wine market (zero duty on wine). Track preferred wine regions, grape varieties, price range, and specific bottles. Whisky and cognac are also significant. Log spirit preferences with brand specificity.
- **Tea Preferences**: Chinese tea selection is integral to dim sum and Chinese fine dining. Track preferred tea types (Pu'er, Tieguanyin, Longjing, Chrysanthemum).
- **Language of Service**: Note whether the guest prefers service in English, Cantonese, Mandarin, or other languages. Critical for staff assignment.
- **Privacy (PDPO)**: Guest profiles contain personal data including dining habits and health information (allergies). Comply with Hong Kong's Personal Data Protection Ordinance. Require opt-in for marketing communications. Provide data access and deletion on request.

## Data Model

```sql
CREATE TABLE guests (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    preferred_name TEXT,
    phone TEXT UNIQUE,
    email TEXT,
    photo_path TEXT,
    language_pref TEXT DEFAULT 'cantonese',
    vip_tier TEXT DEFAULT 'regular',
    tags TEXT,
    total_visits INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    avg_spend_per_head REAL,
    first_visit DATE,
    last_visit DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dietary_info (
    id INTEGER PRIMARY KEY,
    guest_id INTEGER REFERENCES guests(id),
    type TEXT NOT NULL,
    item TEXT NOT NULL,
    severity TEXT,
    notes TEXT
);

CREATE TABLE celebrations (
    id INTEGER PRIMARY KEY,
    guest_id INTEGER REFERENCES guests(id),
    event_type TEXT NOT NULL,
    gregorian_date DATE,
    lunar_date TEXT,
    use_lunar BOOLEAN DEFAULT FALSE,
    notes TEXT,
    last_acknowledged DATE
);

CREATE TABLE visits (
    id INTEGER PRIMARY KEY,
    guest_id INTEGER REFERENCES guests(id),
    visit_date DATE NOT NULL,
    party_size INTEGER,
    party_notes TEXT,
    table_number TEXT,
    total_spend REAL,
    wine_orders TEXT,
    food_highlights TEXT,
    staff_notes TEXT,
    rating INTEGER
);

CREATE TABLE preferences (
    id INTEGER PRIMARY KEY,
    guest_id INTEGER REFERENCES guests(id),
    category TEXT NOT NULL,
    preference TEXT NOT NULL,
    strength TEXT DEFAULT 'like',
    notes TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Restaurant Profile**: Restaurant name, address, cuisine type, operating hours (lunch/dinner/dim sum sessions)
2. **VIP Configuration**: Define VIP tier thresholds (visit count, total spend), custom guest tags
3. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
4. **Sibling Connections**: Link to TableMaster AI for booking data and NoShowShield for reliability scores
5. **Celebration Settings**: Default celebration types (birthday, anniversary), lookahead period, gesture suggestions per VIP tier
6. **Sample Data**: Option to seed demo guest profiles for testing
7. **Connection Test**: Validates all API connections and reports any issues

## Testing Criteria

- [ ] Guest profile CRUD operations work: create, read, update, and soft-delete
- [ ] Allergy flagging appears prominently when a guest with anaphylactic allergies is seated
- [ ] Celebration lookahead correctly identifies guests with birthdays in the next 7 days
- [ ] Briefing card includes guest name, last visit, allergies, wine preference, and VIP tier
- [ ] LLM-generated preference summary is concise, accurate, and usable by serving staff
- [ ] VIP tier auto-upgrades when a guest crosses the visit/spend threshold
- [ ] Visit history correctly calculates lifetime value and average spend per head
- [ ] Lunar calendar celebration dates convert correctly to Gregorian for the current year

## Implementation Notes

- **LLM for summarization only**: Use the local LLM to generate natural language briefing summaries from structured guest data. Example output: "Mrs. Chan is a VVIP who visits biweekly, usually for business dinners of 4-6. She's allergic to shellfish (severe) and prefers Burgundy reds. Her birthday is March 15 — consider the complimentary cake." Load LLM on demand; unload after idle.
- **Allergy criticality**: This is the most safety-critical feature. Allergies with severity "severe" or "anaphylactic" must be displayed with high-visibility formatting (red, bold, persistent banner). Never allow allergy data to be accidentally deleted. Maintain an audit log for allergy modifications.
- **Lunar calendar**: Use `lunardate` or `korean_lunar_calendar` Python library for lunar↔Gregorian conversion. Recalculate Gregorian dates annually since lunar dates shift each year.
- **Memory**: Steady-state <300MB without LLM. Briefing card generation loads LLM temporarily (~5GB). Schedule briefing generation before service (e.g., 5pm for dinner service).
- **Guest photos**: Optional feature. Store photos locally in `~/OpenClawWorkspace/sommelier-memory/guest_photos/` with filename = guest ID. Encrypt at rest. Only accessible through the authenticated dashboard.
- **Data portability**: Provide CSV export for all guest data to comply with PDPO data access requests. Include a data deletion function that removes all traces of a guest from all tables.
- **Logging**: All operations logged to `/var/log/openclaw/sommelier-memory.log` with daily rotation (7-day retention). Guest phone numbers masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication on first access. Guest personal data (phone, dietary/health info) protected under PDPO.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all tool data.
