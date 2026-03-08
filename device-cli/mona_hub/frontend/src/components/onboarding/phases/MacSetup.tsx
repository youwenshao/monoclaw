import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  PageTransition,
  FadeUp,
  NeuCard,
  NeuButton,
  NeuInput,
} from "@/components/ui";
import {
  getSystemInfo,
  setComputerName,
  setAppearance,
  openSettings,
  updateProgress,
} from "@/lib/api";
import type { SystemInfo } from "@/lib/api";
import { childVariants } from "@/lib/animations";

type Appearance = "light" | "dark" | "auto";

const APPEARANCE_OPTIONS: { value: Appearance; label: string; icon: string }[] = [
  { value: "light", label: "Light", icon: "☀️" },
  { value: "dark", label: "Dark", icon: "🌙" },
  { value: "auto", label: "Auto", icon: "💻" },
];

export function MacSetup() {
  const navigate = useNavigate();
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [computerName, setComputerNameValue] = useState("");
  const [appearance, setAppearanceValue] = useState<Appearance>("auto");
  const [saving, setSaving] = useState(false);
  const [nameEdited, setNameEdited] = useState(false);

  useEffect(() => {
    getSystemInfo()
      .then((info) => {
        setSystemInfo(info);
        setComputerNameValue(info.computer_name);
      })
      .catch(() => {});
  }, []);

  async function handleSaveName() {
    if (!computerName.trim() || saving) return;
    setSaving(true);
    try {
      await setComputerName(computerName.trim());
      setNameEdited(false);
    } catch {}
    setSaving(false);
  }

  async function handleAppearance(mode: Appearance) {
    setAppearanceValue(mode);
    try {
      await setAppearance(mode);
    } catch {}
  }

  async function handleContinue() {
    await updateProgress(6, 6, true).catch(() => {});
    navigate("/welcome/api-keys");
  }

  return (
    <PageTransition fullHeight centered>
      <FadeUp className="mb-3">
        <h2 className="text-2xl font-light text-text-primary">
          Make it yours.
        </h2>
      </FadeUp>

      <FadeUp className="mb-10">
        <p className="text-text-secondary">
          A few quick system preferences — skip anything you like.
        </p>
      </FadeUp>

      <div className="flex w-full max-w-[480px] flex-col gap-6">
        {/* System info summary */}
        {systemInfo && (
          <FadeUp>
            <NeuCard variant="flat" padding="sm">
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">macOS</span>
                <span className="text-sm text-text-primary">
                  {systemInfo.macos_version}
                </span>
              </div>
              <div className="my-2 h-px bg-white/5" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">Hardware</span>
                <span className="text-sm text-text-primary">
                  {systemInfo.hardware}
                </span>
              </div>
            </NeuCard>
          </FadeUp>
        )}

        {/* Computer name */}
        <FadeUp>
          <NeuCard variant="raised" padding="md">
            <p className="mb-3 text-sm font-medium text-text-primary">
              Computer name
            </p>
            <div className="flex gap-3">
              <NeuInput
                value={computerName}
                onChange={(e) => {
                  setComputerNameValue(e.target.value);
                  setNameEdited(true);
                }}
                placeholder="My Mac"
                className="flex-1"
              />
              <AnimatePresence>
                {nameEdited && computerName.trim() && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                  >
                    <NeuButton
                      size="sm"
                      onClick={handleSaveName}
                      disabled={saving}
                    >
                      {saving ? "..." : "Save"}
                    </NeuButton>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </NeuCard>
        </FadeUp>

        {/* Appearance */}
        <FadeUp>
          <NeuCard variant="raised" padding="md">
            <p className="mb-4 text-sm font-medium text-text-primary">
              Appearance
            </p>
            <div className="flex gap-3">
              {APPEARANCE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleAppearance(opt.value)}
                  className={`flex flex-1 flex-col items-center gap-2 rounded-xl p-3 transition-all ${
                    appearance === opt.value
                      ? "neu-inset ring-2 ring-accent/50"
                      : "neu-raised"
                  }`}
                >
                  <span className="text-xl">{opt.icon}</span>
                  <span className="text-xs text-text-secondary">
                    {opt.label}
                  </span>
                </button>
              ))}
            </div>
          </NeuCard>
        </FadeUp>

        {/* Open System Settings */}
        <FadeUp>
          <NeuButton
            variant="secondary"
            size="sm"
            onClick={() => openSettings("general").catch(() => {})}
            className="mx-auto"
          >
            Open System Settings
          </NeuButton>
        </FadeUp>
      </div>

      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="mt-10 flex flex-col items-center gap-3"
      >
        <NeuButton size="lg" onClick={handleContinue}>
          Continue
        </NeuButton>
        <NeuButton
          variant="ghost"
          size="sm"
          onClick={() => navigate("/welcome/api-keys")}
        >
          Skip
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
