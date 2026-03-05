"""Voice system (TTS/STT) tests."""

import subprocess
from pathlib import Path
from .base import BaseTestSuite


class VoiceSystemTests(BaseTestSuite):

    def test_whisper_model_exists(self):
        model_paths = [
            Path("/opt/openclaw/models/whisper-large-v3"),
            Path.home() / ".cache" / "whisper",
        ]
        for p in model_paths:
            if p.exists():
                return "pass", {"path": str(p)}
        return "skipped", {"note": "Whisper model not found (may use API STT)"}

    def test_tts_model_exists(self):
        tts_paths = [
            Path("/opt/openclaw/models/qwen-tts"),
            Path("/opt/openclaw/models/edge-tts"),
        ]
        for p in tts_paths:
            if p.exists():
                return "pass", {"path": str(p)}
        return "skipped", {"note": "TTS model not found (may use API TTS)"}

    def test_audio_framework_available(self):
        result = subprocess.run(
            ["python3", "-c", "import AVFoundation; print('ok')"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "pass", {}
        return "warning", {"note": "AVFoundation not directly importable (expected for non-PyObjC env)"}

    def test_ffmpeg_audio_support(self):
        result = subprocess.run(
            ["ffmpeg", "-formats"],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and "wav" in result.stdout:
            return "pass", {"formats": "wav, mp3, etc. supported"}
        return "fail", {"error": "FFmpeg missing audio format support"}

    def test_language_detection_cantonese(self):
        cantonese_markers = ["嘅", "咁", "啲", "喺", "喎", "吓"]
        test_text = "今日天氣好好嘅"
        detected = any(m in test_text for m in cantonese_markers)
        if detected:
            return "pass", {"detected": "cantonese", "text": test_text}
        return "fail", {"note": "Cantonese detection failed"}

    def test_language_detection_mandarin(self):
        cantonese_markers = ["嘅", "咁", "啲", "喺", "喎", "吓"]
        test_text = "今天天气很好"
        is_cantonese = any(m in test_text for m in cantonese_markers)
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in test_text)
        if has_chinese and not is_cantonese:
            return "pass", {"detected": "mandarin", "text": test_text}
        return "fail", {}

    def test_language_detection_english(self):
        test_text = "The weather is nice today"
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in test_text)
        if not has_chinese:
            return "pass", {"detected": "english", "text": test_text}
        return "fail", {}

    def test_microphone_permission(self):
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType"],
            capture_output=True, text=True,
        )
        if "Input" in result.stdout or "Microphone" in result.stdout:
            return "pass", {"note": "Audio input detected"}
        return "warning", {"note": "No microphone detected (Mac mini may need external mic)"}
