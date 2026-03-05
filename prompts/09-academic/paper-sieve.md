# PaperSieve

## Overview

PaperSieve is a local RAG (Retrieval-Augmented Generation) system for academic researchers that indexes research papers, answers research questions with precise citations, and supports systematic literature review workflows. It uses ChromaDB for vector storage and MLX for local LLM inference, ensuring that unpublished research materials and proprietary datasets never leave the researcher's machine.

## Target User

Academic researchers, PhD students, and postdoctoral fellows at Hong Kong universities (HKU, CUHK, HKUST, PolyU, CityU, HKBU, LingU, EdUHK) who need to efficiently review large volumes of academic literature, extract key findings, and maintain organized research knowledge bases.

## Core Features

- **Paper Ingestion**: Imports PDFs of academic papers, extracts text with layout-aware parsing (handling two-column formats, figures, tables, references), and chunks content for vector indexing
- **Semantic Search**: Natural language queries against the paper corpus return relevant passages with exact paper citations (author, year, page number)
- **Question Answering**: Ask research questions and receive synthesized answers grounded in the indexed papers, with inline citations and confidence indicators
- **Systematic Review Workflow**: Guided workflow for PRISMA-style systematic reviews — screening, inclusion/exclusion criteria application, data extraction templates, and quality assessment checklists
- **Knowledge Graph**: Auto-extracts key concepts, relationships, and findings to build a visual knowledge graph across the paper corpus
- **Citation Network**: Maps citation relationships between indexed papers to identify seminal works, research clusters, and emerging topics

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Vector DB | ChromaDB for embedding storage and similarity search |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2 or multilingual equivalent) for text embedding |
| LLM | MLX local inference (Qwen-2.5-7B or Llama-3-8B quantized) for question answering and synthesis |
| PDF Parsing | PyMuPDF (fitz) for layout-aware PDF text extraction; pdfplumber as fallback |
| Database | SQLite for paper metadata, tags, review status, and extraction records |
| UI | Streamlit with search interface, paper viewer, and knowledge graph visualization |
| Visualization | pyvis or networkx + plotly for knowledge graph and citation network rendering |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/paper-sieve/
├── app.py                       # Streamlit research interface
├── ingestion/
│   ├── pdf_parser.py            # Layout-aware PDF text extraction
│   ├── chunker.py               # Intelligent text chunking (section-aware)
│   ├── metadata_extractor.py    # Title, authors, abstract, DOI extraction
│   └── reference_parser.py      # Bibliography/reference section parsing
├── indexing/
│   ├── embedder.py              # Sentence-transformer embedding generation
│   ├── chroma_store.py          # ChromaDB indexing and retrieval
│   └── index_manager.py         # Index lifecycle (create, update, delete)
├── retrieval/
│   ├── search_engine.py         # Semantic search with citation tracking
│   ├── qa_engine.py             # RAG question answering pipeline
│   └── synthesis.py             # Multi-paper synthesis and summarization
├── review/
│   ├── systematic_review.py     # PRISMA workflow management
│   ├── screening.py             # Inclusion/exclusion screening tools
│   └── data_extraction.py       # Structured data extraction templates
├── knowledge/
│   ├── concept_extractor.py     # Key concept and relationship extraction
│   ├── knowledge_graph.py       # Knowledge graph construction and visualization
│   └── citation_network.py      # Citation relationship mapping
├── models/
│   ├── llm_handler.py           # MLX inference wrapper
│   └── prompts.py               # QA, synthesis, and extraction prompts
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/paper-sieve/
├── papersieve.db                # SQLite metadata database
├── chroma_db/                   # ChromaDB vector store directory
└── papers/                      # Imported PDF papers
```

## Key Integrations

- **ChromaDB**: Local vector database for embedding storage — no cloud vector DB dependency
- **Local LLM (MLX)**: All question answering and synthesis runs on-device
- **DOI.org**: Fetches paper metadata from DOI when available for automatic cataloging
- **Semantic Scholar API** (optional): Enriches paper metadata and citation data from Semantic Scholar's open API
- **Telegram Bot API**: Secondary channel for deadline reminders, paper alerts, and translation notifications.

## GUI Specification

Part of the **Academic Dashboard** (`http://mona.local:8505`) — PaperSieve tab.

### Views

- **Paper Library Browser**: Searchable list of all indexed papers with tag filters, year range, journal, and sort options (relevance, date, citation count).
- **Semantic Search**: Full-text search with highlighted passage results and exact citations (author, year, page). Click any result to jump to the source passage.
- **Q&A Chat**: RAG-powered chat interface with inline citations that link directly to source passages. Streaming LLM responses with "Show Sources" expandable panel.
- **Knowledge Graph**: Interactive node-and-edge visualization of concepts, relationships, and findings across the paper corpus. Zoomable, clickable nodes link to source papers.
- **Systematic Review Workflow**: PRISMA flow diagram, paper screening interface (include/exclude with reason), and structured data extraction forms.
- **Citation Network**: Visual map of citation relationships between indexed papers to identify seminal works and research clusters.

### Mona Integration

