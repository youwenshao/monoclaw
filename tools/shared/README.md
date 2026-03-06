# OpenClaw Shared Library

Shared utilities for all OpenClaw industry tools. Provides common infrastructure for config, auth, LLM, messaging, database, health checks, export, and Mona events.

## Purpose

Every tool in `tools/01-real-estate/` through `tools/12-student/` depends on `openclaw_shared`. It centralizes:

- **Configuration** — YAML config loader with Pydantic validation and env var overrides
- **Authentication** — PIN-based dashboard auth with session management
- **LLM** — Mock and MLX adapters for local inference
- **Messaging** — WhatsApp (Twilio) and Telegram bot integrations
- **Database** — SQLite migration helpers and connection utilities
- **Health** — Health check router for tool status
- **Export** — Data export router for backup and PDPO
- **Mona Events** — Activity feed and approval queue for AI assistant integration
- **Logging** — Structured logging setup

## Installation

From any tool directory:

```bash
cd tools/04-accounting  # or any tool
pip install -e ../shared
```

Or from the shared directory:

```bash
cd tools/shared
pip install -e .
```

### Optional Extras

| Extra | Description |
|-------|-------------|
| `[mlx]` | MLX adapter for local LLM inference (macOS ARM64) |
| `[messaging]` | Twilio (WhatsApp) and python-telegram-bot |
| `[all]` | All optional dependencies |

```bash
pip install -e ".[mlx,messaging]"
```

## Modules

| Module | Description |
|--------|-------------|
| `openclaw_shared.config` | `load_config()`, `save_config()`, `ToolConfig`, `LLMConfig`, `MessagingConfig`, etc. |
| `openclaw_shared.auth` | `PINAuthMiddleware`, `create_auth_router()` |
| `openclaw_shared.llm` | `create_llm_provider()`, `BaseLLM`, mock and MLX adapters |
| `openclaw_shared.messaging` | WhatsApp and Telegram send/receive helpers |
| `openclaw_shared.database` | `run_migrations()`, `get_db()` |
| `openclaw_shared.health` | `create_health_router()` |
| `openclaw_shared.export` | `create_export_router()` |
| `openclaw_shared.mona_events` | `emit_event()`, `get_events()`, `acknowledge_event()`, `init_mona_db()` |
| `openclaw_shared.logging` | `setup_logging()` |

## Usage by Tools

Tools typically import and use shared components as follows:

```python
from openclaw_shared.auth import PINAuthMiddleware, create_auth_router
from openclaw_shared.config import load_config, save_config
from openclaw_shared.export import create_export_router
from openclaw_shared.health import create_health_router
from openclaw_shared.llm import create_llm_provider
from openclaw_shared.logging import setup_logging
from openclaw_shared.mona_events import get_events, init_mona_db
```

Config is loaded from each tool's `config.yaml`:

```python
config = load_config(CONFIG_PATH)  # e.g. BASE_DIR.parent / "config.yaml"
```

LLM provider is created with:

```python
llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)
```

## Dependencies

Core dependencies (no extras):

- `fastapi>=0.115`
- `uvicorn[standard]>=0.32`
- `pyyaml>=6.0`
- `pydantic>=2.0`
- `python-dateutil>=2.9`
- `httpx>=0.27`
- `apscheduler>=3.10`

## Architecture

```
tools/shared/
├── pyproject.toml
├── README.md
└── openclaw_shared/
    ├── __init__.py
    ├── auth.py
    ├── config.py
    ├── database.py
    ├── export.py
    ├── health.py
    ├── logging.py
    ├── mona_events.py
    ├── llm/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── mock_adapter.py
    │   └── mlx_adapter.py
    └── messaging/
        ├── __init__.py
        ├── base.py
        ├── whatsapp.py
        └── telegram.py
```

## Related

- **Tools**: `tools/01-real-estate/` through `tools/12-student/` — all depend on this library
- **Real Estate README**: `tools/01-real-estate/README.md` — documents shared library usage in context
