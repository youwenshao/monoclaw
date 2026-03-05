# GitAssistant

## Overview

GitAssistant is a local AI-powered Git workflow automation tool that drafts pull request descriptions from diffs, suggests reviewers based on code ownership, writes release notes from tagged commits, and auto-labels GitHub Issues based on content analysis. It streamlines the software development lifecycle tasks that surround code changes, using the local LLM so that proprietary code diffs never leave the machine.

## Target User

Software developers, team leads, and open-source maintainers who want to spend less time writing PR descriptions, release notes, and triaging issues, and more time writing code. Suitable for individual developers managing their own repos or team leads reviewing multiple PRs daily.

## Core Features

- **PR Description Generator**: Analyzes git diffs (staged changes or branch comparison) and produces structured PR descriptions with summary, motivation, changes breakdown, testing notes, and related issues
- **Reviewer Suggestion**: Analyzes code ownership history (git blame + commit frequency per file) to suggest the most appropriate reviewers for a given PR
- **Release Notes Writer**: Generates human-readable release notes from commits between two tags, grouping by features, bug fixes, breaking changes, and improvements
- **Issue Auto-Labeler**: Analyzes GitHub Issue content (title + body) and suggests appropriate labels based on the project's existing label taxonomy
- **Commit Message Improver**: Takes a draft commit message and rewrites it following conventional commits format or the project's commit message conventions
- **Branch Summary**: Provides a quick natural-language summary of all changes on the current branch compared to main/master

## Tech Stack

| Component | Library / Tool |
|-----------|---------------|
| Git | GitPython for repository analysis; subprocess for git commands |
| GitHub | PyGithub or httpx for GitHub API interaction (issues, PRs, labels, reviewers) |
| LLM | MLX local inference (Qwen-2.5-Coder-7B) for text generation from code diffs |
| CLI | Typer for command-line interface (`gitassist pr`, `gitassist release`, `gitassist label`) |
| Database | SQLite for reviewer history, label mappings, and generation cache |
| UI | Streamlit for optional dashboard view of PRs, issues, and release history |
| Telegram | `python-telegram-bot` |

## File Structure

```
/opt/openclaw/skills/local/git-assistant/
├── app.py                        # Streamlit optional dashboard
├── cli.py                        # CLI entry point (gitassist command)
├── pr/
│   ├── diff_analyzer.py          # Git diff parsing and summarization
│   ├── description_generator.py  # PR description drafting
│   └── reviewer_suggester.py     # Code ownership analysis for reviewer suggestions
├── release/
│   ├── commit_analyzer.py        # Commit categorization between tags
│   ├── notes_generator.py        # Release notes generation
│   └── version_helper.py         # SemVer version suggestion
├── issues/
│   ├── issue_fetcher.py          # GitHub Issues API integration
│   ├── auto_labeler.py           # Issue content analysis and label suggestion
│   └── label_taxonomy.py         # Project label taxonomy management
├── commits/
│   ├── message_improver.py       # Commit message enhancement
│   └── conventional_commits.py   # Conventional commits format enforcement
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # PR, release, and issue analysis prompts
├── data/
│   └── gitassist.db              # SQLite database
├── requirements.txt
└── README.md
```

```
~/OpenClawWorkspace/git-assistant/
├── data/
│   └── gitassist.db             # SQLite database
├── cache/                       # Cached PR descriptions and release notes
└── logs/
    └── git_ops.log              # Git operation logs
```

## Key Integrations

- **GitHub API**: Read/write access to PRs, Issues, Labels, and Releases via PyGithub or REST API
- **Git (local)**: Reads repository state, diffs, logs, blame, and tags from the local git repository
- **Local LLM (MLX)**: All text generation from code analysis runs on-device
- **Telegram Bot API**: Secondary channel for build notifications and documentation alerts.

## GUI Specification

Part of the **Vibe Coder Dashboard** (`http://mona.local:8010`) — GitAssistant tab.

### Views

- **Repo Selector**: Choose from local Git repositories. Display recent commits, branches, and tags.
- **PR Description Generator**: Select commits to include, generate a structured PR description with summary, changes, and testing notes. Edit before copying.
- **Release Notes Builder**: Select version range (tag to tag), generate a formatted changelog grouped by category (features, fixes, breaking changes).
- **Issue Labeling**: Display open issues with AI-suggested labels (bug, feature, enhancement, documentation). Apply labels with one click.
- **Commit Message Helper**: Staged changes summary with a suggested conventional commit message. Edit and copy.

### Mona Integration

- Mona auto-generates PR descriptions when branches are pushed.
- Mona suggests release notes when tags are created.
- Developer reviews and edits all generated content before use.

### Manual Mode

