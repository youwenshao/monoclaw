import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Orb,
  NeuButton,
  NeuCard,
  WaveForm,
  PageTransition,
  FadeUp,
  VoiceToggle,
} from "@/components/ui";
import { useVoice } from "@/hooks/useVoice";
import { sendChatMessage, toggleVoice } from "@/lib/api";
import { childVariants } from "@/lib/animations";

type Language = "en" | "yue" | "zh";

const GREETINGS: Record<Language, { text: string; label: string }> = {
  en: {
    text: "Hello! I'm Mona, your assistant. It's nice to finally meet you.",
    label: "English",
  },
  yue: {
    text: "你好！我係Mona，你嘅助手。好開心終於見到你。",
    label: "粵語",
  },
  zh: {
    text: "你好！我是Mona，你的助手。很高兴终于见到你。",
    label: "普通話",
  },
};

function MicIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="8" y1="22" x2="16" y2="22" />
    </svg>
  );
}

export function VoiceDemo() {
  const navigate = useNavigate();
  const { speak, isPlaying, startListening, stopListening, isListening, transcript } =
    useVoice();

  const [activeLanguage, setActiveLanguage] = useState<Language | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [monaResponse, setMonaResponse] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  const orbState = isPlaying ? "speaking" : isListening ? "listening" : "idle";

  const handleLanguageSelect = useCallback(
    (lang: Language) => {
      if (isPlaying) return;
      setActiveLanguage(lang);
      speak(GREETINGS[lang].text, lang);
    },
    [isPlaying, speak],
  );

  const handleMicToggle = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      setShowTranscript(false);
      setMonaResponse("");
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const handleVoiceToggle = useCallback(async (enabled: boolean) => {
    setVoiceEnabled(enabled);
    try { await toggleVoice(enabled); } catch {}
  }, []);

  useEffect(() => {
    if (!transcript) return;
    setShowTranscript(true);
  }, [transcript]);

  useEffect(() => {
    if (!transcript || !showTranscript) return;

    const fetchResponse = async () => {
      try {
        const chatResponse = await sendChatMessage(transcript);
        const responseText = chatResponse.response;
        setMonaResponse(responseText);
        speak(responseText, activeLanguage || "en");
      } catch {
        setMonaResponse("I heard you, but couldn't formulate a response right now.");
      }
    };

    const timer = setTimeout(fetchResponse, 600);
    return () => clearTimeout(timer);
  }, [showTranscript, transcript, speak, activeLanguage]);

  return (
    <PageTransition fullHeight centered>
      <FadeUp className="mb-8">
        <Orb state={orbState} size="lg" />
      </FadeUp>

      <AnimatePresence mode="wait">
        {isPlaying ? (
          <motion.div
            key="waveform"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mb-8 w-full max-w-[280px]"
          >
            <WaveForm active />
          </motion.div>
        ) : (
          <motion.div
            key="text"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="mb-8"
          >
            <p className="text-xl font-light text-text-primary">
              You can talk to me anytime.
            </p>
            <p className="mt-2 text-text-secondary">
              I understand English, Cantonese, and Mandarin.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <FadeUp className="mb-10">
        <div className="flex items-center justify-center gap-3">
          {(Object.entries(GREETINGS) as [Language, { text: string; label: string }][]).map(
            ([lang, { label }]) => (
              <NeuButton
                key={lang}
                pill
                size="sm"
                variant={activeLanguage === lang ? "primary" : "secondary"}
                onClick={() => handleLanguageSelect(lang)}
                disabled={isPlaying}
                className={activeLanguage === lang ? "bg-accent text-white" : ""}
              >
                {label}
              </NeuButton>
            ),
          )}
        </div>
      </FadeUp>

      <FadeUp className="mb-10 w-full max-w-[360px]">
        <NeuCard variant="raised" padding="md" className="flex flex-col items-center gap-4">
          <p className="text-sm text-text-secondary">Want to try?</p>

          <motion.button
            onClick={handleMicToggle}
            className={`flex h-16 w-16 items-center justify-center rounded-full transition-colors ${
              isListening
                ? "bg-accent text-white"
                : "neu-raised text-text-secondary hover:text-accent"
            }`}
            animate={isListening ? { scale: [1, 1.06, 1] } : { scale: 1 }}
            transition={
              isListening
                ? { duration: 1.2, repeat: Infinity, ease: "easeInOut" }
                : undefined
            }
            whileTap={{ scale: 0.95 }}
          >
            <MicIcon className="h-7 w-7" />
          </motion.button>

          <p className="text-xs text-text-tertiary">
            {isListening ? "Tap to stop" : "Tap to speak"}
          </p>

          <AnimatePresence>
            {showTranscript && transcript && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="w-full overflow-hidden"
              >
                <div className="rounded-[8px] neu-inset p-3 text-sm text-text-secondary">
                  "{transcript}"
                </div>
                {monaResponse && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="mt-3 rounded-[8px] neu-raised p-3 text-sm text-text-primary"
                  >
                    {monaResponse}
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>
      </FadeUp>

      <FadeUp className="w-full max-w-[360px]">
        <NeuCard variant="flat" padding="sm" className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-text-primary">Voice interaction</p>
            <p className="text-xs text-text-tertiary">Mona can speak and listen</p>
          </div>
          <VoiceToggle enabled={voiceEnabled} onToggle={handleVoiceToggle} />
        </NeuCard>
      </FadeUp>

      <FadeUp>
        <p className="mt-4 text-center text-xs text-text-tertiary">
          Mona's voice runs entirely on your Mac — no internet needed.
        </p>
      </FadeUp>

      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="mt-8 flex flex-col items-center gap-3"
      >
        <NeuButton onClick={() => navigate("/welcome/chat")}>Continue</NeuButton>
        <NeuButton variant="ghost" size="sm" onClick={() => navigate("/welcome/chat")}>
          Skip
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
