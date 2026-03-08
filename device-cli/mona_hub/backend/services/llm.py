"""LLM service with local mlx-lm inference, cloud API fallback, model routing, and streaming."""
import json
import logging
import threading
from pathlib import Path
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

MODELS_PATH = Path("/opt/openclaw/models")
ROUTING_CONFIG_PATH = Path("/opt/openclaw/state/routing-config.json")
ACTIVE_WORK_PATH = Path("/opt/openclaw/state/active-work.json")
LLM_CONFIG_PATH = Path("/opt/openclaw/state/llm-provider.json")

VOICE_MODEL_DIRS = {"whisper-large-v3-turbo", "qwen3_tts", "qwen3-tts"}

CLOUD_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "name": "DeepSeek",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-128k",
        "name": "Kimi (Moonshot)",
    },
    "glm5": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "name": "GLM-5 (Zhipu)",
    },
}

CLOUD_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


class CloudAPIError(Exception):
    """Raised when a cloud API call fails with an actionable user message."""


def _cloud_error_message(provider_name: str, status_code: int, body: str) -> str:
    if status_code == 401:
        return f"Your {provider_name} API key was rejected (HTTP 401). Please check the key in the API Keys section."
    if status_code == 402:
        return f"Your {provider_name} account has insufficient credits (HTTP 402). Please top up your balance."
    if status_code == 429:
        return f"{provider_name} rate limit reached (HTTP 429). Please wait a moment and try again."
    if 500 <= status_code < 600:
        return f"{provider_name} servers returned an error (HTTP {status_code}). Please try again later."
    return f"{provider_name} returned an unexpected error (HTTP {status_code}): {body[:200]}"


