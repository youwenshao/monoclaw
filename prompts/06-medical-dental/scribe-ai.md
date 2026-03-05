# ScribeAI

## Overview

ScribeAI is a voice-to-text clinical note transcription system that converts doctor-patient consultations into structured medical records. It supports English and Traditional Chinese speech input, auto-structures notes into the SOAP format adapted for Hong Kong medical practice, and integrates extracted clinical data (diagnoses, medications, follow-up plans) into a queryable record. All processing runs locally via Whisper and MLX for complete patient privacy.

## Target User

Hong Kong private practice doctors, dentists, and clinic nurses who spend significant time writing up consultation notes and want to dictate notes in real-time or post-consultation, with automatic structuring into standard medical record format.

## Core Features

- **Real-Time Transcription**: Streams audio from the consultation room microphone and produces running transcription using Whisper (locally hosted)
- **SOAP Note Structuring**: Automatically organizes transcribed content into Subjective, Objective, Assessment, and Plan sections based on clinical context
- **Bilingual STT**: Handles English, Traditional Chinese (Cantonese), and code-mixed speech common in HK medical consultations
- **Clinical Entity Extraction**: Identifies and tags medications, dosages, diagnoses (ICD-10 coding), procedures, and follow-up instructions from the transcription
- **Template Library**: Pre-built note templates for common HK consultations (URTI, hypertension follow-up, diabetes review, dental check-up, dental extraction)
- **Edit & Finalize Workflow**: Doctor reviews the auto-generated note, makes corrections, and finalizes — creating an immutable record with timestamp

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| STT | OpenAI Whisper (medium or small model) via whisper.cpp / MLX-whisper for M4-optimized inference |
| LLM | MLX local inference (Qwen-2.5-7B) for SOAP structuring and clinical entity extraction |
| Audio | PyAudio for microphone capture; soundfile for audio file processing |
| Database | SQLite for patient records, consultation notes, template library |
| UI | Streamlit with real-time transcription display and SOAP note editor |
| Export | python-docx for Word export; HL7 FHIR JSON for standards-compliant export |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/scribe-ai/
├── app.py                     # Streamlit main interface
├── transcription/
│   ├── whisper_engine.py      # Whisper STT wrapper (MLX-optimized)
│   ├── audio_capture.py       # Microphone input handling
│   └── language_detect.py     # Auto-detect EN/TC in audio stream
├── structuring/
│   ├── soap_generator.py      # SOAP note auto-structuring via LLM
│   ├── entity_extractor.py    # Clinical entity recognition (meds, diagnoses)
│   └── icd_coder.py           # ICD-10 code suggestion from diagnoses
├── records/
│   ├── note_manager.py        # CRUD for consultation notes
│   ├── template_engine.py     # Template-based note generation
│   └── finalization.py        # Note review, edit, and lock workflow
├── models/
│   ├── llm_handler.py         # MLX inference wrapper
│   └── prompts.py             # SOAP structuring and entity extraction prompts
├── data/
│   ├── scribe.db              # SQLite database
│   ├── templates/             # Consultation note templates
│   └── icd10_hk.json          # ICD-10 codes commonly used in HK practice
├── requirements.txt
└── README.md
```

### Workspace Data Directory

```
~/OpenClawWorkspace/scribe-ai/
├── db/                        # SQLite database files
├── audio/                     # Temporary consultation recordings
├── exports/                   # Word and FHIR JSON exports
└── logs/                      # Transcription and structuring logs
```

## Key Integrations

- **Whisper (local)**: Speech-to-text running entirely on M4 hardware — no audio sent to cloud services
- **Local LLM (MLX)**: SOAP structuring and clinical NER without external API dependency
- **Export**: HL7 FHIR-compatible JSON for potential eHRSS integration; Word format for printing/filing
- **Telegram Bot API**: Secondary patient communication channel for appointment reminders and medication alerts.

## GUI Specification

Part of the **Medical Dashboard** (`http://mona.local:8502`) — ScribeAI tab.

### Views

- **Recording Interface**: Start/stop recording button with live audio waveform display and real-time transcription text stream scrolling below.
- **SOAP Note Editor**: Four collapsible sections (Subjective, Objective, Assessment, Plan) with rich text editing. Auto-populated from transcription; fully editable.
- **Entity Extraction Sidebar**: Auto-detected medications, diagnoses, and procedures displayed as clickable tag chips. Click to highlight the source text in the transcription.
- **ICD-10 Code Panel**: Suggested ICD-10 codes with search. Click to add to the note's assessment section.
- **Template Selector**: Quick-access dropdown for common consultation types (URTI, hypertension follow-up, diabetes review, dental check-up) that pre-fill SOAP sections.
- **Finalization Workflow**: Review → Approve → Lock flow with immutable audit trail. Locked notes cannot be edited (only amended).

### Mona Integration

- Mona transcribes consultations in real-time and auto-structures notes into SOAP format.
- Mona extracts clinical entities and suggests ICD-10 codes from the transcription.
- Doctor reviews, corrects, and finalizes all notes — Mona never auto-finalizes clinical records.

### Manual Mode

- Doctor can manually type consultation notes, use templates, add ICD-10 codes, and finalize records without Mona's transcription.

