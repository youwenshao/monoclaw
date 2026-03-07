"""Manages voice/text interaction modes to prevent conflicts."""
import asyncio
from enum import Enum


class InteractionMode(str, Enum):
    IDLE = "idle"
    TEXT_GENERATING = "text_generating"
    VOICE_LISTENING = "voice_listening"
    VOICE_SPEAKING = "voice_speaking"


class InteractionManager:
    def __init__(self):
        self.mode = InteractionMode.IDLE
        self.voice_enabled = True
        self._lock = asyncio.Lock()

    async def acquire(self, requested_mode: InteractionMode) -> bool:
        async with self._lock:
            if self.mode != InteractionMode.IDLE:
                return False
            if requested_mode in (InteractionMode.VOICE_LISTENING, InteractionMode.VOICE_SPEAKING):
                if not self.voice_enabled:
                    return False
            self.mode = requested_mode
            return True

    async def release(self):
        async with self._lock:
            self.mode = InteractionMode.IDLE

    def set_voice_enabled(self, enabled: bool):
        self.voice_enabled = enabled

    def get_status(self) -> dict:
        return {"mode": self.mode.value, "voice_enabled": self.voice_enabled}


interaction_manager = InteractionManager()
