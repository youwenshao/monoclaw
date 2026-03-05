# StudyBuddy

## Overview

StudyBuddy is a privacy-first local document Q&A system for university students that indexes course materials (PDFs, lecture slides, readings, notes) and answers study questions using RAG (Retrieval-Augmented Generation) with ChromaDB and a local LLM. All processing happens on-device — no course materials or queries are ever sent to cloud services, making it safe for use with copyrighted textbooks and exam prep materials.

## Target User

University students in Hong Kong (undergraduate and postgraduate) who accumulate large volumes of course materials across multiple subjects and need an efficient way to search, review, and study from their personal document collection.

## Core Features

- **Document Ingestion**: Import PDFs (textbooks, papers), PowerPoint slides (.pptx), Word documents (.docx), and plain text files; extract and index content with section/page awareness
- **Natural Language Q&A**: Ask study questions in English or Chinese and receive answers synthesized from indexed course materials with page-level citations
- **Course Organization**: Organize materials by semester, course code, and topic; search within a specific course or across the entire library
- **Flashcard Generation**: Automatically generates Q&A flashcards from indexed materials for spaced repetition study; exports to Anki-compatible format
- **Summary Generation**: Produces chapter/lecture summaries from indexed content at configurable detail levels (brief overview, detailed summary, key concepts only)
- **Exam Prep Mode**: Given past exam papers (PDFs), identifies which topics are covered and retrieves relevant material from indexed courses for targeted revision

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Vector DB | ChromaDB for embedding storage and semantic retrieval |
| Embeddings | sentence-transformers (multilingual model for EN/TC support) |
| LLM | MLX local inference (Qwen-2.5-7B quantized to 4-bit) for Q&A, summarization, and flashcard generation |
| Document Parsing | PyMuPDF for PDFs, python-pptx for slides, python-docx for Word files |
| Database | SQLite for document metadata, course organization, flashcard decks, and study history |
| UI | Streamlit with search interface, document browser, and flashcard review mode |
| Export | genanki for Anki flashcard export |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/study-buddy/
├── app.py                        # Streamlit study interface
├── ingestion/
│   ├── pdf_parser.py             # PDF text extraction with page tracking
│   ├── pptx_parser.py            # PowerPoint slide content extraction
│   ├── docx_parser.py            # Word document parsing
│   ├── chunker.py                # Content chunking for vector indexing
│   └── batch_importer.py         # Bulk document import by course folder
├── indexing/
│   ├── embedder.py               # Sentence-transformer embedding generation
│   ├── chroma_store.py           # ChromaDB index management
│   └── course_organizer.py       # Course-level index partitioning
├── retrieval/
│   ├── qa_engine.py              # RAG Q&A pipeline
│   ├── search_engine.py          # Semantic + keyword hybrid search
│   └── citation_tracker.py       # Source tracking for answer citations
├── study/
│   ├── flashcard_generator.py    # Auto-generate flashcards from materials
│   ├── summary_generator.py      # Chapter/lecture summary generation
│   ├── exam_prep.py              # Past paper analysis and topic mapping
│   └── anki_exporter.py          # Export flashcards to Anki format
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # QA, summary, and flashcard generation prompts
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/study-buddy/
├── studybuddy.db                 # SQLite database
├── chroma_db/                    # ChromaDB vector store
└── imports/                      # Imported course documents
```

## Key Integrations

- **ChromaDB**: Local vector database — no cloud dependency; data stays on the student's machine
- **Local LLM (MLX)**: All Q&A and generation runs on-device for complete privacy
- **Anki**: Export flashcards in .apkg format compatible with the popular Anki spaced repetition app
- **ExamGenerator (sibling tool)**: Shares the ChromaDB index and course database. ExamGenerator generates practice exam questions from the same indexed content. Exam performance data feeds back into StudyBuddy's flashcard generation — weak topics identified by exam results get prioritized in spaced repetition.
- **Telegram Bot API**: Secondary channel for study reminders, interview notifications, and deadline alerts.

## GUI Specification

Part of the **Student Dashboard** (`http://mona.local:8507`) — StudyBuddy tab.

### Views

- **Course Organizer**: Hierarchical browser showing semester → course → topic structure. Add courses, organize materials by topic.
- **Document Uploader**: Drag-drop area for PDFs, .pptx, .docx files. Batch import from course folders. Progress indicators for indexing.
- **Semantic Search**: Search bar with course/topic scope filters. Results show relevant passages with page-level citations. Click to view in context.
- **Q&A Chat**: RAG-powered chat with streaming responses. Inline citations link to source documents. "Show Sources" panel for verification.
- **Flashcard Review Mode**: Spaced repetition flashcards with flip animation. Difficulty rating (easy/medium/hard) after each card. Progress bar and streak counter.
- **Summary Viewer**: Chapter and lecture summaries at configurable detail levels (brief overview, detailed, key concepts only). Generate on demand.

### Mona Integration

