# InsuranceAgent

## Overview

InsuranceAgent is a pre-authorization and insurance verification tool for Hong Kong medical and dental clinics. It checks patient coverage with major HK insurers (Bupa, AXA, Cigna, and others), estimates patient co-pay amounts before the consultation, and handles pre-authorization submissions for procedures requiring prior approval. This reduces billing surprises and streamlines the front-desk insurance workflow.

## Target User

Hong Kong private clinic administrators, front-desk staff, and practice managers who need to verify patient insurance coverage, estimate out-of-pocket costs, and manage pre-authorization requests across multiple insurer systems.

## Core Features

- **Coverage Verification**: Checks patient policy status, benefit limits, and remaining annual balance with major HK insurers via their provider portals or API endpoints
- **Co-Pay Estimation**: Calculates expected patient co-pay based on the planned procedure, insurer schedule of benefits, and the clinic's fee schedule
- **Pre-Authorization Submission**: Auto-populates and submits pre-authorization forms for procedures requiring prior approval (surgeries, specialist referrals, advanced imaging)
- **Insurer Rate Comparison**: For uninsured or partially covered procedures, shows cost comparison between HA (Hospital Authority) public rates and the clinic's private rates
- **Claim Tracking**: Tracks submitted claims through to settlement; flags overdue payments for follow-up
- **Batch Verification**: Verifies insurance for all next-day appointments in bulk, flagging any coverage issues before patients arrive

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Web Automation | Playwright for headless browser interaction with insurer portals that lack APIs |
| HTTP | httpx/requests for API-based insurer integrations |
| LLM | MLX local inference for parsing unstructured portal responses and extracting coverage details |
| Database | SQLite for patient insurance records, claim history, fee schedules |
| UI | Streamlit dashboard with patient insurance status overview and claim tracking |
| PDF | PyPDF2 and reportlab for parsing insurer EOB (Explanation of Benefits) documents and generating claim forms |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/insurance-agent/
├── app.py                      # Streamlit clinic dashboard
├── verification/
│   ├── bupa_connector.py       # Bupa HK portal/API integration
│   ├── axa_connector.py        # AXA HK portal/API integration
│   ├── cigna_connector.py      # Cigna HK portal/API integration
│   ├── generic_connector.py    # Template for additional insurers
│   └── batch_verify.py         # Bulk verification for next-day appointments
├── estimation/
│   ├── copay_calculator.py     # Co-pay estimation engine
│   ├── fee_schedule.py         # Clinic fee schedule management
│   └── ha_rate_lookup.py       # HA Gazette public hospital rate reference
├── preauth/
│   ├── form_generator.py       # Pre-authorization form auto-population
│   └── submission_handler.py   # Pre-auth submission and tracking
├── claims/
│   ├── claim_tracker.py        # Claim lifecycle management
│   └── eob_parser.py           # Parse insurer EOB documents
├── models/
│   ├── llm_handler.py          # MLX inference wrapper
│   └── prompts.py              # Portal response parsing prompts
├── data/
│   ├── insurance.db            # SQLite database
│   └── fee_schedules/          # Insurer benefit schedules (JSON)
├── requirements.txt
└── README.md
```

### Workspace Data Directory

```
~/OpenClawWorkspace/insurance-agent/
├── db/                        # SQLite database files
├── forms/                     # Generated pre-authorization forms
├── eob/                       # Parsed EOB documents
├── screenshots/               # Portal automation debug screenshots
└── logs/                      # Verification and claim logs
```

## Key Integrations

- **Bupa HK**: Provider portal automation or API for real-time eligibility checks and pre-authorization
- **AXA Hong Kong**: General insurance portal for medical coverage verification
- **Cigna Hong Kong**: Group medical insurance verification
- **HA Gazette Rates**: Reference lookup for Hospital Authority public rates (for patient cost comparison)
- **Local LLM (MLX)**: Parsing unstructured insurer portal responses into structured coverage data
- **Telegram Bot API**: Secondary patient communication channel for appointment reminders and medication alerts.

## GUI Specification

Part of the **Medical Dashboard** (`http://mona.local:8502`) — InsuranceAgent tab.

### Views

- **Verification Form**: Patient and policy lookup form with insurer selector. Results display coverage status, benefit limits, and remaining balance.
- **Co-Pay Estimator**: Calculator showing expected patient out-of-pocket cost based on planned procedure, insurer schedule, and clinic fee schedule.
- **Pre-Authorization Builder**: Form to create and submit pre-auth requests with auto-populated patient and procedure details. Status tracking (draft → submitted → approved/denied).
- **Claim Tracker**: Board showing all submitted claims with status (pending/approved/partial/rejected/paid) and insurer reference numbers. Overdue payment flags.
- **Batch Verification**: One-click verification for all next-day appointments with summary of coverage issues flagged.

### Mona Integration

- Mona runs batch verification for next-day appointments overnight and flags coverage issues in the morning.
- Mona submits pre-authorization requests through insurer portals and tracks response status.
- Human reviews coverage exceptions and handles patient-facing cost discussions.

### Manual Mode

- Admin can manually verify coverage, estimate co-pays, submit pre-authorizations, and track claims without Mona.

## HK-Specific Requirements

