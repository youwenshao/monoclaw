# ScribeAI

## Tool Name & Overview

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

- **STT**: OpenAI Whisper (medium or small model) via whisper.cpp / MLX-whisper for M4-optimized inference
- **LLM**: MLX local inference (Qwen-2.5-7B) for SOAP structuring and clinical entity extraction
- **Audio**: PyAudio for microphone capture; soundfile for audio file processing
- **Database**: SQLite for patient records, consultation notes, template library
- **UI**: Streamlit with real-time transcription display and SOAP note editor
- **Export**: python-docx for Word export; HL7 FHIR JSON for standards-compliant export

## File Structure

```
~/OpenClaw/tools/scribe-ai/
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

## Key Integrations

- **Whisper (local)**: Speech-to-text running entirely on M4 hardware — no audio sent to cloud services
- **Local LLM (MLX)**: SOAP structuring and clinical NER without external API dependency
- **Export**: HL7 FHIR-compatible JSON for potential eHRSS integration; Word format for printing/filing

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
