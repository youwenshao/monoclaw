from pydantic import BaseModel, Field


class ProfileData(BaseModel):
    name: str
    language_pref: str = "en"
    communication_style: str = "balanced"
    role: str | None = None


class OnboardingState(BaseModel):
    phase: int = 0
    step: int = 0
    completed_phases: list[int] = Field(default_factory=list)
    profile: ProfileData | None = None
    voice_enabled: bool = True
    onboarding_completed: bool = False
    created_at: str = ""
    updated_at: str = ""


class ChatMessage(BaseModel):
    message: str
    conversation_id: str | None = None
    model_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


class STTResponse(BaseModel):
    text: str
    language: str


class SystemInfo(BaseModel):
    computer_name: str
    username: str
    macos_version: str
    hardware: str


class ProgressUpdate(BaseModel):
    phase: int
    step: int
    completed: bool = True


class InstalledTool(BaseModel):
    slug: str
    name: str
    description: str | None = None
    tools: list[str] = Field(default_factory=list)


class InstalledModel(BaseModel):
    model_id: str
    name: str
    category: str | None = None
    size_bytes: int | None = None


class ValidateKeyRequest(BaseModel):
    provider: str
    credentials: dict


class ValidateKeyResponse(BaseModel):
    valid: bool
    error: str | None = None


class ActiveModelUpdate(BaseModel):
    model_id: str


class RoutingModeUpdate(BaseModel):
    auto: bool


class VoiceToggleUpdate(BaseModel):
    enabled: bool


class MessagingConfigUpdate(BaseModel):
    platform: str
    config: dict


class LlmConfigUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = None
