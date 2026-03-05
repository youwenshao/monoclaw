# TranslateAssist

## Overview

TranslateAssist is a specialized academic translation tool that translates research papers and scholarly text between Chinese and English while preserving technical terminology, academic tone, and field-specific conventions. Unlike generic translation tools, it uses domain-aware prompting with the local LLM to maintain accuracy for discipline-specific terms and handles both Traditional and Simplified Chinese with awareness of academic publishing norms in each context.

## Target User

Hong Kong academic researchers, graduate students, and research staff who need to translate abstracts, papers, grant proposals, or correspondence between Chinese and English for publication in international or Chinese-language journals.

## Core Features

- **Domain-Aware Translation**: Discipline-specific translation with pre-loaded terminology glossaries for STEM, social sciences, humanities, medicine, law, and business
- **Abstract Translation**: Specialized workflow for translating paper abstracts — the most common academic translation need — with automatic adherence to journal style guidelines
- **Full Paper Translation**: Section-by-section translation of complete papers preserving heading structure, figure/table references, and citation markers
- **Terminology Consistency**: Maintains a per-project glossary to ensure the same English term maps to the same Chinese term throughout a document
- **Traditional/Simplified Toggle**: Translates to Traditional Chinese (HK/Taiwan academic convention) or Simplified Chinese (Mainland convention) with appropriate academic vocabulary for each
- **Review Mode**: Side-by-side original and translated text with inline comments on translation choices for difficult passages

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM | MLX local inference (Qwen-2.5-7B — excellent bilingual Chinese-English capability) |
| Text Processing | python-docx for Word document input/output; PyMuPDF for PDF text extraction |
| Terminology | SQLite-backed glossary database with per-discipline term mappings |
| Chinese Processing | opencc for Traditional↔Simplified Chinese conversion; jieba for Chinese word segmentation |
| UI | Streamlit with side-by-side translation view and glossary management |
| Export | python-docx for Word output; HTML for web preview |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/translate-assist/
├── app.py                        # Streamlit translation interface
├── translation/
│   ├── translator.py             # Core translation engine using LLM
│   ├── domain_prompter.py        # Domain-specific prompt construction
│   ├── abstract_translator.py    # Specialized abstract translation workflow
│   └── paper_translator.py       # Full paper section-by-section translation
├── terminology/
│   ├── glossary_manager.py       # Terminology glossary CRUD
│   ├── term_enforcer.py          # Consistency enforcement across translation
│   └── domain_glossaries.py      # Pre-built discipline glossary loader
├── processing/
│   ├── document_parser.py        # PDF/DOCX text extraction with structure
│   ├── chinese_converter.py      # Traditional↔Simplified conversion (opencc)
│   └── segmenter.py              # Chinese word segmentation for terminology detection
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Translation prompts per domain
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/translate-assist/
├── translate.db                  # SQLite database
└── glossaries/                   # Domain-specific glossary files (JSON)
    ├── stem.json
    ├── social_science.json
    ├── medicine.json
    ├── law.json
    └── business.json
```

## Key Integrations

- **Local LLM (MLX)**: All translation runs locally — critical for unpublished research that must not be uploaded to cloud translation services
- **OpenCC**: Reliable Traditional↔Simplified Chinese conversion library
- **DOI.org** (optional): Look up published translations of paper titles for reference
- **Telegram Bot API**: Secondary channel for deadline reminders, paper alerts, and translation notifications.

## GUI Specification

Part of the **Academic Dashboard** (`http://mona.local:8505`) — TranslateAssist tab.

### Views

- **Side-by-Side Editor**: Source text on the left, translation on the right. Paragraph-aligned scrolling. Click any paragraph to focus on it.
- **Domain Glossary Panel**: Editable glossary of domain-specific terms auto-populated from the paper corpus. Add custom terms. Glossary entries highlighted in the translation.
- **Translation Memory**: Previously translated phrases shown as suggestions for consistency across documents. Accept or override.
- **Quality Indicators**: Per-paragraph confidence score for machine translation. Low-confidence paragraphs highlighted for human review.
- **Language Pair Selector**: Switch between EN↔TC (Traditional Chinese), EN↔SC (Simplified Chinese), and TC↔SC.

### Mona Integration

- Mona auto-translates uploaded documents paragraph by paragraph, populating the right pane.
- Mona learns from human corrections to improve domain-specific translation quality.
- Human reviews and corrects translations, especially for domain terminology.

### Manual Mode

- Researcher can manually input text, manage the glossary, review translations, and export results without Mona.

## HK-Specific Requirements

