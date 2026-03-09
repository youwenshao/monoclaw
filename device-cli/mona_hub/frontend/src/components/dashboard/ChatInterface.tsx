import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type KeyboardEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSearchParams, useParams, useNavigate } from "react-router-dom";
import { Orb, NeuCard, NeuButton, NeuInput, ModelSelector, StopButton, VoiceToggle } from "@/components/ui";
import { useChat } from "@/hooks/useChat";
import { useVoice } from "@/hooks/useVoice";
import {
  getRoutingConfig,
  setActiveModel,
  setRoutingMode,
  getChatTools,
  toggleVoice as toggleVoiceApi,
  type ToolInfo,
  type RoutingConfig,
} from "@/lib/api";
import { childVariants } from "@/lib/animations";
import type { ChatMessage } from "@/lib/api";

function SendIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function MicIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="9" y="1" width="6" height="12" rx="3" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
    </svg>
  );
}

function ToolSelector({
  tools,
  activeTool,
  onSelect,
}: {
  tools: ToolInfo[];
  activeTool: string | null;
  onSelect: (slug: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  const activeToolInfo = tools.find((t) => t.slug === activeTool);
  const displayName = activeToolInfo ? activeToolInfo.name : "All tools";

  return (
    <div ref={containerRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 font-sans text-sm font-medium text-text-secondary border-0 cursor-pointer select-none"
        style={{
          height: 36,
          paddingLeft: 14,
          paddingRight: 14,
          borderRadius: 9999,
          background: "var(--surface-raised)",
          boxShadow: "4px 4px 8px var(--shadow-dark), -4px -4px 8px var(--shadow-light)",
          transition: "box-shadow 200ms ease-out",
          minHeight: 44,
          minWidth: 44,
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="h-3.5 w-3.5">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
        </svg>
        <span className="hidden sm:inline">{displayName}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className="transition-transform" style={{ transform: open ? "rotate(180deg)" : "rotate(0)" }}>
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute bottom-full mb-2 left-0 z-50"
            style={{ minWidth: 240, maxHeight: 320, overflowY: "auto" }}
          >
            <NeuCard variant="raised" padding="sm" radius="md">
              <div className="flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => { onSelect(null); setOpen(false); }}
                  className="flex items-center w-full px-3 py-2 rounded-lg text-sm font-sans border-0 cursor-pointer text-left transition-colors hover:bg-surface-inset"
                  style={{
                    background: activeTool === null ? "var(--surface-inset)" : "transparent",
                    boxShadow: activeTool === null
                      ? "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)"
                      : "none",
                    color: "var(--text-primary)",
                    minHeight: 44,
                  }}
                >
                  Auto-detect tool
                </button>
                <div className="my-1" style={{ height: 1, background: "var(--surface-inset)" }} />
                {tools.map((tool) => {
                  const isActive = tool.slug === activeTool;
                  return (
                    <button
                      key={tool.slug}
                      type="button"
                      onClick={() => { onSelect(tool.slug); setOpen(false); }}
                      className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm font-sans border-0 cursor-pointer text-left transition-colors hover:bg-surface-inset"
                      style={{
                        background: isActive ? "var(--surface-inset)" : "transparent",
                        boxShadow: isActive
                          ? "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)"
                          : "none",
                        color: "var(--text-primary)",
                        minHeight: 40,
                      }}
                    >
                      <span className="truncate">{tool.name}</span>
                      <span className="flex-shrink-0 text-xs text-text-tertiary ml-2">
                        {tool.tools.length} tools
                      </span>
                    </button>
                  );
                })}
              </div>
            </NeuCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ChatInterface() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { conversationId: routeConvId } = useParams();
  const navigate = useNavigate();

  const [lastConvId, setLastConvId] = useState<string | null>(() => localStorage.getItem("last_conversation_id"));

  // Determine the actual conversation ID to use
  const activeConvId = routeConvId || lastConvId || undefined;

  const {
    messages,
    sendMessageStream,
    abortGeneration,
    isLoading,
    isStreaming,
    conversationId: currentConvId,
  } = useChat(activeConvId === "new" ? undefined : activeConvId);

  // Persist last conversation ID
  useEffect(() => {
    if (currentConvId && currentConvId !== "new") {
      localStorage.setItem("last_conversation_id", currentConvId);
      if (!routeConvId || routeConvId === "new") {
        navigate(`/chat/${currentConvId}`, { replace: true });
      }
    }
  }, [currentConvId, routeConvId, navigate]);

  const { speak, isPlaying, startListening, stopListening, isListening, transcript } = useVoice();

  const [inputValue, setInputValue] = useState("");
  const [orbState, setOrbState] = useState<"idle" | "listening" | "speaking" | "thinking">("idle");
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  const [routingConfig, setRoutingConfigState] = useState<RoutingConfig | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [autoMode, setAutoMode] = useState(false);

  const [chatTools, setChatTools] = useState<ToolInfo[]>([]);
  const [selectedTool, setSelectedTool] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const toolParam = searchParams.get("tool");
    if (toolParam) {
      setSelectedTool(toolParam);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    getRoutingConfig()
      .then((config) => {
        setRoutingConfigState(config);
        setAutoMode(config.auto_routing_enabled);
        setSelectedModel(config.active_model_id);
      })
      .catch(() => {});

    getChatTools()
      .then(setChatTools)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (transcript) {
      setInputValue(transcript);
    }
  }, [transcript]);

  useEffect(() => {
    const lastMsg = messages[messages.length - 1];
    if (!lastMsg) return;

    if (isStreaming || isLoading) {
      setOrbState("thinking");
    } else if (lastMsg.role === "assistant" && lastMsg.content) {
      setOrbState("speaking");
      if (voiceEnabled && lastMsg.content.length < 500) {
        speak(lastMsg.content);
      }
      const timer = setTimeout(() => setOrbState("idle"), 2000);
      return () => clearTimeout(timer);
    } else {
      setOrbState("idle");
    }
  }, [messages, isStreaming, isLoading, voiceEnabled, speak]);

  useEffect(() => {
    if (isListening) {
      setOrbState("listening");
    } else if (!isStreaming && !isLoading) {
      setOrbState("idle");
    }
  }, [isListening, isStreaming, isLoading]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isLoading || isStreaming) return;
    setInputValue("");
    const modelId = autoMode ? undefined : selectedModel || undefined;
    sendMessageStream(text, modelId, selectedTool || undefined);
  }, [inputValue, isLoading, isStreaming, sendMessageStream, autoMode, selectedModel, selectedTool]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const handleVoiceToggle = useCallback((enabled: boolean) => {
    setVoiceEnabled(enabled);
    toggleVoiceApi(enabled).catch(() => {});
  }, []);

  const handleMicClick = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const lastMessage = messages[messages.length - 1];
  const showLoadingDots = isLoading || (isStreaming && lastMessage?.role === "assistant" && !lastMessage.content);

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col">
      {messages.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center px-6">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
            className="text-center"
          >
            <Orb size="lg" state={orbState} />
            <h1 className="mt-6 text-2xl font-light text-text-primary">
              What can I help you with?
            </h1>
            <p className="mt-2 text-sm text-text-tertiary">
              Ask me anything, or select a tool to get started.
            </p>
          </motion.div>
        </div>
      )}

      {messages.length > 0 && (
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-6 pb-36 sm:px-12"
        >
          <div className="mx-auto max-w-[680px] space-y-4 pt-6">
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div
                  key={`${msg.role}-${i}`}
                  variants={childVariants}
                  initial="initial"
                  animate="enter"
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" ? (
                    <NeuCard variant="raised" radius="lg" padding="sm" className="max-w-[80%]">
                      <p className="text-text-primary leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </NeuCard>
                  ) : (
                    <div className="max-w-[80%] rounded-[16px] bg-accent/10 px-4 py-3">
                      <p className="text-text-primary leading-relaxed">
                        {msg.content}
                      </p>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {showLoadingDots && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
                <NeuCard variant="raised" radius="lg" padding="sm">
                  <div className="flex items-center gap-1.5 px-2 py-1">
                    {[0, 1, 2].map((dot) => (
                      <motion.span
                        key={dot}
                        className="h-2 w-2 rounded-full bg-accent/40"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1, repeat: Infinity, delay: dot * 0.2 }}
                      />
                    ))}
                  </div>
                </NeuCard>
              </motion.div>
            )}
          </div>
        </div>
      )}

      <div
        className="border-t px-6 sm:px-8"
        style={{
          background: "color-mix(in srgb, var(--surface) 80%, transparent)",
          borderColor: "color-mix(in srgb, var(--shadow-dark) 20%, transparent)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="mx-auto flex max-w-[680px] items-center gap-3 py-4">
          {chatTools.length > 0 && (
            <ToolSelector
              tools={chatTools}
              activeTool={selectedTool}
              onSelect={setSelectedTool}
            />
          )}

          {routingConfig && routingConfig.available_models.length > 1 && (
            <ModelSelector
              models={routingConfig.available_models}
              activeModel={selectedModel}
              autoRoutingEnabled={routingConfig.auto_routing_enabled}
              autoRoutingActive={autoMode}
              onSelectModel={(id) => {
                setSelectedModel(id);
                setActiveModel(id).catch(() => {});
              }}
              onToggleAutoRouting={(auto) => {
                setAutoMode(auto);
                setRoutingMode(auto).catch(() => {});
              }}
            />
          )}

          <NeuInput
            placeholder={selectedTool ? `Ask about ${chatTools.find(t => t.slug === selectedTool)?.name ?? selectedTool}...` : "Type a message..."}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            className="flex-1"
          />

          {voiceEnabled && (
            <NeuButton
              pill
              size="sm"
              variant={isListening ? "primary" : "secondary"}
              onClick={handleMicClick}
              disabled={isStreaming || isPlaying}
            >
              <MicIcon className="h-4 w-4" />
            </NeuButton>
          )}

          {isStreaming ? (
            <StopButton onClick={abortGeneration} />
          ) : (
            <NeuButton
              pill
              size="sm"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              <SendIcon className="h-4 w-4" />
            </NeuButton>
          )}

          <VoiceToggle enabled={voiceEnabled} onToggle={handleVoiceToggle} />
        </div>
      </div>
    </div>
  );
}
