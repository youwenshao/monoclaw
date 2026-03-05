# DefectsManager

## Tool Name & Overview

DefectsManager is a property defect logging and work order management tool that accepts WhatsApp photo reports with automatic location tagging. It generates work orders for contractors, tracks repair status through to completion, and produces defect resolution reports for building management. Designed for Hong Kong property management companies and building management offices handling ongoing maintenance across residential and commercial properties.

## Target User

Hong Kong property management officers, building managers, Owners' Corporation committee members, and facilities management teams who handle defect reports from residents/tenants and coordinate repair works with contractors.

## Core Features

- **WhatsApp Photo Logging**: Residents report defects by sending photos via WhatsApp with a brief description; the system auto-creates a defect record with timestamp, location, and category classification
- **AI-Assisted Categorization**: Local LLM analyzes defect photos and descriptions to auto-categorize (water seepage, concrete spalling, lift malfunction, plumbing, electrical, common area damage)
- **Work Order Generation**: Creates structured work orders from defect reports with scope of work, priority level, and assigned contractor; exports as PDF for contractor dispatch
- **Contractor Management**: Maintains a contractor database with trade specialties, rates, availability, and performance history; auto-suggests the best contractor for each defect type
- **Status Tracking**: Full lifecycle tracking from report → assessment → work order → in-progress → completion → sign-off with photo evidence at each stage
- **DMC Responsibility Assignment**: Identifies whether a defect falls under individual owner responsibility or common area (Owners' Corporation) responsibility per the Deed of Mutual Covenant

## Tech Stack

- **Messaging**: Twilio WhatsApp Business API for resident defect reporting and status updates
- **Image Analysis**: MLX local LLM with vision capability for defect photo classification; Pillow for image processing
- **Database**: SQLite for defects, work orders, contractor records, and property database
- **UI**: Streamlit dashboard for property management staff
- **PDF**: reportlab for work order and defect report generation
- **Geolocation**: Photo EXIF data + manual floor/unit tagging for defect location

## File Structure

```
~/OpenClaw/tools/defects-manager/
├── app.py                      # Streamlit property management dashboard
├── bot/
│   ├── whatsapp_handler.py     # Twilio webhook for resident reports
│   ├── report_flow.py          # Guided defect reporting conversation
│   └── status_updater.py       # Sends status updates to residents
├── defects/
│   ├── categorizer.py          # AI defect classification from photos/text
│   ├── priority_engine.py      # Urgency assessment and prioritization
│   ├── dmc_resolver.py         # DMC responsibility determination
│   └── lifecycle.py            # Defect status lifecycle management
├── work_orders/
│   ├── generator.py            # Work order creation from defect data
│   ├── contractor_matcher.py   # Auto-assign contractor by trade and availability
│   └── pdf_export.py           # PDF work order generation
├── contractors/
│   ├── database.py             # Contractor CRUD and search
│   └── performance.py          # Contractor performance tracking
├── models/
│   ├── llm_handler.py          # MLX inference wrapper
│   └── prompts.py              # Defect classification prompts
├── data/
│   ├── defects.db              # SQLite database
│   └── dmc_rules.json          # Common DMC responsibility rules
├── requirements.txt
└── README.md
```

## Key Integrations

- **Twilio WhatsApp**: Resident-facing defect reporting and status notification channel
- **Local LLM (MLX)**: Photo and text analysis for defect categorization and severity assessment
- **PDF Generation**: Work order and completion report output for contractors and building management

## HK-Specific Requirements

- Deed of Mutual Covenant (DMC): The governing document for multi-story buildings in HK that defines maintenance responsibilities — individual owners vs Owners' Corporation for common parts
- Building Management Ordinance (Cap 344): Governs Owners' Corporation responsibilities for common area maintenance
- Common HK building defects: Water seepage (most common complaint — handled by Joint Office under BO Section 30C), concrete spalling (especially in older buildings), window frame deterioration, slope maintenance, lift breakdowns
- Joint Office for Investigation of Water Seepage Complaints: For inter-flat water seepage disputes, the tool should generate referral documentation for the Food and Environmental Hygiene Department / Buildings Department Joint Office
- Mandatory Building Inspection Scheme (MBIS): Buildings aged 30+ years must undergo periodic inspection — tool should flag defects discovered during MBIS inspections
- Mandatory Window Inspection Scheme (MWIS): Windows in buildings aged 10+ years require periodic inspection — track window defect reports separately
- Common HK property types: Single-block residential, estate (multi-block), commercial, industrial — each has different DMC structures
- Contractor licensing: Registered minor works contractors, registered electrical workers, licensed plumbers — verify contractor registration for regulated works

## Data Model

```sql
CREATE TABLE properties (
    id INTEGER PRIMARY KEY,
    property_name TEXT NOT NULL,
    address TEXT,
    district TEXT,
    property_type TEXT CHECK(property_type IN ('residential','commercial','industrial','mixed')),
    total_units INTEGER,
    building_age INTEGER,
    dmc_reference TEXT,
    management_company TEXT
);

CREATE TABLE defects (
    id INTEGER PRIMARY KEY,
    property_id INTEGER REFERENCES properties(id),
    unit TEXT,
    floor TEXT,
    location_detail TEXT,
    category TEXT CHECK(category IN ('water_seepage','concrete_spalling','plumbing','electrical','lift','window','common_area','structural','other')),
    description TEXT,
    photo_paths TEXT,  -- JSON array of photo file paths
    reported_by TEXT,
    reported_phone TEXT,
    reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    priority TEXT CHECK(priority IN ('emergency','urgent','normal','low')) DEFAULT 'normal',
    responsibility TEXT CHECK(responsibility IN ('owner','oc','management','pending')) DEFAULT 'pending',
    status TEXT CHECK(status IN ('reported','assessed','work_ordered','in_progress','completed','closed','referred')) DEFAULT 'reported',
    closed_date TIMESTAMP
);

CREATE TABLE work_orders (
    id INTEGER PRIMARY KEY,
    defect_id INTEGER REFERENCES defects(id),
    contractor_id INTEGER REFERENCES contractors(id),
    scope_of_work TEXT,
    estimated_cost REAL,
    actual_cost REAL,
    issue_date DATE,
    target_completion DATE,
    actual_completion DATE,
    completion_photos TEXT,  -- JSON array
    status TEXT CHECK(status IN ('draft','issued','accepted','in_progress','completed','signed_off','disputed')) DEFAULT 'draft',
    sign_off_by TEXT,
    sign_off_date DATE
);

CREATE TABLE contractors (
    id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    trades TEXT,  -- JSON array of trade specialties
    registration_numbers TEXT,
    hourly_rate REAL,
    avg_response_hours REAL,
    performance_score REAL DEFAULT 5.0,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE defect_updates (
    id INTEGER PRIMARY KEY,
    defect_id INTEGER REFERENCES defects(id),
    update_type TEXT,
    description TEXT,
    photo_path TEXT,
    updated_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] WhatsApp photo report creates a defect record with correct timestamp and auto-categorization
- [ ] AI categorizer correctly classifies water seepage, concrete spalling, and electrical defects from photos
- [ ] DMC resolver correctly identifies common area vs individual owner responsibility for a hallway defect
- [ ] Work order PDF generates with complete scope, contractor details, and target completion date
- [ ] Contractor matcher suggests the correct trade specialist (plumber for water seepage, electrician for electrical)
- [ ] Status update sends WhatsApp notification to the resident when defect status changes
- [ ] Dashboard shows defect aging report with overdue items highlighted

## Implementation Notes

- Photo storage: organize as `{property_id}/{year}/{month}/{defect_id}/` to keep filesystem manageable for properties with hundreds of defect reports annually
- DMC responsibility rules vary significantly between properties — provide a configurable rules engine (JSON-based) that property managers can customize for their specific DMC
- Water seepage is the #1 defect type in HK — build a specialized sub-workflow that includes the Joint Office referral process
- Contractor performance scoring: weight response time (40%), quality of work (30%), cost competitiveness (20%), and communication (10%)
- LLM vision for photo analysis: use a multimodal model if available on MLX, or fall back to text-only classification based on the resident's description
- Memory budget: ~4GB if using vision-capable LLM; ~2GB if text-only classification
- Consider integrating with the BMO requirement for Owners' Corporation meeting minutes — defect reports can auto-generate agenda items for OC meetings
