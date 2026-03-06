"""Whisper-based speech-to-text engine with lazy loading and idle timeout."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.scribe-ai.whisper")

IDLE_TIMEOUT_SECONDS = 300  # 5 minutes

try:
    import mlx_whisper  # type: ignore[import-untyped]

    _HAS_MLX_WHISPER = True
except ImportError:
    mlx_whisper = None  # type: ignore[assignment]
    _HAS_MLX_WHISPER = False
    logger.warning("mlx_whisper not installed — using placeholder transcription")


MODEL_REGISTRY: dict[str, str] = {
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
}


class WhisperEngine:
    """Wraps MLX-Whisper for speech-to-text with lazy model loading."""

    def __init__(self, model_size: str = "small") -> None:
        self._model_size = model_size
        self._model: Any = None
        self._lock = threading.Lock()
        self._last_used: float = 0.0
        self._idle_timer: threading.Timer | None = None

    def load_model(self, model_size: str = "small") -> None:
        with self._lock:
            if self._model is not None and self._model_size == model_size:
                self._touch()
                return

            if self._model is not None:
                self._do_unload()

            self._model_size = model_size
            if _HAS_MLX_WHISPER:
                model_id = MODEL_REGISTRY.get(model_size, MODEL_REGISTRY["small"])
                logger.info("Loading Whisper model: %s (%s)", model_id, model_size)
                self._model = model_id
            else:
                self._model = "mock"

            self._touch()
            logger.info("Whisper model loaded (%s)", model_size)

    def _touch(self) -> None:
        self._last_used = time.monotonic()
        self._schedule_idle_check()

    def _schedule_idle_check(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._idle_timer = threading.Timer(IDLE_TIMEOUT_SECONDS, self._idle_check)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_check(self) -> None:
        with self._lock:
            if self._model is None:
                return
            elapsed = time.monotonic() - self._last_used
            if elapsed >= IDLE_TIMEOUT_SECONDS:
                logger.info("Whisper model idle for %.0fs — unloading", elapsed)
                self._do_unload()
            else:
                self._schedule_idle_check()

    def _ensure_loaded(self) -> None:
        if self._model is None:
            self.load_model(self._model_size)

    def transcribe(self, audio_path: str | Path) -> dict[str, Any]:
        """Transcribe a full audio file and return text + detected language."""
        with self._lock:
            self._ensure_loaded()
            self._touch()

        path = str(Path(audio_path).resolve())

        if _HAS_MLX_WHISPER and self._model != "mock":
            result = mlx_whisper.transcribe(
                path,
                path_or_hf_repo=self._model,
            )
            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language", "en"),
            }

        return {
            "text": "[Transcription unavailable — mlx_whisper not installed]",
            "language": "en",
        }

    def transcribe_chunk(self, audio_bytes: bytes) -> str:
        """Transcribe a raw audio chunk (WAV bytes) and return text."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            result = self.transcribe(tmp_path)
            return result["text"]
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def unload_model(self) -> None:
        with self._lock:
            self._do_unload()

    def _do_unload(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        self._model = None
        logger.info("Whisper model unloaded")
