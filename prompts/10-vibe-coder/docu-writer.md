# DocuWriter

## Overview

DocuWriter is a local AI-powered documentation generator that analyzes codebases and produces comprehensive technical documentation including README files, API documentation, inline code documentation, and architecture overviews. It uses the local LLM to understand code structure and generate clear, well-organized explanations — all without sending proprietary code to external services.

## Target User

Software developers, open-source maintainers, and development teams who need to create or update technical documentation but find the manual process time-consuming. Especially valuable for solo developers and small teams who lack dedicated technical writers.

## Core Features

- **README Generator**: Analyzes a project's structure, dependencies, and entry points to generate a comprehensive README.md with installation instructions, usage examples, project structure, and contributing guidelines
- **API Documentation**: Parses Python/JavaScript source files to extract function signatures, class definitions, and docstrings, then generates formatted API reference documentation
- **Inline Documentation**: Scans code for undocumented functions and classes, generates appropriate docstrings/JSDoc comments, and applies them in-place
- **Architecture Overview**: Generates a high-level architecture document describing the project's module structure, data flow, and key design patterns
- **Changelog Generator**: Analyzes git commit history to produce human-readable changelogs grouped by version, feature, bugfix, and breaking change categories
- **Documentation Freshness Checker**: Compares existing documentation against current code to identify outdated sections that need updating

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| LLM | MLX local inference (Qwen-2.5-Coder-7B or Qwen-2.5-7B) for code understanding and documentation generation |
| Code Parsing | ast module (Python), tree-sitter for multi-language parsing (JS/TS/Go/Rust) |
| Git | GitPython for commit history analysis and changelog generation |
| Markdown | mdformat for consistent markdown formatting; Jinja2 for documentation templates |
| Database | SQLite for documentation snapshots, freshness tracking, and generation history |
| UI | Streamlit with documentation preview and editing interface |
| CLI | Typer for command-line documentation generation |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/docu-writer/
├── app.py                        # Streamlit documentation dashboard
├── cli.py                        # CLI entry point (docuwriter command)
├── analyzers/
│   ├── project_analyzer.py       # Project structure and dependency analysis
│   ├── python_parser.py          # Python AST-based code analysis
│   ├── js_parser.py              # JavaScript/TypeScript parsing via tree-sitter
│   ├── git_analyzer.py           # Git history analysis for changelogs
│   └── freshness_checker.py      # Documentation vs code staleness detection
├── generators/
│   ├── readme_generator.py       # README.md generation
│   ├── api_doc_generator.py      # API reference documentation
│   ├── docstring_generator.py    # Inline docstring/JSDoc generation
│   ├── architecture_generator.py # Architecture overview document
│   └── changelog_generator.py    # Git-based changelog production
├── templates/
│   ├── readme.md.j2              # README template
│   ├── api_doc.md.j2             # API documentation template
│   └── architecture.md.j2        # Architecture document template
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Documentation generation prompts
├── data/
│   └── docuwriter.db             # SQLite database
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/docu-writer/
├── data/
│   └── docuwriter.db            # SQLite database
├── output/                      # Generated documentation output
└── logs/
    └── generation.log           # Documentation generation logs
```

## Key Integrations

- **Local LLM (MLX)**: All code analysis and documentation generation runs on-device — safe for proprietary codebases
- **Git**: Reads repository history for changelog generation and documentation freshness tracking
- **File System**: Analyzes project directory structure and reads source files directly
- **Telegram Bot API**: Secondary channel for build notifications and documentation alerts.

## GUI Specification

Part of the **Vibe Coder Dashboard** (`http://mona.local:8010`) — DocuWriter tab.

### Views

- **Project File Tree**: Browse the project directory structure. Select files or folders to document.
- **Generated Docs Viewer**: Rendered markdown documentation with table of contents, function signatures, and usage examples.
- **Style Configuration**: Select documentation style (API reference, user guide, README, inline comments) and detail level.
- **Diff View**: Side-by-side comparison of current documentation vs newly regenerated version. Accept individual changes or apply all.
- **Export Panel**: Export as Markdown, HTML, or PDF.

