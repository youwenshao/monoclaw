# Medical-Dental Dashboard

Unified FastAPI application providing four productivity tools for Hong Kong medical and dental clinics, accessible at `http://mona.local:8006`.

## Tools

| Tool | Purpose |
|------|---------|
| **InsuranceAgent** | BUPA, AXA, Cigna verification; copay estimation; fee schedule; pre-auth forms; claims tracking; EOB parsing |
| **ScribeAI** | Whisper transcription, SOAP note generation, entity extraction, ICD coding, note templates, and finalisation |
| **ClinicScheduler** | WhatsApp booking flow, availability engine, waitlist, walk-in queue, and reminder sender |
| **MedReminderBot** | Medication reminders (morning/afternoon/evening/bedtime), compliance tracking, refill workflow (photo + drug matching), interaction checker |

## Quick Start

```bash
cd tools/06-medical-dental
pip install -e ../shared
pip install -e .
python -m medical_dental.app
```

The dashboard launches at `http://localhost:8006`. On first run, complete the setup wizard at `/setup/`.

## User Guide

### InsuranceAgent

Verify patient coverage with BUPA, AXA, Cigna. Copay estimation from fee schedule and HA rates. Pre-auth form generation and submission. Claims tracker with EOB parsing. Batch verification. Portal rate limiting.

### ScribeAI

Audio capture and Whisper transcription. SOAP note generation. Entity extraction (symptoms, diagnoses, medications). ICD coding. Note templates. Finalisation workflow. Auto-delete audio option.

### ClinicScheduler

Operating hours (morning, afternoon, evening, Saturday). Appointment durations by type (GP, specialist, dental, follow-up). WhatsApp booking flow. Availability engine. Waitlist and walk-in queue. Reminder sender.

### MedReminderBot

Configurable reminder times (morning, afternoon, evening, bedtime). Compliance window. Escalation when compliance drops below threshold. Refill workflow: patient photos medication, drug matcher identifies, refill request. Interaction checker for drug-drug interactions.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `morning_start`, `afternoon_start`, `evening_enabled` | Operating hours |
| `extra` | `appointment_durations` | GP, specialist, dental, follow-up (minutes) |
| `extra` | `supported_insurers`, `ha_rates` | InsuranceAgent |
| `extra` | `whisper_model`, `auto_delete_audio` | ScribeAI |
| `extra` | `reminder_times`, `compliance_window_hours` | MedReminderBot |

## Architecture

```
tools/06-medical-dental/
├── config.yaml
├── medical_dental/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── insurance_agent/
│   ├── scribe_ai/
│   ├── clinic_scheduler/
│   ├── med_reminder/
│   └── dashboard/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/medical-dental/`): `insurance_agent.db`, `scribe_ai.db`, `clinic_scheduler.db`, `med_reminder.db`, `shared.db`, `mona_events.db`.

## Running Tests

```bash
cd tools/06-medical-dental
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/medical_dental_implementation_39743d60.plan.md`
- **Shared Library**: `tools/shared/`