- Major HK medical insurers to support: Bupa, AXA, Cigna, Prudential, Manulife, HSBC Insurance, FWD, Zurich — prioritize the first three for initial implementation
- HK insurance market structure: Most private medical insurance in HK is group insurance through employers; individual policies less common
- Common coverage categories: GP consultation, specialist consultation, physiotherapy, dental (basic/major), hospital room & board, surgical benefits
- HA vs private pricing: Many patients want to compare private clinic cost against the HA public hospital equivalent (HA general outpatient: HK$50, specialist: HK$135, A&E: HK$180)
- Insurance terminology in Traditional Chinese: All patient-facing cost estimates should be bilingual
- Pre-authorization typical turnaround: 3-5 business days for most HK insurers; tool should set expectations and track timelines
- Clinic fee schedules: HK private GP consultation typically HK$300-800; specialist HK$800-2,500; dental check-up HK$500-1,500

## Data Model

```sql
CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_tc TEXT,
    phone TEXT,
    date_of_birth DATE
);

CREATE TABLE insurance_policies (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    insurer TEXT NOT NULL,
    policy_number TEXT,
    group_name TEXT,
    member_id TEXT,
    plan_type TEXT,
    effective_date DATE,
    expiry_date DATE,
    annual_limit REAL,
    remaining_balance REAL,
    last_verified TIMESTAMP,
    status TEXT CHECK(status IN ('active','expired','suspended','unknown')) DEFAULT 'unknown'
);

CREATE TABLE coverage_details (
    id INTEGER PRIMARY KEY,
    policy_id INTEGER REFERENCES insurance_policies(id),
    benefit_category TEXT,
    sub_limit REAL,
    copay_percentage REAL,
    copay_fixed REAL,
    deductible REAL,
    requires_preauth BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE TABLE claims (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    policy_id INTEGER REFERENCES insurance_policies(id),
    claim_date DATE,
    procedure_code TEXT,
    description TEXT,
    billed_amount REAL,
    approved_amount REAL,
    patient_copay REAL,
    status TEXT CHECK(status IN ('pending','submitted','approved','partial','rejected','paid','appealed')) DEFAULT 'pending',
    insurer_reference TEXT,
    submitted_at TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE preauthorizations (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    policy_id INTEGER REFERENCES insurance_policies(id),
    procedure_description TEXT,
    estimated_cost REAL,
    submission_date DATE,
    status TEXT CHECK(status IN ('draft','submitted','approved','denied','expired')) DEFAULT 'draft',
    reference_number TEXT,
    response_date DATE,
    approved_amount REAL,
    notes TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Clinic Profile**: Clinic name, provider registration numbers for each insurer panel, clinic address
2. **Insurer Portal Credentials**: Login credentials for Bupa, AXA, Cigna, and other supported insurer provider portals
3. **Messaging Setup**: Twilio API credentials for WhatsApp/SMS, Telegram bot token (for patient cost notifications)
4. **Fee Schedule**: Import or configure the clinic's fee schedule for common procedures
5. **Insurance Panels**: Configure supported insurers, plan types, and benefit schedule documents
6. **HA Rate Reference**: Verify Hospital Authority public rate data is current (GP $50, Specialist $135, A&E $180)
7. **Sample Data**: Option to seed demo patients, policies, and claims for testing
8. **Connection Test**: Validates insurer portal connectivity, LLM availability, and reports any issues

## Testing Criteria

- [ ] Successfully verifies coverage status for a Bupa HK policy via portal automation
- [ ] Co-pay estimation matches manual calculation for a GP consultation with 20% co-insurance
- [ ] Batch verification processes 30 next-day appointments within 10 minutes
- [ ] Pre-authorization form auto-populates with correct patient, policy, and procedure details
- [ ] Claim tracker correctly updates status from "submitted" to "paid" when EOB is received
- [ ] HA rate comparison displays correct public vs private cost for a specialist consultation
- [ ] Dashboard surfaces coverage warnings (expired policy, exhausted benefit) prominently

## Implementation Notes

- Insurer portal automation via Playwright is fragile — implement robust retry logic, screenshot-on-failure for debugging, and graceful degradation when portals change
- Cache coverage verification results for 24 hours to avoid redundant portal queries for the same patient
- Fee schedule data should be stored as JSON files per insurer, version-controlled so updates to benefit schedules can be tracked
- Start with Bupa as the primary connector (largest HK medical insurer), then AXA, then Cigna — use a connector interface pattern so new insurers can be added with minimal code changes
- LLM is used primarily for parsing semi-structured portal responses (HTML tables, PDF EOBs) into structured data — not for decision-making on coverage
- Memory budget: ~3GB (Playwright browser instance is the heaviest component; LLM only invoked for parsing tasks)
- Consider rate-limiting portal requests to avoid being blocked by insurer websites
- **Logging**: All operations logged to `/var/log/openclaw/insurance-agent.log` with daily rotation (7-day retention). Patient names, phone numbers, and clinical data masked in log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Dashboard requires PIN authentication. Health data is the most sensitive category under PDPO — explicit patient consent required for WhatsApp communication. Insurer portal credentials stored in encrypted configuration.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, insurer portal reachability, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Exported records maintain claim history and pre-authorization audit trail.
