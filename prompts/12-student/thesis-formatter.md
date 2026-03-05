# ThesisFormatter

## Tool Name & Overview

ThesisFormatter automates the tedious formatting requirements of university theses and dissertations for Hong Kong universities. It generates proper table of contents, figure lists, table lists, and bibliography sections, and enforces university-specific formatting guidelines (margins, fonts, heading styles, page numbering). Supports HKU, CUHK, HKUST, PolyU, CityU, and other HK university formats using python-docx for precise Word document manipulation.

## Target User

Hong Kong postgraduate students (MPhil and PhD) and final-year undergraduates writing capstone projects who need to format their thesis according to their university's specific submission guidelines, and want to avoid the hours of manual Word formatting that this typically requires.

## Core Features

- **University Template Selection**: Pre-built formatting profiles for major HK universities (HKU, CUHK, HKUST, PolyU, CityU, HKBU, LingU, EdUHK) with correct margins, fonts, heading styles, and page numbering schemes
- **Auto-Generated TOC**: Creates properly formatted and hyperlinked Table of Contents with correct heading levels and page numbers
- **Figure & Table Lists**: Scans the document for figures and tables, generates List of Figures and List of Tables with captions and page references
- **Bibliography Formatting**: Formats the bibliography section according to the university's required citation style; integrates with BibTeX for reference management
- **Page Number Management**: Handles the complex page numbering scheme (Roman numerals for front matter, Arabic for main content, appendix numbering)
- **Format Validation**: Checks the document against university requirements and flags violations (wrong margins, incorrect fonts, missing required sections, improper heading formatting)

## Tech Stack

- **Document Processing**: python-docx for reading and manipulating Word documents (.docx)
- **Bibliography**: citeproc-py for citation formatting; bibtexparser for BibTeX file handling
- **PDF**: docx2pdf for converting formatted thesis to PDF; PyMuPDF for PDF validation
- **Database**: SQLite for university formatting profiles, validation rules, and formatting history
- **UI**: Streamlit with document upload, format preview, and validation report
- **LLM**: MLX local inference (optional) for auto-detecting section types and suggesting heading structures

## File Structure

```
~/OpenClaw/tools/thesis-formatter/
├── app.py                        # Streamlit thesis formatting interface
├── formatting/
│   ├── template_engine.py        # University template application
│   ├── styles_manager.py         # Word style definitions per university
│   ├── page_numbering.py         # Front matter / main body page numbering
│   └── margins_fonts.py          # Margin and font enforcement
├── generation/
│   ├── toc_generator.py          # Table of Contents generation
│   ├── list_of_figures.py        # List of Figures generation
│   ├── list_of_tables.py         # List of Tables generation
│   └── front_matter.py           # Title page, abstract, declaration generation
├── bibliography/
│   ├── bib_formatter.py          # Bibliography section formatting
│   ├── bibtex_handler.py         # BibTeX file parsing and integration
│   └── citation_inserter.py      # In-text citation formatting
├── validation/
│   ├── format_checker.py         # Document format validation against university rules
│   ├── completeness_checker.py   # Required sections presence check
│   └── report_generator.py       # Validation report generation
├── profiles/
│   ├── hku.json                  # HKU thesis formatting rules
│   ├── cuhk.json                 # CUHK thesis formatting rules
│   ├── hkust.json                # HKUST thesis formatting rules
│   ├── polyu.json                # PolyU thesis formatting rules
│   ├── cityu.json                # CityU thesis formatting rules
│   └── generic.json              # Generic fallback profile
├── data/
│   └── formatter.db              # SQLite database
├── requirements.txt
└── README.md
```

## Key Integrations

- **python-docx**: Core library for all Word document manipulation
- **BibTeX**: Import references from .bib files for bibliography formatting
- **PDF Conversion**: docx2pdf for final PDF output (many universities require PDF submission)
- **Local LLM (MLX)**: Optional — for auto-detecting section types in unformatted documents

## HK-Specific Requirements

