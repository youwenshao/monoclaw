import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.models.onboarding_state import STTResponse, TTSRequest
from backend.services import voice
from backend.services.interaction import InteractionMode, interaction_manager

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    if req.language not in ("en", "yue", "cmn"):
        raise HTTPException(status_code=422, detail="Supported languages: en, yue, cmn")

    acquired = await interaction_manager.acquire(InteractionMode.VOICE_SPEAKING)
    if not acquired:
        raise HTTPException(status_code=409, detail="Another interaction is in progress")

    try:
        wav_bytes = voice.synthesize(req.text, req.language)
    finally:
        await interaction_manager.release()

    return StreamingResponse(
        io.BytesIO(wav_bytes),
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=speech.wav"},
    )


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(file: UploadFile):
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=422, detail="Uploaded file must be an audio file")

    acquired = await interaction_manager.acquire(InteractionMode.VOICE_LISTENING)
    if not acquired:
        raise HTTPException(status_code=409, detail="Another interaction is in progress")

    try:
        audio_data = await file.read()
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        result = voice.transcribe(tmp_path)

        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
    finally:
        await interaction_manager.release()

    return STTResponse(text=result["text"], language=result["language"])


@router.get("/status")
async def voice_status():
    return voice.get_voice_status()
