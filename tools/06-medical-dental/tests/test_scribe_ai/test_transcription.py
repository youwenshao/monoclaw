"""Tests for language detection, Cantonese post-processing, and Whisper engine."""

from unittest.mock import patch

from medical_dental.scribe_ai.transcription.language_detect import (
    detect_language,
    post_process_cantonese,
)
from medical_dental.scribe_ai.transcription.whisper_engine import WhisperEngine


def test_language_detect_english():
    assert detect_language("Patient complains of sore throat for 3 days") == "en"


def test_language_detect_chinese():
    assert detect_language("病人投訴喉嚨痛三天") == "zh"


def test_language_detect_mixed():
    text = "病人投訴頭痛同喉嚨痛 fever for three days"
    result = detect_language(text)
    assert result == "mixed"


def test_cantonese_post_processing():
    text = "病人話血壓高，同埋有糖尿"
    result = post_process_cantonese(text)
    assert "高血壓" in result
    assert "糖尿病" in result


def test_whisper_engine_mock():
    engine = WhisperEngine(model_size="small")
    engine.load_model()

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"\x00" * 1000)
        tmp_path = f.name

    try:
        result = engine.transcribe(tmp_path)
        assert "text" in result
        assert "language" in result
        assert isinstance(result["text"], str)
        assert isinstance(result["language"], str)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        engine.unload_model()