- HKU thesis format: 1.5 line spacing, 12pt Times New Roman, 25mm margins all sides, declaration page required, abstract in both English and Chinese, chapter numbering starts at Chapter 1
- CUHK thesis format: Double spacing for main text, 12pt font, left margin 38mm (for binding), other margins 25mm, approval page format specific to CUHK Graduate School
- HKUST thesis format: 1.5 or double spacing, 12pt, margins minimum 25mm, electronic submission format requirements
- PolyU thesis format: Specific PolyU logo placement on cover page, 1.5 line spacing, A4 paper, specific binding margin requirements
- CityU thesis format: CityU-specific cover page template, abstract format, and declaration format
- Common requirements across HK universities:
  - Front matter order: Cover page → Title page → Declaration → Abstract (EN) → Abstract (TC/SC) → Acknowledgments → TOC → List of Figures → List of Tables
  - Bilingual abstracts: Most HK universities require both English and Chinese abstracts
  - Page numbering: Roman numerals (i, ii, iii...) for front matter, Arabic (1, 2, 3...) from Chapter 1 onwards
  - Appendix formatting: Appendices use letter numbering (A, B, C) with sub-numbering (A.1, A.2)
- Thesis language: Most HK theses are in English, but Chinese-medium programmes exist — support both

## Data Model

```sql
CREATE TABLE formatting_profiles (
    id INTEGER PRIMARY KEY,
    university TEXT NOT NULL,
    degree_level TEXT CHECK(degree_level IN ('undergraduate','mphil','phd')),
    font_name TEXT DEFAULT 'Times New Roman',
    font_size INTEGER DEFAULT 12,
    line_spacing REAL DEFAULT 1.5,
    margin_top REAL DEFAULT 25,
    margin_bottom REAL DEFAULT 25,
    margin_left REAL DEFAULT 25,
    margin_right REAL DEFAULT 25,
    page_size TEXT DEFAULT 'A4',
    front_matter_numbering TEXT DEFAULT 'roman',
    main_body_numbering TEXT DEFAULT 'arabic',
    required_sections TEXT,  -- JSON array of required section types
    heading_styles TEXT,     -- JSON: per-level heading format definitions
    notes TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE thesis_projects (
    id INTEGER PRIMARY KEY,
    title TEXT,
    author TEXT,
    university TEXT,
    department TEXT,
    degree TEXT,
    supervisor TEXT,
    year INTEGER,
    profile_id INTEGER REFERENCES formatting_profiles(id),
    source_file TEXT,
    formatted_file TEXT,
    validation_status TEXT DEFAULT 'not_validated',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE validation_results (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES thesis_projects(id),
    check_type TEXT,
    passed BOOLEAN,
    message TEXT,
    location TEXT,
    severity TEXT CHECK(severity IN ('error','warning','info')),
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sections (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES thesis_projects(id),
    section_type TEXT CHECK(section_type IN ('cover','title','declaration','abstract_en','abstract_tc','acknowledgments','toc','lof','lot','chapter','appendix','bibliography')),
    section_title TEXT,
    page_start INTEGER,
    page_end INTEGER,
    status TEXT DEFAULT 'detected'
);
```

## Testing Criteria

- [ ] Applies HKU formatting profile with correct margins (25mm), font (Times New Roman 12pt), and 1.5 line spacing
- [ ] Generates Table of Contents with correct heading levels and page numbers for a 5-chapter thesis
- [ ] List of Figures correctly identifies all figures with captions and page references
- [ ] Page numbering transitions from Roman numerals (front matter) to Arabic (Chapter 1) correctly
- [ ] Bibliography formats 20 references in APA style from a BibTeX file
- [ ] Format validator detects incorrect left margin (20mm instead of required 25mm) and reports as error
- [ ] PDF conversion produces a valid PDF from the formatted .docx

## Implementation Notes

- python-docx is the core dependency — understand its limitations: it cannot read/modify all Word formatting (e.g., complex headers/footers may need workarounds); test thoroughly with real thesis documents
- University profiles: maintain as JSON files that can be updated independently; include a version number so changes can be tracked
- TOC generation: python-docx can insert TOC field codes, but the actual page numbers are populated when the document is opened in Word — document this behavior for users
- Page numbering with section breaks: use python-docx to insert section breaks between front matter and main content, with different header/footer configurations per section
- Bilingual abstract handling: detect language and apply correct formatting (Chinese abstract may need different font: SimSun or MingLiU for Traditional Chinese)
- Format validation: check margins via section properties, font via run properties, spacing via paragraph properties — generate a detailed report with line-by-line findings
- Memory budget: ~2GB without LLM; ~5GB with LLM for auto-detection features; recommend running without LLM for pure formatting tasks
- Consider adding a "format from scratch" mode that takes a plain text/markdown thesis and generates a fully formatted .docx from scratch, vs "fix existing" mode that adjusts formatting of an existing .docx
- Testing approach: include sample thesis documents (anonymized) for each supported university to validate formatting profiles
