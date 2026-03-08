"""Voice service with real local TTS and STT inference."""
import io
import os
import struct
import logging
from pathlib import Path

# Suppress misleading transformers warnings about Mistral regex when loading Qwen3-TTS
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logger = logging.getLogger(__name__)

WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
TTS_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
WHISPER_LOCAL = Path("/opt/openclaw/models/whisper-large-v3-turbo")
TTS_LOCAL = Path("/opt/openclaw/models/qwen3_tts")

LANGUAGE_MAP = {
    "en": {"lang_code": "en"},
    "yue": {"lang_code": "zh"},
    "cmn": {"lang_code": "zh"},
}

_tts_model = None


def _get_tts_model():
    global _tts_model
    if _tts_model is None:
        try:
            from mlx_audio.tts.utils import load_model
            # Prefer local path if it has valid weights, otherwise use HF repo ID
            # which mlx-audio resolves via its own cache and knows the correct architecture.
            if TTS_LOCAL.exists() and any(TTS_LOCAL.glob("*.safetensors")):
                model_id = str(TTS_LOCAL)
            else:
                model_id = TTS_MODEL
            _tts_model = load_model(model_id)
            logger.info("TTS model loaded: %s", model_id)
        except ImportError:
            logger.warning("mlx_audio not installed")
            raise
    return _tts_model


def _samples_to_wav(samples_list: list, sample_rate: int = 24000) -> bytes:
    """Convert raw float32 audio samples to WAV bytes."""
    import numpy as np
    all_samples = np.concatenate(samples_list) if len(samples_list) > 1 else samples_list[0]
    if hasattr(all_samples, 'tolist'):
        all_samples = all_samples.flatten()
    pcm = (all_samples * 32767).astype(np.int16)
    buf = io.BytesIO()
    data_size = len(pcm) * 2
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(pcm.tobytes())
    return buf.getvalue()


def _generate_silent_wav(duration_seconds: float = 0.5, sample_rate: int = 22050) -> bytes:
    """Fallback: generate a minimal silent WAV."""
    num_samples = int(sample_rate * duration_seconds)
    data_size = num_samples * 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(b"\x00" * data_size)
    return buf.getvalue()


def transcribe(audio_path: str) -> dict:
    """Transcribe audio file using mlx-whisper."""
    try:
        import mlx_whisper
        model_path = str(WHISPER_LOCAL) if WHISPER_LOCAL.exists() else WHISPER_MODEL
        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=model_path,
            condition_on_previous_text=False,
        )
        return {"text": result.get("text", "").strip(), "language": result.get("language", "en")}
    except ImportError:
        logger.warning("mlx_whisper not installed, returning placeholder")
        return {"text": "[Speech-to-text not available — mlx-whisper not installed]", "language": "en"}
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        return {"text": f"[Transcription error: {e}]", "language": "en"}


def synthesize(text: str, language: str = "en") -> bytes:
    """Synthesize speech from text using Qwen3-TTS."""
    try:
        model = _get_tts_model()
        lang_config = LANGUAGE_MAP.get(language, LANGUAGE_MAP["en"])
        audio_samples = []
        for result in model.generate(text, **lang_config):
            audio_samples.append(result.audio)
        if not audio_samples:
            return _generate_silent_wav()
        return _samples_to_wav(audio_samples)
    except (ImportError, Exception) as e:
        logger.warning("TTS synthesis failed, returning silent audio: %s", e)
        return _generate_silent_wav()


def get_voice_status() -> dict:
    """Check availability of voice models."""
    tts_ready = TTS_LOCAL.exists() or False
    stt_ready = WHISPER_LOCAL.exists() or False

    try:
        import mlx_whisper  # noqa: F401
        stt_ready = stt_ready and True
    except ImportError:
        stt_ready = False

    try:
        from mlx_audio.tts.utils import load_model  # noqa: F401
        tts_ready = tts_ready and True
    except ImportError:
        tts_ready = False

    if tts_ready and stt_ready:
        msg = "Voice models ready — fully offline"
    elif tts_ready or stt_ready:
        msg = f"Partial voice: TTS={'ready' if tts_ready else 'unavailable'}, STT={'ready' if stt_ready else 'unavailable'}"
    else:
        msg = "Voice models not available"

    return {"tts_ready": tts_ready, "stt_ready": stt_ready, "message": msg}