## HK-Specific Requirements

- Medical Council of Hong Kong record-keeping guidelines: Clinical records must include date, patient identification, presenting complaint, findings, diagnosis, treatment, and follow-up plan
- SOAP format adaptation for HK practice: "Objective" section should include vital signs in metric units (°C, mmHg, kg), common HK lab reference ranges
- Cantonese speech recognition: Whisper handles Cantonese reasonably well but may need post-processing for medical Cantonese terms; maintain a custom vocabulary file for common HK medical Cantonese
- Code-mixing: HK doctors frequently mix English medical terms into Cantonese speech (e.g., "個 patient 有 hypertension") — the system must handle this gracefully
- Drug names: Reference the HK Drug Formulary for standard drug name spelling used in local practice
- Dental-specific templates: Include standard dental charting notation and common dental procedures using HK dental terminology
- PDPO: Audio recordings and transcriptions are sensitive health data — implement auto-deletion of raw audio after note finalization

## Data Model

```sql
CREATE TABLE patients (
    id INTEGER PRIMARY KEY,
    patient_ref TEXT UNIQUE,
    name_en TEXT,
    name_tc TEXT,
    date_of_birth DATE,
    gender TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE consultations (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    doctor TEXT,
    consultation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    audio_path TEXT,
    raw_transcription TEXT,
    soap_subjective TEXT,
    soap_objective TEXT,
    soap_assessment TEXT,
    soap_plan TEXT,
    icd10_codes TEXT,  -- JSON array of ICD-10 codes
    medications_prescribed TEXT,  -- JSON array
    follow_up_date DATE,
    status TEXT CHECK(status IN ('recording','transcribing','draft','finalized')) DEFAULT 'recording',
    finalized_at TIMESTAMP,
    finalized_by TEXT
);

CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    name TEXT,
    category TEXT,
    soap_template TEXT,  -- JSON with placeholder fields
    common_icd10 TEXT,
    common_medications TEXT,
    language TEXT DEFAULT 'en'
);

CREATE TABLE custom_vocabulary (
    id INTEGER PRIMARY KEY,
    term TEXT,
    category TEXT CHECK(category IN ('medication','diagnosis','procedure','anatomy','general')),
    language TEXT,
    phonetic TEXT
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Clinic Profile**: Clinic name, HKMA registration number, practitioner names and specialties
2. **Audio Settings**: Select microphone input device, test recording level, configure noise threshold for consultation room environment
3. **Speech Model**: Choose Whisper model size (small/medium) based on available RAM; download and verify model weights
4. **Language Preferences**: Default transcription language (English, Cantonese, or auto-detect), import custom vocabulary file for HK medical Cantonese terms
5. **Templates**: Review and customize built-in consultation templates (URTI, hypertension, diabetes, dental check-up)
6. **Export Settings**: Default export format (Word/FHIR JSON), clinic letterhead for Word exports
7. **Sample Data**: Option to load a demo audio recording for testing the transcription pipeline
8. **Connection Test**: Validates microphone input, STT model loading, LLM availability, and reports any issues

## Testing Criteria

- [ ] Transcribes a 5-minute English consultation audio with >90% word accuracy
- [ ] Correctly handles Cantonese speech with English medical term code-mixing
- [ ] Auto-generates SOAP note with all four sections populated from a transcription
- [ ] Extracts at least 3 medications with dosages from a prescription-heavy consultation
- [ ] Suggests appropriate ICD-10 codes for common diagnoses (URTI → J06.9, Hypertension → I10)
- [ ] Template-based note for a diabetes review pre-fills expected fields
- [ ] Finalized note is immutable — editing after finalization creates a new amendment record
- [ ] Total latency: transcription + structuring completes within 30 seconds of a 5-minute recording

## Implementation Notes

- Use Whisper "small" model (or "medium" if RAM permits) for best balance of accuracy and speed on M4; quantize to fp16 for MLX
- Stream audio in 30-second chunks for real-time transcription rather than waiting for the full consultation to end
- SOAP structuring: pass the full transcription to the LLM with a structured output prompt requesting JSON with S/O/A/P keys — this is more reliable than segmenting during transcription
- Custom vocabulary: maintain a local dictionary of HK medical Cantonese terms mapped to English equivalents for post-processing correction
- Memory budget: Whisper small (~1GB) + Qwen-2.5-7B 4-bit (~4GB) + application (~1GB) = ~6GB, leaving headroom on 16GB M4
- Audio files: store temporarily during consultation, auto-delete after note finalization (configurable retention for clinics that want to keep recordings)
- Consider implementing a "dictation mode" for post-consultation use where the doctor dictates a summary rather than recording the full conversation
- **Logging**: All operations logged to `/var/log/openclaw/scribe-ai.log` with daily rotation (7-day retention). Patient names, phone numbers, and clinical data masked in log output.
- **Security**: SQLite database encrypted at rest via SQLCipher. Dashboard requires PIN authentication. Health data is the most sensitive category under PDPO — explicit patient consent required for WhatsApp communication. Audio recordings auto-deleted after note finalization (configurable).
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, STT/LLM model state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive. Exported clinical records maintain SOAP structure and audit trail.
