# MedReminder Bot

## Overview

MedReminder Bot is a medication reminder and refill management system that communicates with patients via WhatsApp and SMS. It sends timely medication reminders, handles chronic medication refill requests with photo-based verification of empty bottles, and tracks patient adherence over time. Designed for Hong Kong clinics managing patients on long-term medication regimens.

## Target User

Hong Kong GP clinics, chronic disease management centres, and pharmacies that prescribe ongoing medications and want to improve patient compliance, reduce missed doses, and streamline the refill process.

## Core Features

- **Scheduled Reminders**: Sends WhatsApp/SMS medication reminders at patient-specific times (morning, afternoon, evening, bedtime) with medication name, dosage, and instructions in the patient's preferred language
- **Compliance Tracking**: Patients reply "taken" or send a confirmation emoji; the system tracks adherence rates and flags patients with declining compliance for clinic follow-up
- **Photo Refill Requests**: Patients photograph their near-empty medication bottles and send via WhatsApp; OCR extracts the drug name and quantity, creating a refill request for clinic review
- **Drug Interaction Alerts**: Cross-references patient medication lists against a local interaction database; alerts clinic staff when new prescriptions may interact with existing medications
- **Refill Workflow**: Clinic staff review refill requests on a dashboard, approve/modify, and the patient receives pickup notification with estimated ready time
- **Compliance Reports**: Generates weekly/monthly adherence reports per patient for doctor review during follow-up consultations

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Messaging | Twilio WhatsApp Business API and Twilio SMS for patient communication |
| OCR | Tesseract OCR (pytesseract) for extracting drug names from bottle photos; MLX LLM as fallback for ambiguous text |
| Scheduler | APScheduler with SQLite job store for reliable reminder delivery |
| Database | SQLite for patient profiles, medication lists, compliance logs, refill requests |
| UI | Streamlit dashboard for clinic staff to manage reminders and review refill requests |
| Drug Data | Local JSON/SQLite database of common HK-prescribed medications with bilingual names |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/med-reminder-bot/
├── app.py                     # Streamlit clinic dashboard
├── bot/
│   ├── whatsapp_handler.py    # Twilio webhook for patient messages
│   ├── sms_handler.py         # SMS message handling
│   └── message_templates.py   # Bilingual reminder message templates
├── reminders/
│   ├── scheduler.py           # APScheduler reminder engine
│   ├── compliance_tracker.py  # Patient adherence tracking
│   └── escalation.py          # Low-compliance patient flagging
├── refill/
│   ├── photo_processor.py     # OCR extraction from bottle photos
│   ├── refill_workflow.py     # Refill request lifecycle management
│   └── drug_matcher.py        # Match OCR text to drug database
├── safety/
│   └── interaction_checker.py # Drug interaction cross-reference
├── data/
│   ├── medreminder.db         # SQLite database
│   └── drug_database.json     # HK common medications with bilingual names
├── requirements.txt
└── README.md
```

### Workspace Data Directory

```
~/OpenClawWorkspace/med-reminder-bot/
├── db/                        # SQLite database files
├── photos/                    # Medication bottle photos
├── logs/                      # Reminder and compliance logs
└── reports/                   # Generated compliance reports
```

## Key Integrations

- **Twilio WhatsApp/SMS**: Dual-channel patient communication with automatic fallback from WhatsApp to SMS
- **Tesseract OCR**: Extracts printed text from medication bottle photos for refill processing
- **Local LLM (MLX)**: Fallback OCR interpretation and natural language understanding of patient messages
- **Telegram Bot API**: Secondary patient communication channel for appointment reminders and medication alerts.

## GUI Specification

Part of the **Medical Dashboard** (`http://mona.local:8502`) — MedReminder tab.

### Views

- **Patient Medication Table**: List of patients with their active medications, dosage schedules, and overall compliance rates.
- **Reminder Status Board**: Today's reminders with sent/acknowledged/missed status per patient per medication.
- **Refill Management**: Queue of refill requests (from WhatsApp photo submissions) with OCR results, approval controls, and ready-for-pickup notifications.
- **Compliance Reports**: Weekly/monthly adherence charts per patient with trend lines and clinic-wide averages.
- **Drug Interaction Alerts**: Active warnings panel showing flagged interactions for current patient medication combinations.

### Mona Integration

- Mona sends medication reminders at scheduled times and tracks patient responses automatically.
- Mona processes bottle photo refill requests via OCR and queues them for clinic staff review.
- Human approves refill requests and reviews compliance trends for follow-up decisions.

### Manual Mode

- Clinic staff can manually manage medication lists, send reminders, process refills, and review compliance without Mona.

## HK-Specific Requirements

