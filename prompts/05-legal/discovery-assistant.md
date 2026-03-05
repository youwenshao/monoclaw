# DiscoveryAssistant

## Tool Name & Overview

DiscoveryAssistant is an e-discovery tool for Hong Kong litigation support that identifies privileged communications within email archives, auto-categorizes documents by relevance, and generates privilege logs. It uses local LLM inference for document classification and privilege detection, ensuring that sensitive legal materials never leave the local machine during review.

## Target User

Hong Kong litigation lawyers, discovery reviewers, and paralegals who need to process large volumes of emails and documents during the discovery/disclosure phase of civil proceedings in the High Court or District Court.

## Core Features

- **Privilege Detection**: Scans emails and attachments to identify legal professional privilege (solicitor-client communications) and litigation privilege, flagging documents for exclusion from disclosure
- **Document Categorization**: Auto-classifies documents into relevance tiers (directly relevant, potentially relevant, not relevant) based on case-specific keywords and semantic analysis
- **Privilege Log Generation**: Produces formatted privilege logs compliant with HK High Court Practice Direction requirements, including document date, author, recipient, and basis for privilege claim
- **Email Archive Parsing**: Ingests .pst, .mbox, and .eml files; extracts headers, body text, and attachments for unified review
- **Keyword Search & Tagging**: Boolean and proximity search across the document corpus with manual tag overlay for reviewer notes
- **Deduplication**: MD5/SHA256 hashing to identify and group exact and near-duplicate documents

## Tech Stack

- **LLM**: MLX local inference (Qwen-2.5-7B quantized) for privilege classification and relevance scoring
- **Email Parsing**: Python `email` module, `imaplib` for live mailbox connection, `libpff` bindings for .pst files
- **Text Extraction**: PyPDF2, python-docx, openpyxl for attachment content extraction
- **Search**: Whoosh full-text search index for keyword queries
- **Database**: SQLite for document metadata, tags, privilege log entries
- **UI**: Streamlit with paginated document review interface
- **Export**: openpyxl for Excel privilege log export, python-docx for Word format

## File Structure

```
~/OpenClaw/tools/discovery-assistant/
├── app.py                    # Streamlit main review interface
├── ingestion/
│   ├── email_parser.py       # .pst, .mbox, .eml parsing
│   ├── attachment_extractor.py # Extract and OCR attachments
│   └── deduplicator.py       # Hash-based dedup logic
├── analysis/
│   ├── privilege_detector.py  # LLM + rule-based privilege classification
│   ├── relevance_scorer.py    # Document relevance tier assignment
│   └── keyword_search.py      # Whoosh index and Boolean search
├── models/
│   ├── llm_handler.py         # MLX inference wrapper
│   └── prompts.py             # Privilege/relevance classification prompts
├── reports/
│   ├── privilege_log.py       # Generates privilege log spreadsheets
│   └── review_summary.py      # Case review statistics
├── data/
│   └── discovery.db           # SQLite database
├── requirements.txt
└── README.md
```

## Key Integrations

- **Email Systems**: IMAP connection for live mailbox scanning; file-based import for .pst/.mbox archives
- **Local LLM**: MLX for all classification — no external API calls for document content analysis
- **Export**: Excel-formatted privilege logs for filing with court; CSV export for litigation support platforms

## HK-Specific Requirements

- Legal Professional Privilege under HK law follows English common law principles — communications must be between solicitor and client, made for the purpose of seeking/giving legal advice, and intended to be confidential
- Litigation privilege extends to communications with third parties made for the dominant purpose of pending or contemplated litigation
- Practice Direction 5.2 (Discovery) of the High Court governs disclosure obligations in civil proceedings
- Privilege log format should include: document date, document type, author, all recipients, subject matter description (without revealing privileged content), and specific privilege claimed
- Without-prejudice communications must also be identified and flagged separately from privileged documents
- Documents in Traditional Chinese must be handled with the same classification accuracy as English documents

## Data Model

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    source_file TEXT,
    doc_type TEXT CHECK(doc_type IN ('email','attachment','standalone')),
    date_created TIMESTAMP,
    author TEXT,
    recipients TEXT,
    subject TEXT,
    body_text TEXT,
    hash_md5 TEXT,
    hash_sha256 TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of INTEGER REFERENCES documents(id)
);

CREATE TABLE classifications (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    relevance_tier TEXT CHECK(relevance_tier IN ('directly_relevant','potentially_relevant','not_relevant')),
    privilege_status TEXT CHECK(privilege_status IN ('privileged','not_privileged','partial','needs_review')),
    privilege_type TEXT,
    confidence_score REAL,
    reviewer_override TEXT,
    reviewed_by TEXT,
    review_date TIMESTAMP
);

CREATE TABLE privilege_log (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    log_date DATE,
    description TEXT,
    privilege_basis TEXT,
    status TEXT DEFAULT 'draft'
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    tag_name TEXT,
    tagged_by TEXT,
    tag_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Successfully parses a .pst archive with 1,000+ emails and extracts all body text and attachments
- [ ] Correctly identifies solicitor-client privilege in >85% of test cases (English and Chinese)
- [ ] Generates a privilege log with all required HK High Court fields
- [ ] Deduplication correctly groups identical emails forwarded to multiple recipients
- [ ] Boolean keyword search returns accurate results with AND/OR/NOT/NEAR operators
- [ ] Processes 500 documents within 30 minutes on M4/16GB hardware
- [ ] Export produces valid .xlsx privilege log openable in Excel

## Implementation Notes

- Process documents in batches of 50 to manage memory on 16GB RAM — load, classify, persist, then release
- Use the LLM for semantic privilege detection only after keyword pre-filtering to reduce inference calls
- Build the Whoosh search index incrementally during ingestion rather than as a separate pass
- Store extracted text in SQLite rather than keeping full documents in memory
- For .pst parsing, use `libpff` Python bindings or fall back to converting via `readpst` CLI tool
- Implement a review queue where the LLM's low-confidence classifications are surfaced first for human review
- Keep all processing strictly local — this tool must never transmit document content to external services