class LLMService:
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._active_model_id: str | None = None
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._routing_config = self._load_json(ROUTING_CONFIG_PATH)
        self._active_work = self._load_json(ACTIVE_WORK_PATH)

    @staticmethod
    def _load_json(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _get_cloud_config(self) -> tuple[str | None, str | None]:
        """Read the LLM provider config fresh (may change during onboarding)."""
        config = self._load_json(LLM_CONFIG_PATH)
        provider = config.get("provider")
        api_key = config.get("api_key")
        if provider and api_key:
            return provider, api_key
        return None, None

    @staticmethod
    def _build_cloud_messages(prompt: str, system_prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def get_available_models(self) -> list[dict]:
        """List all LLM models (excluding voice models)."""
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
        provider, api_key = self._get_cloud_config()
        cloud_info = None
        if provider and provider in CLOUD_PROVIDERS:
            cloud_info = {
                "provider": provider,
                "provider_name": CLOUD_PROVIDERS[provider]["name"],
                "model": CLOUD_PROVIDERS[provider]["model"],
                "configured": bool(api_key),
            }
        return {
            "auto_routing_enabled": self._routing_config.get("auto_routing_enabled", False),
            "routes": self._routing_config.get("routes", {}),
            "active_model_id": self._active_model_id,
            "available_models": self.get_available_models(),
            "cloud_provider": cloud_info,
        }

    def load_model(self, model_id: str):
        with self._lock:
            if model_id == self._active_model_id and self._model is not None:
                return
            self._model = None
            self._tokenizer = None
            self._active_model_id = None

            model_path = MODELS_PATH / model_id
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found: {model_id}")
            try:
                from mlx_lm import load
                self._model, self._tokenizer = load(str(model_path))
                self._active_model_id = model_id
                logger.info("Loaded model: %s", model_id)
            except ImportError:
                logger.warning("mlx_lm not installed, falling back to demo mode")
                raise

    def select_model(self, model_id: str | None = None, complexity: str | None = None) -> str:
        if model_id:
            self.load_model(model_id)
            return model_id
        if self._routing_config.get("auto_routing_enabled"):
            routes = self._routing_config.get("routes", {})
            candidates = routes.get(complexity or "moderate", [])
            if candidates:
                chosen = candidates[0]
                self.load_model(chosen)
                return chosen
        if self._active_model_id and self._model is not None:
            return self._active_model_id
        available = self.get_available_models()
        if available:
            first = available[0]["model_id"]
            self.load_model(first)
            return first
        raise RuntimeError("No local models available")

    def set_active_model(self, model_id: str):
        self.load_model(model_id)

    def set_routing_mode(self, auto: bool):
        self._routing_config["auto_routing_enabled"] = auto

    # ---- Cloud API methods ----

    async def _generate_cloud(
        self, prompt: str, system_prompt: str, max_tokens: int, provider: str, api_key: str,
    ) -> str:
        prov = CLOUD_PROVIDERS[provider]
        url = f"{prov['base_url']}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": prov["model"],
            "messages": self._build_cloud_messages(prompt, system_prompt),
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=CLOUD_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.ConnectError:
            raise CloudAPIError(f"Cannot reach {prov['name']} servers. Check your internet connection.")
        except httpx.TimeoutException:
            raise CloudAPIError(f"Request to {prov['name']} timed out. Please try again.")

        if resp.status_code != 200:
            raise CloudAPIError(_cloud_error_message(prov["name"], resp.status_code, resp.text))

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise CloudAPIError(f"Unexpected response format from {prov['name']}: {e}")

    async def _generate_cloud_stream(
        self, prompt: str, system_prompt: str, max_tokens: int, provider: str, api_key: str,
    ) -> AsyncGenerator[str, None]:
        prov = CLOUD_PROVIDERS[provider]
        url = f"{prov['base_url']}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": prov["model"],
            "messages": self._build_cloud_messages(prompt, system_prompt),
            "max_tokens": max_tokens,
            "stream": True,
        }

        self._abort.clear()
        try:
            async with httpx.AsyncClient(timeout=CLOUD_TIMEOUT) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        body = ""
                        async for chunk in resp.aiter_text():
                            body += chunk
                            if len(body) > 500:
                                break
                        raise CloudAPIError(
                            _cloud_error_message(prov["name"], resp.status_code, body)
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
            raise CloudAPIError(f"Cannot reach {prov['name']} servers. Check your internet connection.")
        except httpx.TimeoutException:
            raise CloudAPIError(f"Request to {prov['name']} timed out. Please try again.")

    # ---- Unified generate methods ----

    async def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 512, model_id: str | None = None, complexity: str | None = None) -> str:
        """Non-streaming generation. Tries local models first, falls back to cloud."""
        try:
            self.select_model(model_id=model_id, complexity=complexity)
        except (ImportError, RuntimeError, FileNotFoundError):
            provider, api_key = self._get_cloud_config()
            if provider and api_key and provider in CLOUD_PROVIDERS:
                return await self._generate_cloud(prompt, system_prompt, max_tokens, provider, api_key)
            raise CloudAPIError(
                "No LLM is available. Please set up an API key in the API Keys section, "
                "or ensure a local model is installed."
            )

        try:
            from mlx_lm import generate
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            output = generate(self._model, self._tokenizer, prompt=full_prompt, max_tokens=max_tokens)
            return output
        except Exception as e:
            logger.error("Generation failed: %s", e)
            raise CloudAPIError(f"Local model inference failed: {e}")

    async def generate_stream(self, prompt: str, system_prompt: str = "", max_tokens: int = 512, model_id: str | None = None, complexity: str | None = None) -> AsyncGenerator[str, None]:
        """Streaming generation. Tries local models first, falls back to cloud."""
        use_cloud = False
        try:
            self.select_model(model_id=model_id, complexity=complexity)
        except (ImportError, RuntimeError, FileNotFoundError):
            provider, api_key = self._get_cloud_config()
            if provider and api_key and provider in CLOUD_PROVIDERS:
                use_cloud = True
            else:
                raise CloudAPIError(
                    "No LLM is available. Please set up an API key in the API Keys section, "
                    "or ensure a local model is installed."
                )

        if use_cloud:
            async for token in self._generate_cloud_stream(prompt, system_prompt, max_tokens, provider, api_key):
                yield token
            return

        self._abort.clear()
        try:
            from mlx_lm import stream_generate
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            for token_text in stream_generate(self._model, self._tokenizer, prompt=full_prompt, max_tokens=max_tokens):
                if self._abort.is_set():
                    break
                yield token_text
        except Exception as e:
            logger.error("Stream generation failed: %s", e)
            raise CloudAPIError(f"Local model inference failed: {e}")

    def abort_generation(self):
        self._abort.set()

    def get_model_status(self) -> dict:
        if self._active_model_id and self._model is not None:
            return {"status": "ready", "model": self._active_model_id, "message": f"Model {self._active_model_id} loaded and ready"}
        provider, api_key = self._get_cloud_config()
        if provider and api_key and provider in CLOUD_PROVIDERS:
            name = CLOUD_PROVIDERS[provider]["name"]
            return {"status": "cloud", "model": None, "message": f"Using {name} cloud API"}
        available = self.get_available_models()
        if available:
            return {"status": "idle", "model": None, "message": f"{len(available)} model(s) available, none loaded yet"}
        return {"status": "no_models", "model": None, "message": "No local models found and no cloud API configured"}


llm_service = LLMService()