- Mona auto-indexes new papers added to the watched folder and updates the knowledge graph.
- Mona synthesizes multi-paper answers with proper citations in the Q&A chat.
- Human curates the library, conducts systematic reviews, and verifies Mona's synthesis quality.

### Manual Mode

- Researcher can manually add papers, search the corpus, browse the knowledge graph, and manage systematic reviews without Mona.

## HK-Specific Requirements

- Bilingual paper support: Many HK researchers publish in both English and Chinese; the system must handle Traditional Chinese academic papers, including Chinese journal citation formats
- University research repository integration: Stub connectors for HKU Scholars Hub, CUHK Research Portal, and HKUST Institutional Repository for direct paper import
- RGC (Research Grants Council) reporting: Extracted findings and citation counts can feed into RGC progress reports and RAE (Research Assessment Exercise) submissions
- Chinese academic citation formats: Support GB/T 7714 citation format used in Chinese academic publishing alongside Western formats (APA, Harvard, IEEE)
- Multilingual embeddings: Use a multilingual sentence-transformer model to handle papers mixing English and Chinese text
- Research ethics: Papers involving human subjects should be flagged if they mention IRB/ethics approval — useful for systematic reviews assessing study quality

## Data Model

```sql
CREATE TABLE papers (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT,  -- JSON array of author names
    abstract TEXT,
    doi TEXT UNIQUE,
    year INTEGER,
    journal TEXT,
    volume TEXT,
    pages TEXT,
    language TEXT DEFAULT 'en',
    file_path TEXT,
    total_pages INTEGER,
    chunk_count INTEGER,
    indexed BOOLEAN DEFAULT FALSE,
    tags TEXT,  -- JSON array
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(id),
    chunk_index INTEGER,
    section_name TEXT,
    text_content TEXT,
    page_number INTEGER,
    chroma_id TEXT,
    token_count INTEGER
);

CREATE TABLE queries (
    id INTEGER PRIMARY KEY,
    query_text TEXT,
    answer_text TEXT,
    cited_chunks TEXT,  -- JSON array of chunk IDs
    confidence REAL,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE systematic_reviews (
    id INTEGER PRIMARY KEY,
    review_name TEXT,
    research_question TEXT,
    inclusion_criteria TEXT,
    exclusion_criteria TEXT,
    status TEXT DEFAULT 'screening',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_papers (
    id INTEGER PRIMARY KEY,
    review_id INTEGER REFERENCES systematic_reviews(id),
    paper_id INTEGER REFERENCES papers(id),
    screening_status TEXT CHECK(screening_status IN ('pending','included','excluded','maybe')),
    exclusion_reason TEXT,
    quality_score REAL,
    extracted_data TEXT  -- JSON
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Researcher Profile**: Name, university affiliation, department, research areas
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token
3. **Paper Library**: Import existing papers from a folder or Zotero export; configure watched folders for auto-indexing
4. **Embedding Model**: Select embedding model (multilingual recommended for EN+ZH papers)
5. **Citation Preferences**: Default citation style for Q&A output
6. **Language Settings**: Primary and secondary research languages for multilingual indexing
7. **Sample Data**: Option to seed demo papers for testing the search and review workflows
8. **Connection Test**: Validates ChromaDB, embedding model, LLM, and reports any issues

## Testing Criteria

- [ ] Ingests a 20-page academic PDF and extracts text with correct section segmentation
- [ ] Semantic search for a concept returns the top 5 most relevant passages with correct paper citations
- [ ] QA engine answers a research question by synthesizing information from 3+ papers with inline citations
- [ ] Handles a Chinese-language academic paper with correct text extraction and embedding
- [ ] Systematic review workflow correctly applies inclusion/exclusion criteria to screen 50 papers
- [ ] Knowledge graph displays concept relationships extracted from 10+ indexed papers
- [ ] Processes and indexes 100 papers within 30 minutes on M4/16GB hardware

## Implementation Notes

- PDF parsing: PyMuPDF handles most academic PDFs well; use section heading detection (font size + bold) to create section-aware chunks rather than fixed-size chunks
- Chunking strategy: aim for ~500 token chunks with 50 token overlap; respect paragraph boundaries; keep title/author metadata as chunk metadata for citation generation
- ChromaDB: use persistent storage mode (not in-memory) to survive application restarts; embed with a multilingual model (e.g., paraphrase-multilingual-MiniLM-L12-v2) for bilingual support
- RAG pipeline: retrieve top 10 chunks → re-rank with cross-encoder or LLM → pass top 5 to LLM for answer generation with instruction to cite sources
- Memory budget: embedding model (~500MB) + LLM 4-bit (~4GB) + ChromaDB + application = ~7GB; tight on 16GB but feasible if other tools are not running simultaneously
- For large paper collections (500+), consider batch embedding overnight rather than real-time indexing
- Citation tracking: each answer must include `[Author, Year, p.XX]` style citations that the user can click to jump to the source passage
- **Logging**: All operations logged to `/var/log/openclaw/paper-sieve.log` with daily rotation (7-day retention). Paper titles and researcher details masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Research materials (unpublished papers, grant proposals) are sensitive — zero cloud processing.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/embedding model state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all papers, citations, translations, and grant data.
