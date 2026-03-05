# ClinicScheduler

## Tool Name & Overview

ClinicScheduler is a 24/7 WhatsApp-based appointment booking system for Hong Kong medical and dental clinics. It provides real-time availability checking across doctors, rooms, and equipment, handles booking confirmations and rescheduling, and maintains a waitlist for popular time slots. The system is designed to reduce front-desk phone volume and enable after-hours appointment booking.

## Target User

Hong Kong private clinic owners, practice managers, and front-desk staff at GP clinics, specialist practices, and dental offices who want to automate appointment scheduling and reduce missed calls outside business hours.

## Core Features

- **WhatsApp Booking Flow**: Conversational appointment booking via WhatsApp Business API — patients select doctor, service type, preferred date/time, and receive instant confirmation
- **Real-Time Availability**: Maintains live availability grid factoring in doctor schedules, room allocation, equipment availability (e.g., X-ray, dental chair), and buffer times between appointments
- **Multi-Doctor Support**: Handles scheduling for clinics with multiple practitioners, each with their own availability patterns (morning/afternoon sessions, specific weekdays)
- **Waitlist Management**: When preferred slots are full, adds patients to a prioritized waitlist and auto-notifies when cancellations open up slots
- **Reminder System**: Sends WhatsApp reminders 24 hours and 2 hours before appointments; tracks confirmation responses to reduce no-shows
- **Walk-In Queue**: Manages a parallel walk-in queue with estimated wait times displayed via a simple web view for the clinic's waiting room

## Tech Stack

- **Messaging**: Twilio WhatsApp Business API for patient communication
- **LLM**: MLX local inference for natural language understanding of patient messages
- **Scheduler**: Python `datetime` + custom scheduling engine; APScheduler for reminders
- **Database**: SQLite for appointments, doctor schedules, patient records
- **UI**: Streamlit dashboard for clinic staff; simple HTML page for waiting room display
- **Calendar**: icalendar for .ics export; optional Google Calendar sync

## File Structure

```
~/OpenClaw/tools/clinic-scheduler/
├── app.py                     # Streamlit clinic staff dashboard
├── bot/
│   ├── whatsapp_handler.py    # Twilio webhook for patient messages
│   ├── booking_flow.py        # Conversational booking state machine
│   └── reminder_sender.py     # Appointment reminder logic
├── scheduling/
│   ├── availability.py        # Real-time slot computation
│   ├── booking_engine.py      # Booking creation, modification, cancellation
│   ├── waitlist.py            # Waitlist queue management
│   └── walk_in_queue.py       # Walk-in patient queue and wait time estimation
├── models/
│   ├── llm_handler.py         # MLX inference for NLU
│   └── prompts.py             # Booking conversation prompts
├── data/
│   ├── clinic.db              # SQLite database
│   └── hk_holidays.json       # HK public holiday schedule
├── templates/
│   └── waiting_room.html      # Walk-in queue display page
├── requirements.txt
└── README.md
```

## Key Integrations

- **Twilio WhatsApp Business API**: Primary patient-facing communication channel
- **Google Calendar API** (optional): Two-way sync for doctors who manage schedules in Google Calendar
- **Local LLM (MLX)**: Understanding freeform patient messages (e.g., "Can I see Dr. Wong next Tuesday afternoon?")

## HK-Specific Requirements

- HKMA (Hong Kong Medical Association) electronic health record interoperability: Stub integration point for future eHRSS (Electronic Health Record Sharing System) connection
- Typical HK private clinic hours: Morning session 9:00-13:00, Afternoon session 14:30-18:00, some clinics have evening sessions 18:30-21:00
- Public holidays: 17 statutory general holidays in HK — clinic closures must be reflected in availability
- Saturday scheduling: Many HK clinics operate Saturday mornings (9:00-13:00) only
- Bilingual messaging: All WhatsApp messages must support English and Traditional Chinese; patient language preference should be remembered
- PDPO compliance: Patient phone numbers and appointment data are personal data — collection requires PICS notice, data must be stored securely
- Common HK clinic appointment durations: GP consultation 10-15 mins, specialist 20-30 mins, dental cleaning 45 mins, dental procedure 60+ mins

## Data Model

```sql
CREATE TABLE doctors (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    specialty TEXT,
    registration_number TEXT,
    default_slot_duration INTEGER DEFAULT 15,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,
    doctor_id INTEGER REFERENCES doctors(id),
    day_of_week INTEGER CHECK(day_of_week BETWEEN 0 AND 6),
    session TEXT CHECK(session IN ('morning','afternoon','evening')),
    start_time TIME,
    end_time TIME,
    room TEXT,
    effective_from DATE,
    effective_until DATE
);

CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    patient_phone TEXT NOT NULL,
    patient_name TEXT,
    patient_name_tc TEXT,
    doctor_id INTEGER REFERENCES doctors(id),
    service_type TEXT,
    appointment_date DATE,
    start_time TIME,
    end_time TIME,
    room TEXT,
    status TEXT CHECK(status IN ('booked','confirmed','arrived','in_progress','completed','cancelled','no_show')) DEFAULT 'booked',
    reminder_sent BOOLEAN DEFAULT FALSE,
    source TEXT CHECK(source IN ('whatsapp','phone','walk_in','online')) DEFAULT 'whatsapp',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE waitlist (
    id INTEGER PRIMARY KEY,
    patient_phone TEXT,
    patient_name TEXT,
    doctor_id INTEGER,
    preferred_date DATE,
    preferred_session TEXT,
    service_type TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'waiting',
    notified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] WhatsApp booking flow completes appointment creation in under 6 messages
- [ ] Availability engine correctly blocks double-booked slots and respects buffer times
- [ ] Waitlist notification fires within 5 minutes of a cancellation opening a slot
- [ ] Reminder messages sent at 24h and 2h marks before appointment time
- [ ] Dashboard shows correct daily schedule for each doctor with color-coded status
- [ ] Walk-in queue displays accurate estimated wait times based on current appointments
- [ ] Handles bilingual conversation (switching between EN and TC mid-flow)

## Implementation Notes

- The scheduling engine should use an interval-based approach (not discrete slots) to handle variable appointment durations
- Keep the WhatsApp webhook server lightweight (Flask/FastAPI) — LLM inference is only needed for freeform messages, not structured button responses
- Implement optimistic locking on appointment slots to prevent race conditions when two patients book simultaneously
- Cache today's availability in memory (refresh every 60 seconds) to minimize database reads during peak booking times
- Walk-in queue estimation: calculate based on remaining appointment durations plus average walk-in consultation time
- Total memory budget: ~4GB for this tool (webhook server + LLM + Streamlit), leaving room for other tools on 16GB M4
- Consider implementing a simple SMS fallback via Twilio for patients who don't use WhatsApp (common among elderly patients in HK)
