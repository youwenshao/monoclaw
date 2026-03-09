import json
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.onboarding_state import (
    ActiveModelUpdate,
    InstalledModel,
    InstalledTool,
    LlmConfigUpdate,
    MessagingConfigUpdate,
    RoutingModeUpdate,
    SystemInfo,
    ValidateKeyRequest,
    ValidateKeyResponse,
    VoiceToggleUpdate,
)
from backend.services import mac_config, messaging
from backend.services.interaction import interaction_manager
from backend.services.llm import llm_service
from backend.services import profile
from backend.services import openclaw_config

router = APIRouter(prefix="/api/system", tags=["system"])

LLM_CONFIG_PATH = Path("/opt/openclaw/state/llm-provider.json")
CLAWHUB_SKILLS_PATH = Path("/opt/openclaw/skills/clawhub")


class ComputerNameUpdate(BaseModel):
    name: str


class AppearanceUpdate(BaseModel):
    mode: str


class OpenSettingsRequest(BaseModel):
    panel: str


@router.get("/info", response_model=SystemInfo)
async def system_info():
    try:
        info = mac_config.get_system_info()
        return SystemInfo(**info)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/computer-name")
async def set_computer_name(body: ComputerNameUpdate):
    success = mac_config.set_computer_name(body.name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set computer name")
    return {"success": True, "name": body.name}


@router.put("/appearance")
async def set_appearance(body: AppearanceUpdate):
    if body.mode not in ("light", "dark", "auto"):
        raise HTTPException(status_code=422, detail="Mode must be 'light', 'dark', or 'auto'")
    success = mac_config.set_appearance(body.mode)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to set appearance")
    return {"success": True, "mode": body.mode}


@router.post("/open-settings")
async def open_settings(body: OpenSettingsRequest):
    success = mac_config.open_system_settings(body.panel)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to open System Settings")
    return {"success": True, "panel": body.panel}


@router.get("/installed-tools", response_model=list[InstalledTool])
async def installed_tools():
    return mac_config.get_installed_tools()


@router.get("/models", response_model=list[InstalledModel])
async def installed_models():
    return mac_config.get_installed_models()


# --- Key Validation ---

_VALIDATION_HANDLERS = {
    "deepseek": lambda creds: ("GET", "https://api.deepseek.com/models", {"Authorization": f"Bearer {creds.get('api_key', '')}"}),
    "kimi": lambda creds: ("GET", "https://api.moonshot.cn/v1/models", {"Authorization": f"Bearer {creds.get('api_key', '')}"}),
    "glm5": lambda creds: ("GET", "https://open.bigmodel.cn/api/paas/v4/models", {"Authorization": f"Bearer {creds.get('api_key', '')}"}),
    "telegram": lambda creds: ("GET", f"https://api.telegram.org/bot{creds.get('token', '')}/getMe", {}),
    "discord": lambda creds: ("GET", "https://discord.com/api/v10/users/@me", {"Authorization": f"Bot {creds.get('token', '')}"}),
}


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_key(req: ValidateKeyRequest):
    provider = req.provider.lower()

    if provider == "whatsapp":
        sid = req.credentials.get("account_sid", "")
        token = req.credentials.get("auth_token", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}",
                    auth=(sid, token),
                )
                if resp.status_code < 300:
                    return ValidateKeyResponse(valid=True)
                return ValidateKeyResponse(valid=False, error=f"HTTP {resp.status_code}")
        except Exception as e:
            return ValidateKeyResponse(valid=False, error=str(e))

    handler = _VALIDATION_HANDLERS.get(provider)
    if not handler:
        return ValidateKeyResponse(valid=False, error=f"Unknown provider: {req.provider}")

    method, url, headers = handler(req.credentials)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(method, url, headers=headers)
            if resp.status_code < 300:
                return ValidateKeyResponse(valid=True)
            return ValidateKeyResponse(valid=False, error=f"HTTP {resp.status_code}")
    except Exception as e:
        return ValidateKeyResponse(valid=False, error=str(e))


