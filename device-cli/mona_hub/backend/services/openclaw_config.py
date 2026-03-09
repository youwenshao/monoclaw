"""Sync LLM provider config to OpenClaw's ~/.openclaw (.env and openclaw.json)."""

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Mona provider id -> (OpenClaw provider id, default model id)
PROVIDER_TO_OPENCLAW_MODEL: dict[str, tuple[str, str]] = {
    "deepseek": ("deepseek", "deepseek-chat"),
    "openai": ("openai", "gpt-4o"),
    "anthropic": ("anthropic", "claude-sonnet-4-5"),
    "kimi": ("moonshot", "kimi-k2.5"),
    "glm5": ("glm5", "glm-4-flash"),
}

# Mona provider -> env var name for API key (written to ~/.openclaw/.env)
PROVIDER_ENV_KEY: dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "glm5": "GLM_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

GATEWAY_TOKEN_PATH = Path("/opt/openclaw/state/gateway-token.txt")
LLM_PROVIDER_PATH = Path("/opt/openclaw/state/llm-provider.json")


def _real_user() -> str:
    """Real user when running under sudo."""
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"


def _real_user_home() -> Path:
    """Home directory of the real user (for ~/.openclaw)."""
    user = _real_user()
    return Path(f"/Users/{user}")


def _openclaw_state_dir() -> Path:
    return _real_user_home() / ".openclaw"


def sync_openclaw_env(llm_config: dict) -> None:
    """Write ~/.openclaw/.env with gateway token and API keys from llm_config."""
    state_dir = _openclaw_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    env_path = state_dir / ".env"

    # Gateway token (required for Mona Hub to talk to gateway)
    gateway_token = ""
    if GATEWAY_TOKEN_PATH.exists():
        try:
            gateway_token = GATEWAY_TOKEN_PATH.read_text().strip()
        except OSError:
            pass
    env_lines = [f"OPENCLAW_GATEWAY_TOKEN={gateway_token}"] if gateway_token else []

    # Merge existing .env: keep lines that are not OPENCLAW_GATEWAY_TOKEN or our API key vars
    our_keys = {"OPENCLAW_GATEWAY_TOKEN"} | set(PROVIDER_ENV_KEY.values())
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    env_lines.append(line)
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    if key not in our_keys:
                        env_lines.append(line)
        except OSError:
            pass

    # API keys from llm_config (api_keys dict or legacy provider/api_key)
    api_keys = llm_config.get("api_keys", {})
    if not api_keys and llm_config.get("provider") and llm_config.get("api_key"):
        api_keys = {llm_config["provider"]: llm_config["api_key"]}
    for provider, env_name in PROVIDER_ENV_KEY.items():
        val = api_keys.get(provider)
        if val:
            env_lines.append(f"{env_name}={val}")

    env_path.write_text("\n".join(env_lines) + "\n")
    try:
        os.chmod(env_path, 0o600)
        user = _real_user()
        subprocess.run(["chown", user, str(env_path)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pass


def _default_model_for_provider(provider: str) -> str | None:
    """Return OpenClaw 'provider/model' string for the given Mona provider."""
    entry = PROVIDER_TO_OPENCLAW_MODEL.get(provider.lower() if provider else "")
    if not entry:
        return None
    openclaw_provider, model_id = entry
    return f"{openclaw_provider}/{model_id}"


def _ensure_deepseek_provider(config: dict) -> None:
    """Ensure models.providers.deepseek exists so OpenClaw can resolve deepseek/deepseek-chat."""
    if "models" not in config:
        config["models"] = {}
    providers = config["models"].setdefault("providers", {})
    if "deepseek" in providers:
        return
    providers["deepseek"] = {
        "baseUrl": "https://api.deepseek.com",
        "apiKey": {"source": "env", "provider": "default", "id": "DEEPSEEK_API_KEY"},
        "models": [
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat",
                "reasoning": False,
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 128000,
                "maxTokens": 4096,
            }
        ],
    }


def sync_openclaw_default_model(provider: str, llm_config: dict) -> None:
    """Update ~/.openclaw/openclaw.json agents.defaults.model for the given provider."""
    state_dir = _openclaw_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    config_path = state_dir / "openclaw.json"

    default_model = _default_model_for_provider(provider)
    if not default_model:
        return

    # Load existing or minimal structure
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}
    else:
        config = {}

    if "agents" not in config:
        config["agents"] = {}
    if "defaults" not in config["agents"]:
        config["agents"]["defaults"] = {}
    config["agents"]["defaults"]["model"] = default_model
    if "workspace" not in config["agents"]["defaults"]:
        config["agents"]["defaults"]["workspace"] = str(_real_user_home() / "OpenClawWorkspace")

    if provider and provider.lower() == "deepseek":
        _ensure_deepseek_provider(config)

    config_path.write_text(json.dumps(config, indent=2))
    try:
        user = _real_user()
        subprocess.run(["chown", user, str(config_path)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pass


def sync_openclaw_after_llm_save(provider: str | None, api_key: str | None, full_llm_config: dict) -> None:
    """Call after saving LLM config: sync .env and agents.defaults.model to ~/.openclaw."""
    sync_openclaw_env(full_llm_config)
    if provider:
        sync_openclaw_default_model(provider, full_llm_config)


def sync_openclaw_active_model(model_id: str | None) -> None:
    """Sync the active local model to OpenClaw's agents.defaults.model."""
    if not model_id:
        return

    # Only sync if it's a local model (ollama-compatible)
    # We check if it exists in /opt/openclaw/models
    models_path = Path("/opt/openclaw/models")
    if not (models_path / model_id).exists():
        return

    state_dir = _openclaw_state_dir()
    config_path = state_dir / "openclaw.json"

    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}
    else:
        config = {}

    if "agents" not in config:
        config["agents"] = {}
    if "defaults" not in config["agents"]:
        config["agents"]["defaults"] = {}
    
    # Set to ollama/model_id as per OpenClaw convention for local MLX models
    config["agents"]["defaults"]["model"] = f"ollama/{model_id}"

    config_path.write_text(json.dumps(config, indent=2))
    try:
        user = _real_user()
        subprocess.run(["chown", user, str(config_path)], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pass


def get_default_model_status() -> dict:
    """Return whether OpenClaw has a default model set (for Settings hint)."""
    config_path = _openclaw_state_dir() / "openclaw.json"
    has_default_model = False
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            model = (config.get("agents") or {}).get("defaults", {}).get("model")
            has_default_model = bool(model and isinstance(model, str) and model.strip())
        except (json.JSONDecodeError, OSError):
            pass
    return {"has_default_model": has_default_model}


def restart_gateway() -> None:
    """Stop then start the OpenClaw gateway LaunchAgent so it picks up new config.

    Runs launchctl bootout then bootstrap for the real user's GUI domain.
    Logs failures; does not raise (caller can ignore restart errors).
    """
    user = _real_user()
    user_home = _real_user_home()
    plist_path = user_home / "Library" / "LaunchAgents" / "ai.openclaw.gateway.plist"
    if not plist_path.exists():
        logger.warning("Gateway plist not found at %s", plist_path)
        return
    try:
        uid_result = subprocess.run(
            ["id", "-u", user],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        uid = uid_result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.warning("Could not resolve user uid for gateway restart: %s", e)
        return
    domain = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        capture_output=True,
        timeout=10,
    )
    result = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        err = (result.stderr or b"").decode(errors="replace").strip()
        logger.warning("launchctl bootstrap failed: %s", err or "unknown")
    else:
        logger.info("OpenClaw gateway restarted")
