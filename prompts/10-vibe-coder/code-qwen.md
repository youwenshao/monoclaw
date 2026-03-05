# CodeQwen

## Tool Name & Overview

CodeQwen is a local coding assistant powered by Qwen-2.5-Coder-7B running on MLX. It provides code completion, explanation, refactoring, and debugging assistance for Python, JavaScript, React, and other languages — all running entirely on-device. It operates as both a CLI tool for terminal-based workflows and a lightweight editor plugin server, giving developers a private, zero-latency coding companion without cloud API dependencies.

## Target User

Software developers, indie hackers, and technical founders in Hong Kong who want an always-available, private coding assistant that works offline, incurs no API costs, and runs locally on their M4 Mac hardware.

## Core Features

- **Code Completion**: Context-aware code completion using the local Qwen-2.5-Coder-7B model — accepts a code prefix/suffix and generates the most likely continuation
- **Code Explanation**: Paste a code block and receive a plain-English (or Chinese) explanation of what it does, suitable for code review or learning
- **Refactoring Suggestions**: Analyze a function or class and receive suggestions for improved structure, naming, performance, and adherence to best practices
- **Bug Detection**: Identifies potential bugs, logic errors, and common anti-patterns in submitted code snippets
- **CLI Interface**: Command-line tool for quick code queries (`codeqwen explain`, `codeqwen complete`, `codeqwen refactor`) integrated into terminal workflows
- **LSP-Compatible Server**: Runs as a lightweight Language Server Protocol server that editors (VS Code, Cursor, Neovim) can connect to for inline completions

## Tech Stack

- **LLM**: Qwen-2.5-Coder-7B via MLX (4-bit quantized for 16GB RAM); mlx-lm for model loading and inference
- **CLI**: Click or Typer for command-line interface construction
- **Server**: FastAPI for the LSP-compatible HTTP server; uvicorn for async serving
- **Streaming**: Server-Sent Events (SSE) for streaming code completions to editor clients
- **Database**: SQLite for conversation history, completion cache, and usage analytics
- **Editor Integration**: VS Code extension (if needed) or compatible with existing Continue/Copilot-style extension protocols

## File Structure

```
~/OpenClaw/tools/code-qwen/
├── app.py                       # FastAPI server for editor integration
├── cli.py                       # CLI entry point (codeqwen command)
├── inference/
│   ├── model_loader.py          # MLX model loading and quantization handling
│   ├── completion_engine.py     # Code completion (FIM: fill-in-middle support)
│   ├── chat_engine.py           # Chat-based code Q&A
│   └── streaming.py             # SSE streaming response handler
├── features/
│   ├── explainer.py             # Code explanation generation
│   ├── refactorer.py            # Refactoring suggestion engine
│   ├── debugger.py              # Bug detection and fix suggestion
│   └── docstring_writer.py      # Auto-generate docstrings for functions
├── server/
│   ├── routes.py                # FastAPI route definitions
│   ├── lsp_adapter.py           # LSP-compatible request/response adapter
│   └── middleware.py            # Request logging and rate limiting
├── data/
│   ├── codeqwen.db              # SQLite database
│   └── prompts/                 # System prompts per feature
├── requirements.txt
└── README.md
```

## Key Integrations

- **MLX Framework**: Apple Silicon-optimized LLM inference — critical for acceptable latency on M4 hardware
- **Editor Plugins**: Compatible with VS Code extension protocols for inline code completion
- **Terminal**: CLI tool integrates with shell workflows (pipe code in, get completions out)

## HK-Specific Requirements

- This tool is language/locale-agnostic in its core functionality, but should support:
  - Chinese-language comments and variable names (Unicode-safe throughout)
  - Code explanation output in Traditional Chinese when requested
  - Documentation generation in bilingual format (English + Chinese) for HK development teams that operate bilingually
- HK developer ecosystem: Strong demand for React/Next.js (startup scene), Python (fintech/data), and Node.js (backend services) — prioritize these languages in testing and prompt tuning
- Offline-first: HK developers may work in coffee shops, co-working spaces, or on MTR with intermittent connectivity — the tool must work fully offline

## Data Model

```sql
CREATE TABLE conversations (
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

CREATE TABLE completions_cache (
    id INTEGER PRIMARY KEY,
    prefix_hash TEXT,
    suffix_hash TEXT,
    language TEXT,
    completion TEXT,
    confidence REAL,
    hit_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE usage_stats (
    id INTEGER PRIMARY KEY,
    date DATE,
    feature TEXT,
    request_count INTEGER DEFAULT 0,
    avg_latency_ms REAL,
    avg_tokens INTEGER
);
```

## Testing Criteria

- [ ] Code completion generates syntactically valid Python for a 5-line function prefix within 2 seconds
- [ ] Code explanation correctly describes a sorting algorithm in plain English
- [ ] Refactoring suggestion identifies a deeply nested conditional and proposes early return pattern
- [ ] Bug detection catches an off-by-one error in a loop boundary
- [ ] CLI `codeqwen complete` reads from stdin and writes completion to stdout
- [ ] FastAPI server responds to completion requests via SSE with streaming tokens
- [ ] Model loads and serves first request within 15 seconds on M4/16GB hardware

## Implementation Notes

- Model choice: Qwen-2.5-Coder-7B has excellent coding benchmarks and fits in 16GB RAM at 4-bit quantization (~4GB VRAM); use mlx-lm for loading
- Fill-in-Middle (FIM): Qwen-2.5-Coder supports FIM tokens — use `<|fim_prefix|>`, `<|fim_suffix|>`, `<|fim_middle|>` for code completion (more accurate than left-to-right generation)
- Streaming is essential for UX — users expect to see tokens appear progressively; implement SSE for the HTTP server and character-by-character output for CLI
- Completion cache: hash the code prefix + suffix and cache completions; if the same context appears again, return cached result instantly (common for repeated editing patterns)
- Context window: Qwen-2.5-Coder-7B supports 32K context — sufficient for most single-file coding tasks; for multi-file context, implement a relevance-based file selection
- Memory budget: ~5GB (model ~4GB + inference overhead ~1GB); this is one of the heavier tools — avoid running alongside other LLM-intensive tools
- Latency target: <500ms for short completions (single line); <2s for multi-line completions; <5s for full explanations/refactoring
- Consider implementing a "warm" mode where the model stays loaded in memory between requests vs a "cold" mode that unloads after inactivity to free RAM
