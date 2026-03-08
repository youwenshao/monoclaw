import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { PageTransition, FadeUp, NeuInput, NeuButton, NeuCard } from "@/components/ui";
import { saveProfile, updateProgress } from "@/lib/api";
import { childVariants } from "@/lib/animations";

type Stage = "name" | "language" | "style";

interface LanguageOption {
  value: string;
  label: string;
  badge: string;
}

const LANGUAGES: LanguageOption[] = [
  { value: "en", label: "English", badge: "EN" },
  { value: "yue", label: "繁體中文", badge: "粵" },
  { value: "zh", label: "简体中文", badge: "普" },
];

interface StyleOption {
  value: string;
  label: string;
  example: string;
}

const STYLES: StyleOption[] = [
  {
    value: "casual",
    label: "Casual",
    example: "Hey! Ready when you are. What's on the agenda?",
  },
  {
    value: "balanced",
    label: "Balanced",
    example: "Hi there. I'm ready to help. What would you like to work on?",
  },
  {
    value: "formal",
    label: "Formal",
    example: "Good morning. I'm at your service. How may I assist you today?",
  },
];

const stageVariants = {
  initial: { opacity: 0, y: 16 },
  enter: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.25, 0.1, 0.25, 1] as const } },
  exit: { opacity: 0, y: -12, transition: { duration: 0.25 } },
};

export function Profile() {
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>("name");
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("");
  const [style, setStyle] = useState("");
  const [saving, setSaving] = useState(false);
  const autoAdvanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (autoAdvanceTimer.current) clearTimeout(autoAdvanceTimer.current);
    };
  }, []);

  useEffect(() => {
    if (stage === "name") {
      const timer = setTimeout(() => nameInputRef.current?.focus(), 400);
      return () => clearTimeout(timer);
    }
  }, [stage]);

  function handleNameContinue() {
    if (!name.trim()) return;
    setStage("language");
  }

  function handleLanguageSelect(value: string) {
    setLanguage(value);
    autoAdvanceTimer.current = setTimeout(() => setStage("style"), 500);
  }

  async function handleStyleSelect(value: string) {
    setStyle(value);
    setSaving(true);
    try {
      await saveProfile({
        name: name.trim(),
        language_pref: language,
        communication_style: value,
      });
      localStorage.setItem("mona_profile", JSON.stringify({ name: name.trim(), language, style: value }));
      await updateProgress(5, 5, true);
      setTimeout(() => navigate("/welcome/mac-setup"), 600);
    } catch {
      setTimeout(() => navigate("/welcome/mac-setup"), 600);
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageTransition fullHeight centered>
      <AnimatePresence mode="wait">
        {stage === "name" && (
          <motion.div
            key="name"
            variants={stageVariants}
            initial="initial"
            animate="enter"
            exit="exit"
            className="flex w-full max-w-[400px] flex-col items-center gap-8"
          >
            <h2 className="text-2xl font-light text-text-primary">
              What should I call you?
            </h2>
            <NeuInput
              ref={nameInputRef}
              placeholder="Your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleNameContinue()}
              className="w-full text-center text-lg"
            />
            <NeuButton onClick={handleNameContinue} disabled={!name.trim()}>
              Continue
            </NeuButton>
          </motion.div>
        )}

        {stage === "language" && (
          <motion.div
            key="language"
            variants={stageVariants}
            initial="initial"
            animate="enter"
            exit="exit"
            className="flex w-full max-w-[480px] flex-col items-center gap-8"
          >
            <h2 className="text-2xl font-light text-text-primary">
              What language do you prefer?
            </h2>
            <div className="flex w-full gap-4">
              {LANGUAGES.map((lang) => (
                <NeuCard
                  key={lang.value}
                  variant={language === lang.value ? "inset" : "raised"}
                  padding="md"
                  className={`flex flex-1 cursor-pointer flex-col items-center gap-3 transition-all ${
                    language === lang.value ? "ring-2 ring-accent/50" : ""
                  }`}
                  onClick={() => handleLanguageSelect(lang.value)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <span className="text-xs font-medium uppercase tracking-wider text-accent">
                    {lang.badge}
                  </span>
                  <span className="text-text-primary">{lang.label}</span>
                </NeuCard>
              ))}
            </div>
          </motion.div>
        )}

        {stage === "style" && (
          <motion.div
            key="style"
            variants={stageVariants}
            initial="initial"
            animate="enter"
            exit="exit"
            className="flex w-full max-w-[480px] flex-col items-center gap-8"
          >
            <h2 className="text-2xl font-light text-text-primary">
              How should I communicate?
            </h2>
            <div className="flex w-full flex-col gap-3">
              {STYLES.map((s) => (
                <NeuCard
                  key={s.value}
                  variant={style === s.value ? "inset" : "raised"}
                  padding="md"
                  className={`cursor-pointer text-left transition-all ${
                    style === s.value ? "ring-2 ring-accent/50" : ""
                  }`}
                  onClick={() => handleStyleSelect(s.value)}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                >
                  <span className="mb-1 block text-sm font-medium text-accent">
                    {s.label}
                  </span>
                  <span className="text-sm leading-relaxed text-text-secondary">
                    "{s.example}"
                  </span>
                </NeuCard>
              ))}
            </div>
          </motion.div>
        )}

      </AnimatePresence>

      <FadeUp className="mt-12">
        <div className="flex items-center justify-center gap-2">
          {(["name", "language", "style"] as Stage[]).map((s) => (
            <motion.div
              key={s}
              className={`h-1.5 rounded-full transition-colors ${
                s === stage
                  ? "w-6 bg-accent"
                  : (["name", "language", "style"].indexOf(s) <
                      ["name", "language", "style"].indexOf(stage))
                    ? "w-1.5 bg-accent/40"
                    : "w-1.5 bg-text-tertiary/30"
              }`}
              layout
            />
          ))}
        </div>
      </FadeUp>
    </PageTransition>
  );
}
