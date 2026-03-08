"""LLM service backed by the OpenClaw gateway's OpenAI-compatible API."""
import json
import logging
import threading
from pathlib import Path
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

GATEWAY_URL = "http://127.0.0.1:18789"
GATEWAY_TOKEN_PATH = Path("/opt/openclaw/state/gateway-token.txt")
MODELS_PATH = Path("/opt/openclaw/models")
ROUTING_CONFIG_PATH = Path("/opt/openclaw/state/routing-config.json")
ACTIVE_WORK_PATH = Path("/opt/openclaw/state/active-work.json")
LLM_CONFIG_PATH = Path("/opt/openclaw/state/llm-provider.json")

VOICE_MODEL_DIRS = {"whisper-large-v3-turbo", "qwen3_tts", "qwen3-tts"}

CLOUD_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


class CloudAPIError(Exception):
    """Raised when a gateway or cloud API call fails with an actionable user message."""


class LLMService:
    """Proxies chat requests through the local OpenClaw gateway."""

    def __init__(self):
        self._active_model_id: str | None = None
        self._abort = threading.Event()
        self._routing_config = self._load_json(ROUTING_CONFIG_PATH)
        self._active_work = self._load_json(ACTIVE_WORK_PATH)
        self._cancel_stream: httpx.Response | None = None

    @staticmethod
    def _load_json(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _get_gateway_token(self) -> str:
        try:
            return GATEWAY_TOKEN_PATH.read_text().strip()
        except (OSError, FileNotFoundError):
            return ""

    def _gateway_headers(self) -> dict[str, str]:
        token = self._get_gateway_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_available_models(self) -> list[dict]:
        """List all LLM models from the local models directory (excluding voice)."""
        models = []
        if not MODELS_PATH.exists():
            return models
        for entry in sorted(MODELS_PATH.iterdir()):
            if not entry.is_dir() or entry.name in VOICE_MODEL_DIRS:
                continue
            config_path = entry / "config.json"
            config = {}
            if config_path.exists():
                try:
                    config = json.loads(config_path.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            size_bytes = None
            weight_files = list(entry.glob("*.safetensors")) + list(entry.glob("*.gguf"))
            if weight_files:
                size_bytes = sum(f.stat().st_size for f in weight_files)
            models.append({
                "model_id": entry.name,
                "name": config.get("name", entry.name),
                "category": config.get("category"),
                "size_bytes": size_bytes,
            })
        return models

    def get_routing_config(self) -> dict:
        self._routing_config = self._load_json(ROUTING_CONFIG_PATH)
        return {
            "auto_routing_enabled": self._routing_config.get("auto_routing_enabled", False),
            "routes": self._routing_config.get("routes", {}),
            "active_model_id": self._active_model_id,
            "available_models": self.get_available_models(),
            "cloud_provider": None,
            "gateway": {"url": GATEWAY_URL, "healthy": self._check_gateway_health()},
        }

    def _check_gateway_health(self) -> bool:
        try:
            resp = httpx.get(f"{GATEWAY_URL}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def set_active_model(self, model_id: str):
        self._active_model_id = model_id

    def set_routing_mode(self, auto: bool):
        self._routing_config["auto_routing_enabled"] = auto

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        model_id: str | None = None,
        complexity: str | None = None,
    ) -> str:
        """Non-streaming generation via the OpenClaw gateway."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "openclaw",
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=CLOUD_TIMEOUT) as client:
                resp = await client.post(
                    f"{GATEWAY_URL}/v1/chat/completions",
                    headers=self._gateway_headers(),
                    json=payload,
                )
        except httpx.ConnectError:
            raise CloudAPIError(
                "Cannot connect to the OpenClaw gateway at localhost:18789. "
                "The gateway may still be starting — please try again in a moment."
            )
        except httpx.TimeoutException:
            raise CloudAPIError("Request to OpenClaw gateway timed out. Please try again.")

        if resp.status_code == 401:
            raise CloudAPIError("OpenClaw gateway rejected the authentication token.")
        if resp.status_code != 200:
            raise CloudAPIError(
                f"OpenClaw gateway returned HTTP {resp.status_code}: {resp.text[:300]}"
            )

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise CloudAPIError(f"Unexpected response format from gateway: {e}")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        model_id: str | None = None,
        complexity: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming generation via the OpenClaw gateway (SSE)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "openclaw",
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        self._abort.clear()
        try:
            async with httpx.AsyncClient(timeout=CLOUD_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{GATEWAY_URL}/v1/chat/completions",
                    headers=self._gateway_headers(),
                    json=payload,
                ) as resp:
                    if resp.status_code == 401:
                        raise CloudAPIError("OpenClaw gateway rejected the authentication token.")
                    if resp.status_code != 200:
                        body = ""
                        async for chunk in resp.aiter_text():
                            body += chunk
                            if len(body) > 500:
                                break
                        raise CloudAPIError(
                            f"OpenClaw gateway returned HTTP {resp.status_code}: {body[:300]}"
                        )

                    buffer = ""
                    async for chunk in resp.aiter_text():
                        if self._abort.is_set():
                            break
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except httpx.ConnectError:
            raise CloudAPIError(
                "Cannot connect to the OpenClaw gateway at localhost:18789. "
                "The gateway may still be starting — please try again in a moment."
            )
        except httpx.TimeoutException:
            raise CloudAPIError("Request to OpenClaw gateway timed out. Please try again.")

    def abort_generation(self):
        self._abort.set()

    def get_model_status(self) -> dict:
        if self._check_gateway_health():
            return {
                "status": "ready",
                "model": "openclaw-gateway",
                "message": "OpenClaw gateway is running and accepting requests",
            }
        return {
            "status": "offline",
            "model": None,
            "message": "OpenClaw gateway is not responding at localhost:18789",
        }


llm_service = LLMService()
