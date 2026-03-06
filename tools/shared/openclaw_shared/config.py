"""YAML config loader with Pydantic validation and env var overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "mock"
    model_path: str = ""
    embedding_model_path: str = ""
    max_tokens: int = 512


class MessagingConfig(BaseModel):
    whatsapp_enabled: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    default_language: str = "en"


class DatabaseConfig(BaseModel):
    encryption_key: str = ""
    workspace_path: str = "~/OpenClawWorkspace"


class AuthConfig(BaseModel):
    pin_hash: str = ""
    session_ttl_hours: int = 24


class ToolConfig(BaseModel):
    tool_name: str = ""
    version: str = "1.0.0"
    port: int = 8000
    llm: LLMConfig = LLMConfig()
    messaging: MessagingConfig = MessagingConfig()
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    extra: dict[str, Any] = {}


def _apply_env_overrides(data: dict[str, Any], prefix: str = "OPENCLAW") -> dict[str, Any]:
    """Override nested config values from environment variables.

    OPENCLAW_LLM_PROVIDER=mlx -> data["llm"]["provider"] = "mlx"
    """
    for key, value in os.environ.items():
        if not key.startswith(f"{prefix}_"):
            continue
        parts = key[len(prefix) + 1 :].lower().split("_")
        target = data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return data


def load_config(config_path: str | Path) -> ToolConfig:
    """Load config from YAML file with environment variable overrides."""
    path = Path(config_path)
    data: dict[str, Any] = {}
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    data = _apply_env_overrides(data)
    return ToolConfig(**data)


def save_config(config: ToolConfig, config_path: str | Path) -> None:
    """Persist config back to YAML."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
    path.chmod(0o600)