- Drug Office (Department of Health) regulations: Medications dispensed must comply with Pharmacy and Poisons Ordinance (Cap 138); refills for Part I poisons require doctor authorization
- Bilingual drug names: All medications must be referenced in both English generic name and Traditional Chinese (e.g., Metformin / 二甲雙胍); many elderly patients only recognize the Chinese name
- DH (Department of Health) labelling requirements: Medication reminders should echo the label format — drug name, strength, dosage, route, frequency
- Common HK chronic medications: Antihypertensives, diabetes medications, cholesterol-lowering drugs, asthma inhalers — reminder templates should be pre-built for these categories
- PDPO compliance: Health data is sensitive personal data; explicit consent required for WhatsApp medication reminders; data retention policy must be documented
- Public hospital vs private: Many HK patients receive chronic medications from HA (Hospital Authority) but seek private refills for convenience — system should note medication source

## Data Model

```sql
CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    name_en TEXT,
    name_tc TEXT,
    phone TEXT UNIQUE NOT NULL,
    whatsapp_enabled BOOLEAN DEFAULT TRUE,
    preferred_language TEXT DEFAULT 'tc',
    date_of_birth DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE medications (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    drug_name_en TEXT NOT NULL,
    drug_name_tc TEXT,
    dosage TEXT,
    frequency TEXT,
    time_slots TEXT,  -- JSON array: ["08:00","20:00"]
    prescribing_doctor TEXT,
    start_date DATE,
    end_date DATE,
    refill_eligible BOOLEAN DEFAULT TRUE,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE compliance_logs (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    medication_id INTEGER REFERENCES medications(id),
    reminder_sent_at TIMESTAMP,
    response TEXT,
    responded_at TIMESTAMP,
    taken BOOLEAN
);

CREATE TABLE refill_requests (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    medication_id INTEGER REFERENCES medications(id),
    photo_path TEXT,
    ocr_result TEXT,
    status TEXT CHECK(status IN ('pending','approved','modified','rejected','ready','collected')) DEFAULT 'pending',
    reviewed_by TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ready_at TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Clinic Profile**: Clinic name, address, pharmacy license details, operating hours
2. **Practitioners**: Add doctors with name, specialty, and prescribing privileges
3. **Messaging Setup**: Twilio API credentials for WhatsApp/SMS, Telegram bot token
4. **Medication Database**: Import or verify local drug database; add custom medications commonly prescribed at this clinic
5. **Reminder Defaults**: Default reminder times (morning 08:00, afternoon 14:00, evening 20:00, bedtime 22:00), compliance response window (default 2 hours)
6. **Refill Workflow**: Configure refill approval requirements, Part I poison authorization rules, pickup notification templates
7. **Sample Data**: Option to seed demo patients and medication schedules for testing
8. **Connection Test**: Validates all API connections, OCR engine availability, and reports any issues

## Testing Criteria

- [ ] Sends medication reminders at correct times for a patient with 3 daily medications across different time slots
- [ ] Tracks compliance correctly when patient replies "taken" vs no response within the 2-hour window
- [ ] OCR correctly extracts drug name from a clear photo of a medication bottle label
- [ ] Refill request appears in clinic dashboard within 30 seconds of photo submission
- [ ] Drug interaction checker flags a known interaction (e.g., warfarin + aspirin) when adding a new medication
- [ ] Compliance report accurately shows weekly adherence percentages per medication
- [ ] Bilingual reminders render correctly in both English and Traditional Chinese

## Implementation Notes

- APScheduler jobs should be patient-specific with unique job IDs — use `f"remind_{patient_id}_{med_id}_{time_slot}"` for easy management
- Store medication bottle photos in a local directory with patient_id subfolders; reference paths in SQLite rather than storing blobs
- OCR pipeline: resize image → enhance contrast → Tesseract extraction → fuzzy match against drug database → LLM fallback if confidence <70%
- Drug interaction database: start with a curated list of 200 common HK-prescribed drugs and their known major interactions; expand over time
- Compliance window: mark a dose as "taken" if patient responds within 2 hours of reminder; "missed" after 2 hours with no response
- Memory budget: ~3GB (APScheduler is lightweight; OCR is invoked on-demand; LLM only for fallback)
- Elderly patient consideration: support voice message responses — use Whisper for STT to detect "taken" confirmations from voice notes
- **Logging**: All operations logged to `/var/log/openclaw/med-reminder-bot.log` with daily rotation (7-day retention). Patient names, phone numbers, and clinical data masked in log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Dashboard requires PIN authentication. Health data is the most sensitive category under PDPO — explicit patient consent required for WhatsApp communication. Medication bottle photos auto-deleted after refill processing (configurable).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, OCR engine state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Exported records maintain medication history and compliance data.