- Traditional Chinese as default: HK academic writing uses Traditional Chinese (繁體中文); Simplified Chinese output should be opt-in for Mainland journal submissions
- Academic Chinese conventions in HK: HK academic Chinese may use some vocabulary that differs from Mainland academic Chinese (e.g., "資訊" vs "信息" for "information", "軟件" vs "软件" for "software")
- Bilingual abstracts: Many HK university theses require both English and Chinese abstracts — tool should support paired abstract generation
- Common translation directions: Chinese→English (for international journal submission) is the primary use case; English→Chinese (for Chinese journal submission or grant proposals to Mainland agencies like NSFC) is secondary
- HK university names: Standardized English names for HK universities should be used in translations (e.g., "香港大學" ↔ "The University of Hong Kong", not "University of Hong Kong")
- Research ethics terminology: Ethics committee/IRB approval terminology should be translated according to HK university conventions
- Grant proposal terminology: UGC/RGC-specific terms (研究資助局, 優配研究金, 傑出青年學者計劃) should have standardized English translations

## Data Model

```sql
CREATE TABLE translation_projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT,
    source_language TEXT CHECK(source_language IN ('en','tc','sc')),
    target_language TEXT CHECK(target_language IN ('en','tc','sc')),
    domain TEXT CHECK(domain IN ('stem','social_science','humanities','medicine','law','business','general')),
    source_file TEXT,
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE translation_segments (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES translation_projects(id),
    segment_index INTEGER,
    section_name TEXT,
    source_text TEXT,
    translated_text TEXT,
    review_status TEXT CHECK(review_status IN ('auto','reviewed','approved')) DEFAULT 'auto',
    reviewer_notes TEXT,
    translated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE glossary_terms (
    id INTEGER PRIMARY KEY,
    term_en TEXT,
    term_tc TEXT,
    term_sc TEXT,
    domain TEXT,
    definition TEXT,
    source TEXT,
    project_specific BOOLEAN DEFAULT FALSE,
    project_id INTEGER REFERENCES translation_projects(id)
);

CREATE TABLE translation_memory (
    id INTEGER PRIMARY KEY,
    source_text TEXT,
    source_language TEXT,
    translated_text TEXT,
    target_language TEXT,
    domain TEXT,
    quality_score REAL,
    used_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Researcher Profile**: Name, university affiliation, department, research areas
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **Language Settings**: Primary and secondary research languages, default translation direction (EN↔TC, EN↔SC, TC↔SC)
4. **Domain Selection**: Choose research domain(s) for terminology glossaries (STEM, social sciences, medicine, law, business)
5. **Glossary Import**: Import custom glossary terms or use pre-built domain glossaries
6. **Sample Data**: Option to seed demo translation projects for testing
7. **Connection Test**: Validates LLM, OpenCC, and reports any issues

## Testing Criteria

- [ ] Correctly translates a STEM paper abstract from Chinese to English with appropriate technical terminology
- [ ] Maintains terminology consistency — same Chinese term maps to the same English term throughout a 5-page document
- [ ] Traditional↔Simplified Chinese conversion preserves academic vocabulary conventions for each region
- [ ] Domain glossary for medicine correctly maps "高血壓" → "hypertension" (not "high blood pressure") in academic context
- [ ] Full paper translation preserves heading structure, figure references (Figure 1/圖一), and citation markers [1,2,3]
- [ ] Side-by-side review mode correctly aligns source and translated paragraphs
- [ ] Translates a 3000-word abstract in under 2 minutes on M4/16GB hardware

## Implementation Notes

- Qwen-2.5-7B is the optimal model choice for Chinese↔English academic translation due to its strong bilingual performance — quantize to 4-bit for 16GB RAM
- Translation pipeline: extract text → segment into paragraphs → inject relevant glossary terms into prompt context → translate paragraph-by-paragraph → enforce terminology consistency in post-processing
- Terminology enforcement: before sending each paragraph to the LLM, prepend the relevant glossary terms as a "translation glossary" in the system prompt
- Translation memory: cache paragraph-level translations; for repeated or similar text (e.g., standard acknowledgment sections), retrieve from memory instead of re-translating
- Chinese word segmentation (jieba) is used to identify multi-character terms that should be looked up in the glossary before translation
- Memory budget: ~5GB (Qwen LLM + OpenCC + application); Translation is the most LLM-intensive task so minimize concurrent tool usage
- Paragraph-by-paragraph translation with context: include the previous paragraph's translation as context to maintain coherence across paragraph boundaries
- Consider adding a "polish" mode that takes an existing translation and improves fluency and academic tone without re-translating from scratch
- **Logging**: All operations logged to `/var/log/openclaw/translate-assist.log` with daily rotation (7-day retention). Paper titles and researcher details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Research materials (unpublished papers, grant proposals) are sensitive — zero cloud processing.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/embedding model state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all papers, citations, translations, and grant data.
