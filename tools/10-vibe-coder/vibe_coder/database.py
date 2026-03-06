"""Database schema initialization for all Vibe Coder tools."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import run_migrations
from openclaw_shared.mona_events import init_mona_db

# ---------------------------------------------------------------------------
# CodeQwen
# ---------------------------------------------------------------------------
CODE_QWEN_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    feature TEXT CHECK(feature IN ('completion','explanation','refactoring','debugging','docstring','chat')),
    input_code TEXT,
    input_language TEXT,
    output_text TEXT,
    model_name TEXT,
    tokens_generated INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS completions_cache (
    id INTEGER PRIMARY KEY,
    prefix_hash TEXT,
    suffix_hash TEXT,
    language TEXT,
    completion TEXT,
    confidence REAL,
    hit_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_stats (
    id INTEGER PRIMARY KEY,
    date DATE,
    feature TEXT,
    request_count INTEGER DEFAULT 0,
    avg_latency_ms REAL,
    avg_tokens INTEGER
);
"""

# ---------------------------------------------------------------------------
# DocuWriter
# ---------------------------------------------------------------------------
DOCU_WRITER_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    project_path TEXT NOT NULL,
    project_name TEXT,
    primary_language TEXT,
    last_analyzed TIMESTAMP,
    file_count INTEGER,
    total_functions INTEGER,
    documented_functions INTEGER,
    documentation_coverage REAL
);

CREATE TABLE IF NOT EXISTS generated_docs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_type TEXT CHECK(doc_type IN ('readme','api_reference','architecture','changelog','docstrings')),
    content TEXT,
    output_path TEXT,
    generation_params TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_elements (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    file_path TEXT,
    element_type TEXT CHECK(element_type IN ('function','class','method','module')),
    element_name TEXT,
    signature TEXT,
    has_docstring BOOLEAN,
    docstring TEXT,
    line_number INTEGER,
    last_modified TIMESTAMP
);

CREATE TABLE IF NOT EXISTS freshness_checks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_path TEXT,
    code_hash TEXT,
    doc_hash TEXT,
    is_stale BOOLEAN,
    stale_sections TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# GitAssistant
# ---------------------------------------------------------------------------
GIT_ASSISTANT_SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY,
    repo_path TEXT,
    github_remote TEXT,
    github_owner TEXT,
    github_repo TEXT,
    default_branch TEXT DEFAULT 'main',
    last_analyzed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pr_generations (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    branch_name TEXT,
    base_branch TEXT,
    diff_summary TEXT,
    generated_title TEXT,
    generated_body TEXT,
    files_changed INTEGER,
    insertions INTEGER,
    deletions INTEGER,
    suggested_reviewers TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS release_notes (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    from_tag TEXT,
    to_tag TEXT,
    version TEXT,
    notes_content TEXT,
    commit_count INTEGER,
    features TEXT,
    fixes TEXT,
    breaking TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS code_ownership (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    file_path TEXT,
    author_email TEXT,
    commit_count INTEGER,
    lines_owned INTEGER,
    last_commit TIMESTAMP,
    ownership_score REAL
);

CREATE TABLE IF NOT EXISTS issue_labels (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    issue_number INTEGER,
    suggested_labels TEXT,
    confidence_scores TEXT,
    applied BOOLEAN DEFAULT FALSE,
    labeled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# HKDevKit
# ---------------------------------------------------------------------------
HK_DEV_KIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    project_name TEXT,
    integrations TEXT,
    created_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snippets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    language TEXT DEFAULT 'python',
    category TEXT CHECK(category IN ('payment','validation','formatting','api','utility')),
    tags TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_configs (
    id INTEGER PRIMARY KEY,
    service_name TEXT NOT NULL,
    base_url TEXT,
    auth_type TEXT,
    api_key TEXT,
    additional_config TEXT,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS generated_docs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_type TEXT,
    content TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ---------------------------------------------------------------------------
# Shared cross-tool DB
# ---------------------------------------------------------------------------
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS developer_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    preferred_languages TEXT,
    coding_style TEXT,
    github_username TEXT,
    default_output_language TEXT DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_dir(workspace: str | Path = "~/OpenClawWorkspace/vibe-coder") -> Path:
    db_dir = Path(workspace).expanduser()
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir


def init_all_databases(workspace: str | Path = "~/OpenClawWorkspace/vibe-coder") -> dict[str, Path]:
    """Initialize all databases and return a mapping of name -> path."""
    db_dir = get_db_dir(workspace)

    db_paths = {
        "code_qwen": db_dir / "code_qwen.db",
        "docu_writer": db_dir / "docu_writer.db",
        "git_assistant": db_dir / "git_assistant.db",
        "hk_dev_kit": db_dir / "hk_dev_kit.db",
        "shared": db_dir / "shared.db",
        "mona_events": db_dir / "mona_events.db",
    }

    run_migrations(db_paths["code_qwen"], CODE_QWEN_SCHEMA)
    run_migrations(db_paths["docu_writer"], DOCU_WRITER_SCHEMA)
    run_migrations(db_paths["git_assistant"], GIT_ASSISTANT_SCHEMA)
    run_migrations(db_paths["hk_dev_kit"], HK_DEV_KIT_SCHEMA)
    run_migrations(db_paths["shared"], SHARED_SCHEMA)
    init_mona_db(db_paths["mona_events"])

    return db_paths