# --- Model Routing ---

@router.get("/routing-config")
async def get_routing_config():
    return llm_service.get_routing_config()


@router.put("/active-model")
async def set_active_model(body: ActiveModelUpdate):
    try:
        llm_service.set_active_model(body.model_id)
        # Sync to OpenClaw so the gateway uses the selected local model as default
        openclaw_config.sync_openclaw_active_model(body.model_id)
        openclaw_config.restart_gateway()
    except (FileNotFoundError, ImportError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"success": True, "model_id": body.model_id}


@router.put("/routing-mode")
async def set_routing_mode(body: RoutingModeUpdate):
    llm_service.set_routing_mode(body.auto)
    return {"success": True, "auto": body.auto}


# --- Interaction Mode ---

@router.get("/interaction-mode")
async def get_interaction_mode():
    return interaction_manager.get_status()


@router.put("/voice-toggle")
async def toggle_voice(body: VoiceToggleUpdate):
    interaction_manager.set_voice_enabled(body.enabled)
    state = profile.get_onboarding_state()
    state["voice_enabled"] = body.enabled
    profile._write_state(state)
    return {"success": True, "enabled": body.enabled}


# --- Messaging Config ---

@router.get("/messaging-config")
async def get_messaging_config():
    return messaging.get_messaging_config()


@router.put("/messaging-config")
async def save_messaging_config(body: MessagingConfigUpdate):
    messaging.save_messaging_config(body.platform, body.config)
    return {"success": True, "platform": body.platform}


# --- ClawHub Skills ---

@router.get("/clawhub-skills")
async def get_clawhub_skills():
    skills = []
    if not CLAWHUB_SKILLS_PATH.exists():
        return skills
    for entry in sorted(CLAWHUB_SKILLS_PATH.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        manifest: dict = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        skills.append({
            "slug": entry.name,
            "name": manifest.get("name", entry.name),
            "description": manifest.get("description"),
            "version": manifest.get("version"),
        })
    return skills


# --- LLM Config ---

def _read_llm_config() -> dict:
    if LLM_CONFIG_PATH.exists():
        try:
            return json.loads(LLM_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write_llm_config(config: dict):
    LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LLM_CONFIG_PATH.write_text(json.dumps(config, indent=2))


@router.get("/llm-config")
async def get_llm_config():
    return _read_llm_config()


@router.get("/default-model-status")
async def get_default_model_status():
    """Return whether a default model is set and gateway is healthy (for Settings hint)."""
    status = openclaw_config.get_default_model_status()
    status["gateway_healthy"] = llm_service._check_gateway_health()
    if not status["has_default_model"]:
        status["message"] = "Add an API key below to set a default model for chat, or ensure local models are available."
    elif not status["gateway_healthy"]:
        status["message"] = "OpenClaw gateway is not responding. Restart the gateway or try again later."
    return status


@router.put("/llm-config")
async def save_llm_config(body: LlmConfigUpdate):
    config = _read_llm_config()
    # Preserve provisioner-written structure: api_keys map, default_provider, offline_mode, etc.
    if "api_keys" not in config or not isinstance(config.get("api_keys"), dict):
        api_keys = {}
        if config.get("provider") and config.get("api_key"):
            api_keys[config["provider"]] = config["api_key"]
        config["api_keys"] = api_keys
    api_keys = config["api_keys"]
    if body.provider is not None:
        config["default_provider"] = body.provider
        config["provider"] = body.provider  # legacy flat field for UI
    if body.api_key is not None and body.provider is not None:
        api_keys[body.provider] = body.api_key
        config["api_key"] = body.api_key  # legacy flat field for UI
    _write_llm_config(config)
    # Sync to OpenClaw so the gateway has a working default model
    try:
        openclaw_config.sync_openclaw_after_llm_save(
            body.provider, body.api_key, config
        )
        openclaw_config.restart_gateway()
    except Exception:
        pass  # do not fail the request if sync fails (e.g. permissions)
    return {"success": True}