- Developer can manually browse repos, write PR descriptions, generate release notes, and label issues without Mona.

## HK-Specific Requirements

- This tool is primarily locale-agnostic, but supports:
  - Chinese-language commit messages: can parse and categorize commits written in Traditional or Simplified Chinese
  - Bilingual PR descriptions: can generate PR descriptions in English, Chinese, or both for teams with bilingual workflows
  - Chinese-language GitHub Issues: auto-labeler handles issue content in Chinese without degradation

## Data Model

```sql
CREATE TABLE repositories (
    id INTEGER PRIMARY KEY,
    repo_path TEXT,
    github_remote TEXT,
    github_owner TEXT,
    github_repo TEXT,
    default_branch TEXT DEFAULT 'main',
    last_analyzed TIMESTAMP
);

CREATE TABLE pr_generations (
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
    suggested_reviewers TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE release_notes (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    from_tag TEXT,
    to_tag TEXT,
    version TEXT,
    notes_content TEXT,
    commit_count INTEGER,
    features TEXT,  -- JSON array
    fixes TEXT,     -- JSON array
    breaking TEXT,  -- JSON array
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE code_ownership (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    file_path TEXT,
    author_email TEXT,
    commit_count INTEGER,
    lines_owned INTEGER,
    last_commit TIMESTAMP,
    ownership_score REAL
);

CREATE TABLE issue_labels (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER REFERENCES repositories(id),
    issue_number INTEGER,
    suggested_labels TEXT,  -- JSON array
    confidence_scores TEXT, -- JSON array
    applied BOOLEAN DEFAULT FALSE,
    labeled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## First-Run Setup

On first launch, the tool presents a configuration wizard:

1. **Developer Profile**: Name, preferred PR description style, and default commit message conventions
2. **Model Configuration**: Verify Qwen-2.5-Coder-7B is loaded; configure generation parameters
3. **Git Configuration**: Configure default Git repositories, base branch, and commit message format (conventional commits or free-form)
4. **GitHub Integration**: Configure GitHub token via `gh auth token` or `GITHUB_TOKEN` for PR, Issue, and Release access
5. **Telegram**: Configure Telegram bot token for PR and release notifications (optional)
6. **Sample Data**: Option to analyze a demo repository for testing PR descriptions and release notes
7. **Connection Test**: Validates model loading, Git repository access, GitHub API connectivity, and Telegram bot

## Testing Criteria

- [ ] Generates a meaningful PR description from a diff with 5 changed files covering the summary, changes, and test plan sections
- [ ] Reviewer suggestion correctly identifies the top 3 contributors to the changed files based on git blame
- [ ] Release notes group 20 commits between two tags into features, fixes, and improvements categories
- [ ] Issue auto-labeler correctly suggests "bug" label for an issue describing unexpected behavior
- [ ] Commit message improver rewrites "fixed stuff" into a conventional commit format "fix: resolve null pointer in user auth flow"
- [ ] Branch summary provides a coherent 2-3 sentence overview of all changes on a feature branch
- [ ] CLI `gitassist pr` generates a description and opens it in $EDITOR for review before creating the PR

## Implementation Notes

- Diff analysis: for large diffs (>500 lines), summarize per-file changes first, then synthesize into an overall PR description — don't try to feed the entire diff to the LLM at once
- Code ownership: compute ownership scores as `(0.6 * recent_commit_weight) + (0.4 * blame_line_count)` — recent activity matters more than total historical lines
- Release notes categorization: if the repo uses conventional commits, parse prefixes directly; otherwise, use LLM to categorize each commit message
- Issue labeling: fetch the repo's existing labels first, then ask the LLM to select from that fixed set — this prevents hallucinated labels
- CLI workflow: `gitassist pr` should default to comparing current branch against default branch; open the generated text in $EDITOR for review; after editing, optionally create the PR via GitHub API
- Memory budget: ~5GB when LLM is loaded; ~200MB for pure Git analysis without LLM features
- GitHub token management: use `gh auth token` or `GITHUB_TOKEN` env var — never store tokens in the SQLite database
- Consider implementing a git hook integration that auto-generates commit messages from staged changes (opt-in via git config)
- **Logging**: All operations logged to `/var/log/openclaw/git-assistant.log` with daily rotation (7-day retention). Code snippets truncated in logs to avoid leaking proprietary source code.
- **Security**: SQLite database encrypted at rest. Dashboard requires PIN authentication. Source code never leaves the local machine — zero cloud processing for all inference.
- **Health check**: Exposes `GET /health` returning tool status, uptime, database connectivity, LLM model state (loaded/warm/cold), and memory usage.
- **Data export**: Supports `POST /api/export` for portable JSON archive of conversation history, generated documentation, and configuration.
