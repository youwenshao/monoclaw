# Academic Dashboard

Unified FastAPI application providing four research productivity tools for Hong Kong academics, accessible at `http://mona.local:8509`.

## Tools

| Tool | Purpose |
|------|---------|
| **PaperSieve** | PDF ingestion, ChromaDB indexing, semantic search, QA chat, knowledge graph, and systematic review workflow |
| **CiteBot** | Citation parsing (BibTeX, RIS, DOI), style formatting (APA, Harvard, IEEE, GB/T 7714), validation, and export |
| **TranslateAssist** | Domain-aware translation (TC/EN), glossary management, terminology enforcement, and translation memory |
| **GrantTracker** | RGC, ITF, NSFC deadline monitoring, application checklists, budget builder, and reminder notifications |

## Quick Start

### Prerequisites

- Python 3.11+
- ChromaDB (for PaperSieve vector store)

### Installation

```bash
cd tools/09-academic
pip install -e ../shared
pip install -e .
```

### Running the Dashboard

```bash
python -m academic.app
# Or: uvicorn academic.app:app --host 0.0.0.0 --port 8509
```

Then open **http://localhost:8509**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### PaperSieve

Ingest PDFs, chunk with overlap, and index in ChromaDB. Semantic search, QA chat with citations, concept extraction, knowledge graph, and systematic review screening. Supports PDF, PPTX, DOCX parsing.

### CiteBot

Parse citations from text, BibTeX, RIS. Resolve DOIs via CrossRef. Format to APA7, Harvard, IEEE, GB/T 7714. Validate completeness, check duplicates, and export to bibliography.

### TranslateAssist

Translate abstracts and full papers with domain prompts (general, medical, legal, etc.). Glossary manager for consistent terminology. Chinese converter (TC/SC), segmenter, and translation memory.

### GrantTracker

Monitor RGC, ITF, NSFC deadlines. Application board with form autofill, checklist generator, budget builder. Researcher profile with ORCID and Google Scholar. Reminder engine with configurable intervals.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `extra` | `chroma_collection` | PaperSieve ChromaDB collection name |
| `extra` | `default_citation_style` | CiteBot default (apa7, harvard, ieee, gbt7714) |
| `extra` | `default_source_language` | TranslateAssist (tc, sc, en) |
| `extra` | `grant_schemes` | RGC, ITF, NSFC |
| `extra` | `institutional_deadline_offset_days` | Days before external deadline |

## Architecture

```
tools/09-academic/
├── config.yaml
├── academic/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── paper_sieve/
│   ├── cite_bot/
│   ├── translate_assist/
│   └── grant_tracker/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/academic/`): `paper_sieve.db`, `cite_bot.db`, `translate_assist.db`, `grant_tracker.db`, `shared.db`, `mona_events.db`. PaperSieve also uses ChromaDB for vector storage.

## Running Tests

```bash
cd tools/09-academic
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/academic_tools_implementation_fbafb453.plan.md`
- **Shared Library**: `tools/shared/`