- Mona auto-indexes documents added to watched course folders.
- Mona generates flashcards from newly indexed materials, prioritizing topics where exam performance is weak.
- Human studies, reviews materials, and rates flashcard difficulty.

### Manual Mode

- Student can manually upload documents, search materials, use flashcards, and generate summaries without Mona.

## HK-Specific Requirements

- Bilingual materials: HK university courses often use English-language textbooks but Chinese-language supplementary materials and lecture notes — the system must handle both seamlessly in the same index
- Course code format: HK universities use specific course code formats (e.g., COMP3001, ECON2220, LAWS3000) — support these as organizing categories
- Academic integrity: The tool is for personal study use with the student's own materials — include a disclaimer about not using it for plagiarism or submitting AI-generated answers as coursework
- Traditional Chinese preference: HK students use Traditional Chinese; answers should be in Traditional Chinese when the question is in Chinese
- Common file formats: HK professors commonly distribute materials as .pdf (scanned textbook chapters), .pptx (lecture slides), and .docx (tutorial worksheets) — all must be supported
- Large class sizes: HK university courses often have 200+ students and 12+ weeks of material per course — the system must handle substantial document volumes

## Data Model

```sql
CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    course_code TEXT,
    course_name TEXT,
    semester TEXT,
    instructor TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    filename TEXT,
    file_path TEXT,
    doc_type TEXT CHECK(doc_type IN ('pdf','pptx','docx','txt','md')),
    title TEXT,
    page_count INTEGER,
    chunk_count INTEGER,
    language TEXT,
    indexed BOOLEAN DEFAULT FALSE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    chunk_index INTEGER,
    text_content TEXT,
    page_number INTEGER,
    section_title TEXT,
    chroma_id TEXT
);

CREATE TABLE queries (
    id INTEGER PRIMARY KEY,
    query_text TEXT,
    course_id INTEGER,
    answer_text TEXT,
    cited_chunks TEXT,  -- JSON array of chunk IDs
    helpful BOOLEAN,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE flashcards (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    document_id INTEGER REFERENCES documents(id),
    question TEXT,
    answer TEXT,
    difficulty TEXT CHECK(difficulty IN ('easy','medium','hard')) DEFAULT 'medium',
    review_count INTEGER DEFAULT 0,
    last_reviewed TIMESTAMP,
    next_review TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Student Profile**: Name, university, programme, year of study, expected graduation date
2. **Messaging Setup**: Twilio API credentials for WhatsApp, Telegram bot token (for study reminders and deadline alerts)
3. **Course Setup**: Add current semester courses with course codes, names, and topics
4. **Document Library**: Import existing course materials from folders or start fresh
5. **Sample Data**: Option to seed demo courses, sample documents, and flashcards for testing
6. **Connection Test**: Validates all API connections, ChromaDB status, and embedding model availability

## Testing Criteria

- [ ] Ingests a 50-page PDF textbook chapter and creates searchable chunks with correct page references
- [ ] Q&A correctly answers a factual question from indexed materials with the correct page citation
- [ ] Handles a Chinese-language question about English-language source material (cross-lingual Q&A)
- [ ] Flashcard generator produces 10 relevant Q&A pairs from a single lecture's slides
- [ ] Anki export creates a valid .apkg file importable into Anki desktop
- [ ] Course-scoped search returns results only from the specified course's materials
- [ ] Processes and indexes 500 pages of material within 15 minutes on M4/16GB hardware

## Implementation Notes

- Embedding model: use paraphrase-multilingual-MiniLM-L12-v2 for bilingual (EN/TC) embedding support; fits in ~500MB RAM
- Chunking for slides: each slide becomes one chunk (natural content boundary); for PDFs, use 500-token chunks with section awareness
- ChromaDB: use persistent mode with course-level collections for efficient scoped searches; metadata filtering by course_code. The `~/OpenClawWorkspace/study-buddy/chroma_db/` directory is shared with ExamGenerator via symlink — StudyBuddy is the sole writer; ExamGenerator reads only.
- Q&A pipeline: retrieve top 8 chunks → pass to LLM with "answer based only on the provided context" instruction → generate answer with citations
- Flashcard generation: for each document section, prompt the LLM to generate 3-5 question-answer pairs covering key concepts; tag with difficulty based on Bloom's taxonomy level
- Exam prep: OCR past papers if scanned (Tesseract), extract questions, classify by topic, then retrieve relevant indexed material per topic
- Memory budget: ~7GB (embedding model + LLM + ChromaDB + application); tight on 16GB — advise students to close other LLM tools when using StudyBuddy intensively
- Consider implementing a "study session" mode with a Pomodoro timer and integrated flashcard reviews between study blocks
- **Logging**: All operations logged to `/var/log/openclaw/study-buddy.log` with daily rotation (7-day retention). Student personal data and academic content masked in log output.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Course materials (copyrighted textbooks, exam papers) processed locally only — zero cloud processing.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM/embedding model state, and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON + files archive of all study data, flashcards, job applications, and exam attempts.
