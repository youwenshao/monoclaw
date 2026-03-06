"""Database schema initialization for all Academic Dashboard tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# PaperSieve
# ---------------------------------------------------------------------------
PAPER_SIEVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    authors TEXT,
    abstract TEXT,
    doi TEXT UNIQUE,
    year INTEGER,
    journal TEXT,
    volume TEXT,
    pages TEXT,
    language TEXT DEFAULT 'en',
    file_path TEXT,
    total_pages INTEGER,
    chunk_count INTEGER DEFAULT 0,
    indexed BOOLEAN DEFAULT FALSE,
    tags TEXT,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER REFERENCES papers(id),
    chunk_index INTEGER,
    section_name TEXT,
    text_content TEXT,
    page_number INTEGER,
    chroma_id TEXT,
    token_count INTEGER
);

CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT,
    answer_text TEXT,
    cited_chunks TEXT,
    confidence REAL,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS systematic_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_name TEXT,
    research_question TEXT,
    inclusion_criteria TEXT,
    exclusion_criteria TEXT,
    status TEXT DEFAULT 'screening',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER REFERENCES systematic_reviews(id),
    paper_id INTEGER REFERENCES papers(id),
    screening_status TEXT CHECK(screening_status IN ('pending','included','excluded','maybe')),
    exclusion_reason TEXT,
    quality_score REAL,
    extracted_data TEXT
);
"""

# ---------------------------------------------------------------------------
# CiteBot
# ---------------------------------------------------------------------------
CITE_BOT_SCHEMA = """
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi TEXT,
    title TEXT,
    authors TEXT,
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

CREATE TABLE IF NOT EXISTS formatted_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citation_id INTEGER REFERENCES citations(id),
    style TEXT NOT NULL,
    formatted_text TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bibliography_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    default_style TEXT DEFAULT 'apa7',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES bibliography_projects(id),
    citation_id INTEGER REFERENCES citations(id),
    sort_order INTEGER,
    in_text_key TEXT,
    notes TEXT
);
"""

# ---------------------------------------------------------------------------
# TranslateAssist
# ---------------------------------------------------------------------------
TRANSLATE_ASSIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS translation_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT,
    source_language TEXT CHECK(source_language IN ('en','tc','sc')),
    target_language TEXT CHECK(target_language IN ('en','tc','sc')),
    domain TEXT CHECK(domain IN ('stem','social_science','humanities','medicine','law','business','general')),
    source_file TEXT,
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS translation_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES translation_projects(id),
    segment_index INTEGER,
    section_name TEXT,
    source_text TEXT,
    translated_text TEXT,
    review_status TEXT CHECK(review_status IN ('auto','reviewed','approved')) DEFAULT 'auto',
    reviewer_notes TEXT,
    confidence REAL,
    translated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_en TEXT,
    term_tc TEXT,
    term_sc TEXT,
    domain TEXT,
    definition TEXT,
    source TEXT,
    project_specific BOOLEAN DEFAULT FALSE,
    project_id INTEGER REFERENCES translation_projects(id)
);

CREATE TABLE IF NOT EXISTS translation_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_text TEXT,
    source_language TEXT,
    translated_text TEXT,
    target_language TEXT,
    domain TEXT,
    quality_score REAL,
    used_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# GrantTracker
# ---------------------------------------------------------------------------
GRANT_TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS researchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    title TEXT,
    department TEXT,
    institution TEXT,
    email TEXT,
    orcid TEXT,
    google_scholar_id TEXT,
    research_interests TEXT,
    appointment_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS grant_schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agency TEXT CHECK(agency IN ('RGC','ITF','NSFC','Other')),
    scheme_name TEXT,
    scheme_code TEXT,
    description TEXT,
    typical_deadline_month INTEGER,
    typical_funding_range TEXT,
    duration_years INTEGER,
    eligibility_notes TEXT,
    url TEXT
);

CREATE TABLE IF NOT EXISTS deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER REFERENCES grant_schemes(id),
    year INTEGER,
    external_deadline DATE,
    institutional_deadline DATE,
    call_url TEXT,
    status TEXT CHECK(status IN ('upcoming','open','closed')) DEFAULT 'upcoming',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER REFERENCES researchers(id),
    scheme_id INTEGER REFERENCES grant_schemes(id),
    deadline_id INTEGER REFERENCES deadlines(id),
    project_title TEXT,
    requested_amount REAL,
    duration_months INTEGER,
    status TEXT CHECK(status IN ('planning','drafting','internal_review','submitted','under_review','awarded','rejected','withdrawn')) DEFAULT 'planning',
    submission_date DATE,
    outcome_date DATE,
    awarded_amount REAL,
    reviewer_score REAL,
    reviewer_comments TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    researcher_id INTEGER REFERENCES researchers(id),
    title TEXT,
    authors TEXT,
    journal TEXT,
    year INTEGER,
    doi TEXT,
    citation_count INTEGER,
    is_corresponding_author BOOLEAN,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budget_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id),
    category TEXT CHECK(category IN ('ra_salary','postdoc_salary','equipment','travel','consumables','services','other')),
    description TEXT,
    year INTEGER,
    amount REAL,
    justification TEXT
);
"""

# ---------------------------------------------------------------------------
# Shared (cross-tool researcher linking)
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_researchers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL,
    name_tc TEXT,
    institution TEXT,
    department TEXT,
    grant_tracker_researcher_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/academic") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/academic") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "paper_sieve": db_dir / "paper_sieve.db",
        "cite_bot": db_dir / "cite_bot.db",
        "translate_assist": db_dir / "translate_assist.db",
        "grant_tracker": db_dir / "grant_tracker.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["paper_sieve"], PAPER_SIEVE_SCHEMA)
    run_migrations(db_paths["cite_bot"], CITE_BOT_SCHEMA)
    run_migrations(db_paths["translate_assist"], TRANSLATE_ASSIST_SCHEMA)
    run_migrations(db_paths["grant_tracker"], GRANT_TRACKER_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
