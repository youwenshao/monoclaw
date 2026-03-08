import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type KeyboardEvent,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { Orb, NeuCard, NeuButton, NeuInput, ModelSelector, StopButton } from "@/components/ui";
import { useChat } from "@/hooks/useChat";
import { getRoutingConfig, setActiveModel, setRoutingMode } from "@/lib/api";
import { childVariants } from "@/lib/animations";
import type { ChatMessage } from "@/lib/api";

const INITIAL_MESSAGES: ChatMessage[] = [
  { role: "assistant", content: "You can also just type. Whatever's comfortable." },
  { role: "assistant", content: "Try asking me something — anything." },
];

const TRANSITION_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "I think we're going to work well together. Ready to set things up?",
};

function SendIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function ChatDemo() {
  const navigate = useNavigate();
  const {
    messages: apiMessages,
    sendMessage,
    sendMessageStream,
    abortGeneration,
    isLoading,
    isStreaming,
  } = useChat();

  const [allMessages, setAllMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [showTransition, setShowTransition] = useState(false);
  const [userMessageCount, setUserMessageCount] = useState(0);
  const [orbState, setOrbState] = useState<"idle" | "speaking">("idle");
  const [initDone, setInitDone] = useState(false);

  const [routingConfig, setRoutingConfigState] = useState<any>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [autoMode, setAutoMode] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const transitionInjected = useRef(false);

  useEffect(() => {
    getRoutingConfig().then(config => {
      setRoutingConfigState(config);
      setAutoMode(config.auto_routing_enabled);
      setSelectedModel(config.active_model_id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (initDone) return;

    const t1 = setTimeout(() => {
      setAllMessages([INITIAL_MESSAGES[0]]);
    }, 400);

    const t2 = setTimeout(() => {
      setAllMessages([INITIAL_MESSAGES[0], INITIAL_MESSAGES[1]]);
      setInitDone(true);
    }, 2000);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [initDone]);

  useEffect(() => {
    if (!initDone || apiMessages.length === 0) return;

    setAllMessages((prev) => {
      const initLen = INITIAL_MESSAGES.length;
      return [...prev.slice(0, initLen), ...apiMessages];
    });
  }, [apiMessages, initDone]);

  useEffect(() => {
    const lastMsg = allMessages[allMessages.length - 1];
    if (lastMsg?.role !== "assistant" || allMessages.length <= INITIAL_MESSAGES.length) return;

    setOrbState("speaking");
    const timer = setTimeout(() => setOrbState("idle"), 1500);
    return () => clearTimeout(timer);
  }, [allMessages]);

  useEffect(() => {
    if (
      userMessageCount >= 2 &&
      !transitionInjected.current &&
      !isLoading &&
      !isStreaming &&
      allMessages.length > INITIAL_MESSAGES.length
    ) {
      const lastMsg = allMessages[allMessages.length - 1];
      if (lastMsg?.role === "assistant" && lastMsg.content) {
        transitionInjected.current = true;
        const timer = setTimeout(() => {
          setAllMessages((prev) => [...prev, TRANSITION_MESSAGE]);
          setShowTransition(true);
        }, 1200);
        return () => clearTimeout(timer);
      }
    }
  }, [userMessageCount, isLoading, isStreaming, allMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [allMessages]);

  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || isLoading || isStreaming) return;
    setInputValue("");
    setUserMessageCount((c) => c + 1);
    sendMessageStream(text, autoMode ? undefined : selectedModel || undefined);
  }, [inputValue, isLoading, isStreaming, sendMessageStream, autoMode, selectedModel]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const lastMessage = allMessages[allMessages.length - 1];
  const showLoadingDots = isLoading || (isStreaming && lastMessage?.role === "assistant" && !lastMessage.content);

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex items-center gap-4 px-6 pt-8 pb-4 sm:px-12">
        <Orb size="sm" state={orbState} />
        <p className="text-lg font-light text-text-secondary">
          You can also just type. Whatever's comfortable.
        </p>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 pb-36 sm:px-12"
      >
        <div className="mx-auto max-w-[640px] space-y-4 pt-4">
          <AnimatePresence initial={false}>
            {allMessages.map((msg, i) => (
              <motion.div
                key={`${msg.role}-${i}`}
                variants={childVariants}
                initial="initial"
                animate="enter"
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" ? (
                  <NeuCard
                    variant="raised"
                    radius="lg"
                    padding="sm"
                    className="max-w-[80%]"
                  >
                    <p className="text-text-primary leading-relaxed">
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
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <NeuCard variant="raised" radius="lg" padding="sm">
                <div className="flex items-center gap-1.5 px-2 py-1">
                  {[0, 1, 2].map((dot) => (
                    <motion.span
                      key={dot}
                      className="h-2 w-2 rounded-full bg-accent/40"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        delay: dot * 0.2,
                      }}
                    />
                  ))}
                </div>
              </NeuCard>
            </motion.div>
          )}

          <AnimatePresence>
            {showTransition && (
              <motion.div
                variants={childVariants}
                initial="initial"
                animate="enter"
                className="flex justify-center pt-6"
              >
                <NeuButton onClick={() => navigate("/welcome/tools")}>
                  Let's go
                </NeuButton>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 border-t border-white/5 bg-surface/80 backdrop-blur-lg">
        <div className="mx-auto flex max-w-[640px] items-center gap-3 px-6 py-4 sm:px-12">
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
            placeholder="Type a message..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            className="flex-1"
          />
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
        </div>
      </div>
    </div>
  );
}
