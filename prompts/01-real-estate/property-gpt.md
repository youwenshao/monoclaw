# PropertyGPT — HK Property Knowledge RAG System

## Overview

PropertyGPT is a fine-tuned Retrieval-Augmented Generation system built on a comprehensive Hong Kong building database. It enables real estate agents to instantly answer complex property queries, generate professional listing descriptions, and compare properties using semantic search over structured HK property data including floor areas, school nets, MTR walking distances, and building age.

## Target User

Hong Kong licensed estate agents (EAA holders) who handle 20-50 property inquiries daily and need instant access to building-level data, comparable listings, and auto-generated marketing copy in English and Traditional Chinese.

## Core Features

- **Semantic Property Search**: Natural language queries against a vector database of HK buildings. "3-bedroom near Quarry Bay MTR under 15M" returns ranked results with saleable area, age, and price history.
- **Auto-Answer Engine**: Feed WhatsApp client questions into the RAG pipeline and return structured answers with source citations. Handles queries about management fees, pet policies, building facilities, and school catchment.
- **Listing Description Generator**: Given property attributes (size, floor, view, condition), produce platform-ready descriptions in English and Traditional Chinese with SEO keywords for 28Hse, Squarefoot, and agent websites.
- **Comparable Analysis**: Select a property and get the 5 most similar recent transactions within the same district, adjusted for floor level, facing, and renovation status. Output as a formatted comparison table.
- **Floor Plan OCR**: Extract room dimensions and layout from floor plan images using macOS Vision framework. Auto-calculate saleable area breakdown by room.
- **Price Trend Briefing**: Daily digest of Land Registry transaction data for agent's focus districts, with month-on-month price movement summaries.

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM inference | `mlx-lm` with Qwen2.5-7B-Instruct (4-bit quantized) |
| Vector store | ChromaDB (persistent, on-disk) |
| Embeddings | `sentence-transformers` via MLX (`bge-base-zh-v1.5`) |
| OCR | macOS Vision framework via `pyobjc-framework-Vision` |
| Document parsing | `pdfplumber`, `python-docx` |
| Web scraping | `httpx`, `beautifulsoup4` |
| Data processing | `pandas`, `numpy` |
| API layer | `fastapi`, `uvicorn` |
| Database | `sqlite3` (stdlib) |
| WhatsApp | Twilio WhatsApp Business API |

## File Structure

```
/opt/openclaw/skills/local/property-gpt/
├── main.py                  # FastAPI app entry point
├── config.yaml              # Model paths, API keys, district config
├── rag/
│   ├── embedder.py          # MLX embedding pipeline
│   ├── retriever.py         # ChromaDB query layer
│   ├── generator.py         # LLM response generation
│   └── prompts/             # System prompts for each task
├── scrapers/
│   ├── land_registry.py     # Transaction data fetcher
│   ├── rating_valuation.py  # RVD rateable value data
│   └── building_db.py       # Building info aggregator
├── ocr/
│   └── floor_plan.py        # Vision framework floor plan parser
├── messaging/
│   └── whatsapp.py          # Twilio integration
└── tests/
    ├── test_rag.py
    ├── test_ocr.py
    └── test_scrapers.py

~/OpenClawWorkspace/property-gpt/
├── chroma_db/               # Persistent vector store
├── building_data/           # Cached building JSON files
├── exports/                 # Generated descriptions, reports
└── logs/
```

## Key Integrations

- **Land Registry (IRIS Online)**: Scrape recent transaction data for price comparisons
- **Rating and Valuation Department (RVD)**: Rateable values and building age data
- **Centadata / Midland Realty**: Market price references (public pages)
- **Twilio WhatsApp Business API**: Receive client questions, send formatted answers
- **28Hse / Squarefoot**: Target platforms for listing description output formats

## HK-Specific Requirements

- **Saleable vs Gross Floor Area**: Always distinguish saleable area (實用面積) from gross floor area (建築面積). Post-2013 regulations require saleable area as primary measure. Store and display both with clear labels.
- **School Net Zones**: Map properties to primary school net numbers (e.g., Net 11 = Central & Western). Include net number and popular schools in property summaries.
- **MTR Proximity Scoring**: Calculate walking time to nearest MTR station using straight-line distance with a 1.3x urban walk factor. Score: A (<5min), B (5-10min), C (10-15min), D (>15min).
- **Building Management Fees**: Include monthly management fee per square foot. Flag buildings with unusually high fees (>$5/sqft).
- **Stamp Duty Awareness**: Include ad valorem stamp duty tier in price comparisons. Flag non-permanent-resident surcharges (BSD 15%).
- **Bilingual Output**: All client-facing text must support Traditional Chinese (zh-HK) and English. Property names use official transliterations.

## Data Model

```sql
CREATE TABLE buildings (
    id INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    district TEXT NOT NULL,
    sub_district TEXT,
    address_en TEXT,
    address_zh TEXT,
    year_built INTEGER,
    total_floors INTEGER,
    total_units INTEGER,
    management_fee_psf REAL,
    school_net INTEGER,
    nearest_mtr TEXT,
    mtr_walk_minutes REAL,
    has_clubhouse BOOLEAN,
    pet_allowed BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY,
    building_id INTEGER REFERENCES buildings(id),
    flat TEXT,
    floor TEXT,
    saleable_area_sqft REAL,
    gross_area_sqft REAL,
    price_hkd INTEGER,
    price_psf_saleable REAL,
    transaction_date DATE,
    instrument_date DATE,
    source TEXT
);

CREATE TABLE query_log (
    id INTEGER PRIMARY KEY,
    user_phone TEXT,
    query_text TEXT,
    response_text TEXT,
    sources_cited TEXT,
    latency_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Semantic search returns relevant properties for natural language queries in both English and Chinese
- [ ] RAG answers cite specific buildings and transaction data, not hallucinated values
- [ ] Listing descriptions pass EAA compliance (include saleable area, no misleading claims)
- [ ] Floor plan OCR extracts room count and total area within 5% accuracy on test images
- [ ] Comparable analysis matches at least 3 recent transactions in the same estate/district
- [ ] WhatsApp round-trip (question → answer) completes within 8 seconds
- [ ] ChromaDB ingestion handles 50,000+ building records without exceeding 4GB RAM
- [ ] All monetary values display in HKD with proper formatting (e.g., $12,800,000)

## Implementation Notes

- **Memory budget**: Qwen2.5-7B 4-bit uses ~5GB VRAM. ChromaDB should stay under 2GB. Keep total process memory under 12GB to leave headroom for macOS.
- **Privacy**: All property queries and client phone numbers stay local. Never send client data to external APIs except Twilio for message delivery. Scrape only public data sources.
- **Embedding model**: Use `bge-base-zh-v1.5` for bilingual Chinese/English embeddings. Convert to MLX format for ARM64 acceleration.
- **Rate limiting**: Scraping Land Registry and RVD should respect robots.txt and use 2-second delays between requests. Cache aggressively — building data changes infrequently.
- **Startup**: Pre-load the LLM and embedding model on application start. Use lazy loading for ChromaDB collections to reduce cold start time.
- **Error handling**: If LLM inference fails (OOM), fall back to template-based responses for common query types. Log all failures to `/var/log/openclaw/property-gpt.log`.