### Mona Integration

- Mona auto-generates documentation when new code is committed or files change.
- Mona detects undocumented functions and suggests documentation additions.
- Developer reviews and approves documentation changes.

### Manual Mode

- Developer can manually select files, generate documentation, configure styles, and export without Mona.

## HK-Specific Requirements

- Bilingual documentation support: Generate documentation in English, Traditional Chinese, or both — relevant for HK development teams serving bilingual user bases
- Open-source compliance: HK startups increasingly contribute to open source — README generator should include LICENSE references and contributing guidelines
- This tool is primarily language/locale-agnostic but should handle Chinese comments and variable names in code analysis without errors

## Data Model

```sql
CREATE TABLE projects (
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

CREATE TABLE generated_docs (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_type TEXT CHECK(doc_type IN ('readme','api_reference','architecture','changelog','docstrings')),
    content TEXT,
    output_path TEXT,
    generation_params TEXT,  -- JSON: model, temperature, etc.
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE code_elements (
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

CREATE TABLE freshness_checks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    doc_path TEXT,
    code_hash TEXT,
    doc_hash TEXT,
    is_stale BOOLEAN,
    stale_sections TEXT,  -- JSON array
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Developer Profile**: Name, preferred documentation style (API reference, user guide, README), and default output language (English / Chinese / bilingual)
2. **Model Configuration**: Verify LLM is loaded; configure generation parameters (temperature, detail level)
3. **Project Setup**: Select default project directories for code analysis and documentation output
4. **Git Configuration**: Configure Git repositories for changelog generation
5. **Telegram**: Configure Telegram bot token for documentation alerts (optional)
6. **Sample Data**: Option to analyze a demo project and generate sample documentation
7. **Connection Test**: Validates model loading, file system access, Git integration, and Telegram bot connectivity

## Testing Criteria

- [ ] Generates a complete README.md for a Python project with correct installation instructions from requirements.txt
- [ ] API documentation lists all public functions with signatures, parameters, and return types
- [ ] Docstring generator produces valid PEP 257 docstrings for undocumented Python functions
- [ ] Changelog groups commits by category (feature, fix, chore) from the last 50 git commits
- [ ] Architecture overview correctly identifies the main modules and their relationships
- [ ] Freshness checker detects when a function's documentation doesn't match its current signature
- [ ] CLI `docuwriter readme .` generates a README and writes it to the current directory

## Implementation Notes

- Code parsing strategy: use Python's `ast` module for Python code (faster, more reliable); use tree-sitter for JS/TS (handles modern syntax including JSX/TSX)
- LLM prompting: provide the code structure as a summarized tree first, then generate documentation section by section — this produces more coherent output than trying to generate everything at once
- Freshness detection: hash each documented code element (function signature + body) and compare against the hash stored at documentation generation time; flag as stale when hashes diverge
- Docstring generation: for each undocumented function, extract the signature + function body, and generate a docstring with parameter descriptions and return value
- Changelog: parse commit messages using conventional commits format when available; fall back to LLM-based categorization for free-form commit messages
- Memory budget: ~5GB (LLM + code parsing); for large codebases, analyze files incrementally rather than loading everything into memory
- Template-based generation: use Jinja2 templates as the skeleton and fill in LLM-generated content — this ensures consistent formatting even if the LLM output varies
- Consider implementing a "documentation CI" mode that runs on git pre-commit to ensure documentation stays current
- **Logging**: All operations logged to `/var/log/openclaw/docu-writer.log` with daily rotation (7-day retention). Code snippets truncated in logs to avoid leaking proprietary source code.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Source code never leaves the local machine — zero cloud processing for all inference.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM model state (loaded/warm/cold), and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON archive of conversation history, generated documentation, and configuration.
