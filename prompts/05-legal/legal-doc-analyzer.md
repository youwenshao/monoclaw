# LegalDoc Analyzer

## Tool Name & Overview

LegalDoc Analyzer is a local AI-powered clause extraction and review tool for Hong Kong standard contracts. It parses tenancy agreements, employment contracts, and NDAs to identify, classify, and flag unusual or non-standard terms. The tool combines local LLM inference with regex pattern matching to provide fast, privacy-preserving contract analysis without sending sensitive legal documents to external servers.

## Target User

Hong Kong solicitors, paralegals, and in-house counsel who regularly review standard-form contracts and need to quickly identify deviations from market-standard terms, missing clauses, or potentially problematic provisions.

## Core Features

- **Clause Extraction**: Automatically segments contracts into individual clauses with type classification (termination, indemnity, liability cap, rent review, non-compete, confidentiality)
- **Anomaly Flagging**: Highlights terms that deviate significantly from HK market standards (e.g., unusually long notice periods, excessive penalty clauses, one-sided indemnities)
- **Employment Ordinance Compliance**: Checks employment contracts against Cap 57 mandatory provisions (statutory holidays, severance, long service payment, rest days)
- **NDA Clause Library**: Maintains a reference library of standard HK NDA clauses covering scope of confidential information, exclusions, permitted disclosures, and duration
- **Comparison Mode**: Side-by-side comparison of a draft contract against a reference template to surface additions, deletions, and modifications
- **Bilingual Support**: Handles contracts in English, Traditional Chinese, or mixed-language format common in HK practice

## Tech Stack

- **LLM**: MLX-based local inference (Qwen-2.5-7B or Llama-3-8B quantized to 4-bit)
- **Document Parsing**: python-docx, PyPDF2, pdfplumber for extracting text from .docx and .pdf
- **NLP**: regex patterns for clause boundary detection; spaCy (en_core_web_sm) for named entity recognition
- **Database**: SQLite for clause library, flagging rules, and analysis history
- **UI**: Streamlit web interface with clause highlighting and annotation
- **Export**: python-docx for generating annotated Word documents with tracked changes

## File Structure

```
~/OpenClaw/tools/legal-doc-analyzer/
├── app.py                  # Streamlit main application
├── analyzer/
│   ├── clause_extractor.py # Regex + LLM clause segmentation
│   ├── anomaly_detector.py # Deviation scoring against reference templates
│   ├── employment_checker.py # Cap 57 compliance logic
│   └── nda_checker.py      # NDA clause completeness checks
├── models/
│   ├── llm_handler.py      # MLX inference wrapper
│   └── prompts.py          # System prompts for clause classification
├── data/
│   ├── clause_library.db   # SQLite reference clause database
│   ├── templates/           # Standard-form contract templates
│   └── cap57_provisions.json # Employment Ordinance mandatory terms
├── utils/
│   ├── doc_parser.py       # Multi-format document ingestion
│   └── export.py           # Annotated document generation
├── requirements.txt
└── README.md
```

## Key Integrations

- **Local LLM**: MLX framework for on-device inference — no API calls for core analysis
- **File System**: Watches a designated intake folder for new contracts to analyze
- **Export**: Generates annotated .docx files compatible with Microsoft Word track changes

## HK-Specific Requirements

- Employment Ordinance (Cap 57): Validates mandatory provisions including Section 31D (statutory holidays), Section 31R (severance payment), Section 31RA (long service payment), Section 10 (wage period), Section 11A (annual leave)
- Landlord and Tenant (Consolidation) Ordinance (Cap 7): Recognizes standard tenancy clauses, government rent apportionment, and stamp duty obligations
- Standard NDA practice: Reflects typical HK law firm NDA structures including carve-outs for SFC-mandated disclosures and court-ordered disclosure under HK law
- Bilingual clause matching: Handles the common HK practice where the English version prevails in case of discrepancy
- Stamp duty references: Flags unstamped agreements which are inadmissible as evidence under Stamp Duty Ordinance (Cap 117)

## Data Model

```sql
CREATE TABLE contracts (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    contract_type TEXT CHECK(contract_type IN ('tenancy','employment','nda','service','other')),
    language TEXT DEFAULT 'en',
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analysis_status TEXT DEFAULT 'pending'
);

CREATE TABLE clauses (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER REFERENCES contracts(id),
    clause_number TEXT,
    clause_type TEXT,
    text_content TEXT,
    anomaly_score REAL DEFAULT 0.0,
    flag_reason TEXT,
    page_number INTEGER
);

CREATE TABLE reference_clauses (
    id INTEGER PRIMARY KEY,
    contract_type TEXT,
    clause_type TEXT,
    standard_text TEXT,
    source TEXT,
    last_updated TIMESTAMP
);
```

## Testing Criteria

- [ ] Correctly segments a standard HK tenancy agreement into individual clauses with >90% accuracy
- [ ] Identifies all Cap 57 mandatory provisions present/absent in an employment contract
- [ ] Flags a non-standard penalty clause that exceeds typical HK market terms
- [ ] Handles bilingual (EN/TC) contracts without misclassifying clause boundaries
- [ ] Comparison mode highlights additions and deletions against a reference template
- [ ] Processes a 30-page contract within 60 seconds on M4/16GB hardware
- [ ] Exports an annotated .docx with correct track-changes formatting

## Implementation Notes

- Quantize the LLM to 4-bit (MLX q4 format) to fit within 16GB RAM alongside the application
- Use streaming inference to display clause analysis progressively rather than blocking on full-document processing
- Cache clause embeddings for the reference library to avoid recomputation on every analysis
- Regex-first approach for clause boundary detection reduces LLM calls — use LLM only for semantic classification and anomaly reasoning
- Keep the clause reference library as a versioned SQLite DB so firms can customize standard terms for their practice area
- Limit context window to individual clauses (not full documents) to stay within model context limits and improve accuracy
