"""LLM service with real mlx-lm inference, model routing, and streaming."""
import json
import logging
import threading
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

MODELS_PATH = Path("/opt/openclaw/models")
ROUTING_CONFIG_PATH = Path("/opt/openclaw/state/routing-config.json")
ACTIVE_WORK_PATH = Path("/opt/openclaw/state/active-work.json")

VOICE_MODEL_DIRS = {"whisper-large-v3-turbo", "qwen3-tts"}


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
        return {
            "auto_routing_enabled": self._routing_config.get("auto_routing_enabled", False),
            "routes": self._routing_config.get("routes", {}),
            "active_model_id": self._active_model_id,
            "available_models": self.get_available_models(),
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

    async def generate(self, prompt: str, system_prompt: str = "", max_tokens: int = 512, model_id: str | None = None) -> str:
        """Non-streaming generation. Returns full response text."""
        try:
            mid = self.select_model(model_id)
        except (ImportError, RuntimeError, FileNotFoundError) as e:
            return f"I'm not able to process that right now. ({e})"

        try:
            from mlx_lm import generate
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            output = generate(self._model, self._tokenizer, prompt=full_prompt, max_tokens=max_tokens)
            return output
        except Exception as e:
            logger.error("Generation failed: %s", e)
            return "I encountered an error processing that. Please try again."

    async def generate_stream(self, prompt: str, system_prompt: str = "", max_tokens: int = 512, model_id: str | None = None) -> AsyncGenerator[str, None]:
        """Streaming generation. Yields tokens one at a time."""
        try:
            mid = self.select_model(model_id)
        except (ImportError, RuntimeError, FileNotFoundError) as e:
            yield f"I'm not able to process that right now. ({e})"
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
            yield f"[Error: {e}]"

    def abort_generation(self):
        self._abort.set()

    def get_model_status(self) -> dict:
        if self._active_model_id and self._model is not None:
            return {"status": "ready", "model": self._active_model_id, "message": f"Model {self._active_model_id} loaded and ready"}
        available = self.get_available_models()
        if available:
            return {"status": "idle", "model": None, "message": f"{len(available)} model(s) available, none loaded yet"}
        return {"status": "no_models", "model": None, "message": "No local models found"}


llm_service = LLMService()
