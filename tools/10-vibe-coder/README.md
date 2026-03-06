# Vibe Coder Dashboard

Unified FastAPI application providing four developer productivity tools for Hong Kong software engineers, accessible at `http://mona.local:8010`.

## Tools

| Tool | Purpose |
|------|---------|
| **CodeQwen** | Local coding assistant with FIM completions, chat, explainer, refactorer, and debugger (MLX-backed) |
| **DocuWriter** | AI documentation generator for README, API docs, docstrings, architecture diagrams, and changelogs |
| **GitAssistant** | Git workflow automation: PR descriptions, release notes, commit message improvement, issue labeling |
| **HKDevKit** | Hong Kong-specific connectors: FPS, Octopus, GovHK APIs, weather, demographics, and boilerplate scaffolding |

## Quick Start

### Prerequisites

- Python 3.11+
- macOS ARM64 recommended for MLX (optional; mock LLM available)

### Installation

```bash
cd tools/10-vibe-coder
pip install -e ../shared
pip install -e .
# Or with MLX for local inference:
pip install -e ".[mlx]"
```

### Running the Dashboard

```bash
python -m vibe_coder.app
```

Or with uvicorn:

```bash
uvicorn vibe_coder.app:app --host 0.0.0.0 --port 8010
```

Then open **http://localhost:8010**. On first run, complete the setup wizard at `/setup/`.

## User Guide

### CodeQwen

- **Monaco Editor** — Inline code completion with fill-in-the-middle (FIM) support.
- **Chat** — Ask questions about code; responses stream in real time.
- **Explainer** — Generate natural-language explanations for selected code blocks.
- **Refactorer** — Suggest and apply refactoring improvements.
- **Debugger** — Help trace and diagnose issues.

### DocuWriter

- **Project Analyzer** — Scan codebase structure, dependencies, and entry points.
- **Doc Generation** — README, API reference, docstrings, architecture overview, changelog.
- **Freshness Check** — Detect outdated documentation on commit (optional).

### GitAssistant

- **PR Generator** — Analyze diff and generate structured PR descriptions.
- **Release Notes** — Summarize commits for release notes.
- **Commit Helper** — Improve commit messages to conventional format.
- **Issue Labeler** — Auto-suggest labels from issue content.

### HKDevKit

- **FPS Connectors** — HSBC, Standard Chartered adapters for Faster Payment System.
- **Octopus** — Merchant API integration.
- **GovHK** — Weather, demographic data with caching.
- **Boilerplate** — Scaffold HK-specific project templates.

## Configuration

Edit `config.yaml` in the project root:

| Section | Key | Description |
|---------|-----|-------------|
| `llm` | `provider` | `mock` (dev) or `mlx` (local inference) |
| `llm` | `model_path` | MLX model path (e.g. `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit`) |
| `extra` | `model_mode` | `warm` or `cold` for CodeQwen |
| `extra` | `context_window` | Token limit for completions |
| `extra` | `default_base_branch` | Git default branch |
| `extra` | `octopus_merchant_id` | Octopus merchant credentials |

## Architecture

```
tools/10-vibe-coder/
├── config.yaml
├── vibe_coder/
│   ├── app.py
│   ├── database.py
│   ├── seed_data.py
│   ├── dashboard/
│   ├── code_qwen/
│   ├── docu_writer/
│   ├── git_assistant/
│   └── hk_dev_kit/
└── tests/
```

**Databases** (in `~/OpenClawWorkspace/vibe-coder/`): `code_qwen.db`, `docu_writer.db`, `git_assistant.db`, `hk_dev_kit.db`, `shared.db`, `mona_events.db`

## Running Tests

```bash
cd tools/10-vibe-coder
python -m pytest tests/ -v
```

## Related

- **Implementation Plan**: `.cursor/plans/vibe_coder_implementation_25ab3345.plan.md`
- **Shared Library**: `tools/shared/`
