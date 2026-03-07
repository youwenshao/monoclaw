import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { NeuButton, TypeWriter } from "@/components/ui";
import { containerVariants } from "@/lib/animations";

function CheckmarkAnimation({ onComplete }: { onComplete: () => void }) {
  return (
    <motion.svg
      width="80"
      height="80"
      viewBox="0 0 80 80"
      fill="none"
      className="mx-auto"
    >
      <motion.circle
        cx="40"
        cy="40"
        r="36"
        stroke="var(--success)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
      />
      <motion.path
        d="M26 41l10 10 18-22"
        stroke="var(--success)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.4, ease: "easeOut" }}
        onAnimationComplete={onComplete}
      />
    </motion.svg>
  );
}

const LINES = [
  "Everything here runs on your Mac.",
  "No cloud dependencies. No subscriptions. No tracking.",
  "You're in full control, forever.",
];

export function Independence() {
  const navigate = useNavigate();
  const [checkDone, setCheckDone] = useState(false);
  const [typingDone, setTypingDone] = useState(false);

  return (
    <motion.div
      variants={containerVariants}
      initial="initial"
      animate="enter"
      className="flex min-h-screen flex-col items-center justify-center px-6 text-center"
    >
      <div className="mb-10">
        <CheckmarkAnimation onComplete={() => setCheckDone(true)} />
      </div>

      {checkDone && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="mb-12 max-w-md"
        >
          <TypeWriter
            lines={LINES}
            pauseBetweenLines={800}
            lineClassName="text-lg"
            onComplete={() => setTypingDone(true)}
          />
        </motion.div>
      )}

      {typingDone && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-col items-center gap-6"
        >
          <p className="text-sm text-text-tertiary">
            Support is always available at{" "}
            <a
              href="mailto:team@sentimento.dev"
              className="underline underline-offset-2"
            >
              team@sentimento.dev
            </a>
          </p>
          <NeuButton size="lg" onClick={() => navigate("/welcome/meet")}>
            Meet Mona →
          </NeuButton>
        </motion.div>
      )}
    </motion.div>
  );
}
