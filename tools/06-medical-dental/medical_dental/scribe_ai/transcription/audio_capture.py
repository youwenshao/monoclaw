"""Audio capture utility for recording consultation audio to WAV files."""

from __future__ import annotations

import logging
import struct
import threading
import time
from pathlib import Path

logger = logging.getLogger("openclaw.scribe-ai.audio")

try:
    import soundfile as sf  # type: ignore[import-untyped]

    _HAS_SOUNDFILE = True
except ImportError:
    sf = None  # type: ignore[assignment]
    _HAS_SOUNDFILE = False
    logger.warning("soundfile not installed — audio capture will use silent stubs")

SAMPLE_RATE = 16000
CHANNELS = 1


class AudioCapture:
    """Records audio to temporary WAV files in the workspace."""

    def __init__(self, workspace: str | Path) -> None:
        self._workspace = Path(workspace)
        self._audio_dir = self._workspace / "audio"
        self._audio_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._frames: list[bytes] = []
        self._lock = threading.Lock()
        self._current_level: float = 0.0
        self._current_path: Path | None = None

    def start(self) -> Path:
        """Begin recording audio. Returns the path where the WAV will be saved."""
        with self._lock:
            if self._recording:
                raise RuntimeError("Recording already in progress")

            timestamp = int(time.time() * 1000)
            self._current_path = self._audio_dir / f"recording_{timestamp}.wav"
            self._frames = []
            self._recording = True
            self._current_level = 0.0

        logger.info("Audio recording started: %s", self._current_path)
        return self._current_path

    def feed(self, audio_data: bytes) -> None:
        """Feed raw PCM audio data (16-bit mono 16kHz) into the recorder."""
        with self._lock:
            if not self._recording:
                return
            self._frames.append(audio_data)
            self._current_level = self._compute_level(audio_data)

    def stop(self) -> Path:
        """Stop recording and write the WAV file. Returns path to the file."""
        with self._lock:
            if not self._recording:
                raise RuntimeError("No recording in progress")

            self._recording = False
            output_path = self._current_path
            frames = b"".join(self._frames)
            self._frames = []

        if output_path is None:
            raise RuntimeError("No output path set")

        self._write_wav(output_path, frames)
        logger.info("Audio recording saved: %s (%d bytes)", output_path, len(frames))
        return output_path

    def get_level(self) -> float:
        """Return the current audio level as a float from 0.0 to 1.0."""
        with self._lock:
            return self._current_level

    def cleanup(self) -> int:
        """Delete all audio files in the workspace audio directory. Returns count deleted."""
        deleted = 0
        if self._audio_dir.exists():
            for wav_file in self._audio_dir.glob("*.wav"):
                wav_file.unlink(missing_ok=True)
                deleted += 1
        logger.info("Cleaned up %d audio files from %s", deleted, self._audio_dir)
        return deleted

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    @staticmethod
    def _compute_level(audio_data: bytes) -> float:
        """Compute RMS level of 16-bit PCM data, normalized to 0.0-1.0."""
        if len(audio_data) < 2:
            return 0.0
        n_samples = len(audio_data) // 2
        samples = struct.unpack(f"<{n_samples}h", audio_data[: n_samples * 2])
        rms = (sum(s * s for s in samples) / n_samples) ** 0.5
        return min(rms / 32768.0, 1.0)

    @staticmethod
    def _write_wav(path: Path, pcm_data: bytes) -> None:
        """Write raw 16-bit mono PCM data as a WAV file."""
        if _HAS_SOUNDFILE:
            import numpy as np

            n_samples = len(pcm_data) // 2
            if n_samples == 0:
                audio_array = np.array([], dtype=np.int16)
            else:
                audio_array = np.frombuffer(pcm_data[:n_samples * 2], dtype=np.int16)
            sf.write(str(path), audio_array, SAMPLE_RATE)
        else:
            import wave

            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(pcm_data)
