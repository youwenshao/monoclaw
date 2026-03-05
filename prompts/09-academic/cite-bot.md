# CiteBot

## Tool Name & Overview

CiteBot is an automated reference formatting and validation tool for academic researchers. It converts raw citations into properly formatted references for any major citation style (APA 7th, Harvard, MLA 9th, IEEE, Chicago, Vancouver), validates DOIs and retrieves complete metadata, and handles Chinese academic citation formats. It eliminates the tedious manual work of bibliography formatting and ensures citation accuracy.

## Target User

Academic researchers, graduate students, and research assistants at Hong Kong universities who write papers for international and Chinese-language journals and need to format bibliographies accurately across different citation styles.

## Core Features

- **Multi-Style Formatting**: Converts citation data into APA 7th, Harvard, MLA 9th, IEEE, Chicago, Vancouver, and GB/T 7714 (Chinese academic standard) formats with a single click
- **DOI Validation & Enrichment**: Verifies DOI accuracy by querying doi.org; auto-fills missing metadata (journal name, volume, pages, year) from CrossRef/DataCite
- **Batch Processing**: Import a list of references (BibTeX, RIS, or plain text) and reformat the entire bibliography in the target style
- **Chinese Citation Support**: Handles Chinese author names, journal titles, and the GB/T 7714 format requirements including 中文 punctuation and author name ordering
- **Duplicate Detection**: Identifies duplicate references in a bibliography using DOI, title similarity, and author matching
- **Copy-Paste Export**: One-click copy of formatted references for pasting into Word/LaTeX/Google Docs; also exports to BibTeX, RIS, and .docx bibliography

## Tech Stack

- **Citation Data**: httpx for querying DOI.org, CrossRef API, and Semantic Scholar API
- **LLM**: MLX local inference for parsing unstructured citation text into structured fields
- **Citation Formatting**: citeproc-py for CSL-based formatting; custom formatters for GB/T 7714
- **Database**: SQLite for citation library, formatting history, and user preferences
- **UI**: Streamlit with citation input, preview, and batch management interface
- **Export**: BibTeX and RIS generation; python-docx for Word bibliography export

## File Structure

```
~/OpenClaw/tools/cite-bot/
├── app.py                       # Streamlit citation management interface
├── parsing/
│   ├── citation_parser.py       # Parse unstructured citation text into fields
│   ├── bibtex_parser.py         # BibTeX file import
│   ├── ris_parser.py            # RIS file import
│   └── doi_resolver.py          # DOI validation and metadata retrieval
├── formatting/
│   ├── apa_formatter.py         # APA 7th edition formatting
│   ├── harvard_formatter.py     # Harvard style formatting
│   ├── ieee_formatter.py        # IEEE style formatting
│   ├── gbt7714_formatter.py     # GB/T 7714 Chinese academic format
│   ├── csl_engine.py            # CSL-based generic formatting engine
│   └── style_registry.py        # Citation style definitions and selection
├── validation/
│   ├── doi_checker.py           # DOI accuracy verification
│   ├── duplicate_detector.py    # Bibliography duplicate detection
│   └── completeness_checker.py  # Missing field detection
├── models/
│   ├── llm_handler.py           # MLX inference wrapper
│   └── prompts.py               # Citation parsing prompts
├── data/
│   ├── citebot.db               # SQLite database
│   └── csl_styles/              # CSL style definition files
├── requirements.txt
└── README.md
```

## Key Integrations

- **DOI.org / CrossRef API**: Validates DOIs and retrieves complete citation metadata
- **Semantic Scholar API**: Additional metadata source and citation count data
- **Local LLM (MLX)**: Parses unstructured plain-text citations into structured fields (author, title, journal, year, etc.)
- **CSL (Citation Style Language)**: Leverages the open CSL ecosystem for broad style coverage

## HK-Specific Requirements

- GB/T 7714-2015: Chinese national standard for bibliographic references — widely used by Chinese-language journals in HK; tool must implement this format correctly including:
  - Chinese punctuation (，。、；) instead of Western punctuation in Chinese-language entries
  - Author name format: 姓 followed by 名 (surname-first), all Chinese authors listed
  - Mixed-language bibliographies: Chinese entries use GB/T 7714, English entries use the journal's preferred Western style
- HK university submission requirements: Different departments may require specific citation styles — common ones are APA (social sciences), IEEE (engineering), Vancouver (medical), Harvard (business)
- Bilingual author names: HK authors often have both English and Chinese name versions — tool should handle both and use the appropriate one based on the citation language
- HKALL (Hong Kong Academic Library Link): Consider integration for metadata enrichment from the HK academic library consortium
- Traditional vs Simplified Chinese: GB/T 7714 uses Simplified Chinese by convention, but HK academics may need Traditional Chinese formatted citations — support both

## Data Model

```sql
CREATE TABLE citations (
    id INTEGER PRIMARY KEY,
    doi TEXT,
    title TEXT,
    authors TEXT,  -- JSON array: [{"family":"Wong","given":"Tai Man","name_tc":"黃大文"}]
    year INTEGER,
    journal TEXT,
    volume TEXT,
    issue TEXT,
    pages TEXT,
    publisher TEXT,
    url TEXT,
    language TEXT DEFAULT 'en',
    entry_type TEXT CHECK(entry_type IN ('article','book','chapter','conference','thesis','report','website','other')),
    raw_text TEXT,
    metadata_source TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE formatted_references (
    id INTEGER PRIMARY KEY,
    citation_id INTEGER REFERENCES citations(id),
    style TEXT NOT NULL,
    formatted_text TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bibliography_projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT,
    default_style TEXT DEFAULT 'apa7',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE project_citations (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES bibliography_projects(id),
    citation_id INTEGER REFERENCES citations(id),
    sort_order INTEGER,
    in_text_key TEXT,
    notes TEXT
);
```

## Testing Criteria

- [ ] Formats a journal article citation correctly in APA 7th, Harvard, and IEEE styles
- [ ] DOI resolver retrieves complete metadata for a valid DOI (10.xxxx/xxxx)
- [ ] Parses an unstructured plain-text citation ("Wong, T.M. (2023). Title. Journal, 5(2), 10-20.") into structured fields
- [ ] GB/T 7714 formatter produces correct Chinese citation format with proper punctuation
- [ ] Batch import of a 50-entry BibTeX file processes all entries without errors
- [ ] Duplicate detector identifies two entries for the same paper with slightly different titles
- [ ] Export produces a valid BibTeX file importable into Zotero/Mendeley

## Implementation Notes

- Use CrossRef API (free, no key required for polite usage with email in header) as the primary metadata source; fall back to Semantic Scholar for items not in CrossRef
- CSL formatting: leverage citeproc-py with the CSL style repository (10,000+ styles); for GB/T 7714, use a custom CSL or implement a dedicated formatter since CSL support for Chinese standards is limited
- LLM for citation parsing: feed the unstructured text with a structured output prompt requesting JSON fields — this handles the wide variety of citation formats researchers paste in
- Chinese author name handling: Chinese names don't have a given/family split in the same way — detect Chinese characters and format as a single unit per GB/T 7714 rules
- Memory budget: ~4GB (LLM for parsing; the rest of the tool is lightweight text processing)
- DOI validation: batch-check DOIs with a 100ms delay between requests to respect CrossRef rate limits
- Consider implementing a browser extension or clipboard monitor that auto-detects citations copied from Google Scholar and formats them instantly
