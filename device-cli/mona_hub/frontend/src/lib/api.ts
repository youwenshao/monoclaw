export interface OnboardingState {
  phase: number;
  step: number;
  completed_phases: number[];
  profile: UserProfile | null;
  voice_enabled: boolean;
  onboarding_completed: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  name: string;
  language_pref: string;
  communication_style: string;
  role?: string;
}

export interface SystemInfo {
  computer_name: string;
  username: string;
  macos_version: string;
  hardware: string;
}

export interface ToolInfo {
  slug: string;
  name: string;
  description?: string;
  tools: string[];
}

export interface ModelInfo {
  model_id: string;
  name: string;
  category?: string;
  size_bytes?: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  model_id?: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
}

export interface GuidedTaskResponse {
  response: string;
  conversation_id: string;
}

export interface VoiceStatus {
  tts_ready: boolean;
  stt_ready: boolean;
  message: string;
}

export interface ValidateKeyResponse {
  valid: boolean;
  error?: string;
}

export interface RoutingConfig {
  auto_routing_enabled: boolean;
  routes: Record<string, string[]>;
  active_model_id: string | null;
  available_models: ModelInfo[];
}

export interface InteractionStatus {
  mode: string;
  voice_enabled: boolean;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = path.startsWith("/api/") ? path : `/api/${path.replace(/^\//, "")}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, body);
  }

  return response.json();
}

async function apiFetchBlob(path: string, options?: RequestInit): Promise<Blob> {
  const url = path.startsWith("/api/") ? path : `/api/${path.replace(/^\//, "")}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, body);
  }

  return response.blob();
}

// --- Onboarding ---

export function getOnboardingState(): Promise<OnboardingState> {
  return apiFetch<OnboardingState>("/api/onboarding/state");
}

export function saveProfile(data: Partial<UserProfile>): Promise<OnboardingState> {
  return apiFetch("/api/onboarding/profile", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function updateProgress(
  phase: number,
  step: number,
  completed: boolean,
): Promise<OnboardingState> {
  return apiFetch("/api/onboarding/progress", {
    method: "PUT",
    body: JSON.stringify({ phase, step, completed }),
  });
}

export function completeOnboarding(): Promise<OnboardingState> {
  return apiFetch("/api/onboarding/complete", { method: "POST" });
}

// --- System ---

export function getSystemInfo(): Promise<SystemInfo> {
  return apiFetch<SystemInfo>("/api/system/info");
}

export function setComputerName(name: string): Promise<{ success: boolean }> {
  return apiFetch("/api/system/computer-name", {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}

export function setAppearance(mode: "light" | "dark" | "auto"): Promise<{ success: boolean }> {
  return apiFetch("/api/system/appearance", {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
}

export function openSettings(panel: string): Promise<{ success: boolean }> {
  return apiFetch("/api/system/open-settings", {
    method: "POST",
    body: JSON.stringify({ panel }),
  });
}

export function getInstalledTools(): Promise<ToolInfo[]> {
  return apiFetch<ToolInfo[]>("/api/system/installed-tools");
}

export function getInstalledModels(): Promise<ModelInfo[]> {
  return apiFetch<ModelInfo[]>("/api/system/models");
}

export function validateKey(
  provider: string,
  credentials: Record<string, string>,
): Promise<ValidateKeyResponse> {
  return apiFetch<ValidateKeyResponse>("/api/system/validate-key", {
    method: "POST",
    body: JSON.stringify({ provider, credentials }),
  });
}

export function getRoutingConfig(): Promise<RoutingConfig> {
  return apiFetch<RoutingConfig>("/api/system/routing-config");
}

export function setActiveModel(modelId: string): Promise<{ success: boolean }> {
  return apiFetch("/api/system/active-model", {
    method: "PUT",
    body: JSON.stringify({ model_id: modelId }),
  });
}

export function setRoutingMode(auto: boolean): Promise<{ success: boolean }> {
  return apiFetch("/api/system/routing-mode", {
    method: "PUT",
    body: JSON.stringify({ auto }),
  });
}

export function getInteractionMode(): Promise<InteractionStatus> {
  return apiFetch<InteractionStatus>("/api/system/interaction-mode");
}

export function toggleVoice(enabled: boolean): Promise<{ success: boolean }> {
  return apiFetch("/api/system/voice-toggle", {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
}

export function getMessagingConfig(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/api/system/messaging-config");
}

export function saveMessagingConfig(
  platform: string,
  config: Record<string, string>,
): Promise<{ success: boolean }> {
  return apiFetch("/api/system/messaging-config", {
    method: "PUT",
    body: JSON.stringify({ platform, config }),
  });
}

export function getClawHubSkills(): Promise<unknown[]> {
  return apiFetch<unknown[]>("/api/system/clawhub-skills");
}

export function getLlmConfig(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/api/system/llm-config");
}

export function saveLlmConfig(
  provider?: string,
  apiKey?: string,
): Promise<{ success: boolean }> {
  return apiFetch("/api/system/llm-config", {
    method: "PUT",
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
}

// --- Chat ---

export function sendChatMessage(
  message: string,
  conversationId?: string,
  modelId?: string,
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>("/api/chat/message", {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      model_id: modelId,
    }),
  });
}

export async function sendChatMessageStream(
  message: string,
  conversationId?: string,
  modelId?: string,
  onToken?: (token: string) => void,
  onDone?: (conversationId: string) => void,
): Promise<void> {
  const response = await fetch("/api/chat/message/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      model_id: modelId,
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "Unknown error");
    throw new ApiError(response.status, body);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.token && onToken) {
          onToken(data.token);
        }
        if (data.done && onDone) {
          onDone(data.conversation_id);
        }
      } catch {
        // skip malformed SSE lines
      }
    }
  }
}

export function abortChatMessage(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/api/chat/message/abort", {
    method: "POST",
  });
}

export function startGuidedTask(
  industry: string,
  taskType: string,
): Promise<GuidedTaskResponse> {
  return apiFetch<GuidedTaskResponse>("/api/chat/guided-task", {
    method: "POST",
    body: JSON.stringify({ industry, task_type: taskType }),
  });
}

// --- Voice ---

export function textToSpeech(text: string, language: string): Promise<Blob> {
  return apiFetchBlob("/api/voice/tts", {
    method: "POST",
    body: JSON.stringify({ text, language }),
  });
}

export function getVoiceStatus(): Promise<VoiceStatus> {
  return apiFetch<VoiceStatus>("/api/voice/status");
}
