import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Orb, TypeWriter, NeuButton, PageTransition, FadeUp } from "@/components/ui";
import { childVariants } from "@/lib/animations";
import { motion } from "framer-motion";

const INTRO_LINES = [
  "Hi. I'm Mona.",
  "I live on this Mac — no cloud, no subscriptions.",
  "I can help you write, research, plan, and automate your work.",
  "Everything stays between us.",
];

export function Introduction() {
  const navigate = useNavigate();
  const [typingDone, setTypingDone] = useState(false);

  return (
    <PageTransition fullHeight centered>
      <FadeUp className="mb-10">
        <Orb state="speaking" size="lg" />
      </FadeUp>

      <FadeUp className="mb-12 max-w-md text-center">
        <TypeWriter
          lines={INTRO_LINES}
          pauseBetweenLines={600}
          lineClassName="text-lg"
          onComplete={() => setTypingDone(true)}
        />
      </FadeUp>

      {typingDone && (
        <motion.div
          variants={childVariants}
          initial="initial"
          animate="enter"
          className="flex flex-col items-center gap-3"
        >
          <NeuButton size="lg" onClick={() => navigate("/welcome/profile")}>
            Hear my voice →
          </NeuButton>
          <NeuButton
            variant="ghost"
            size="sm"
            onClick={() => navigate("/welcome/profile")}
          >
            Skip
          </NeuButton>
        </motion.div>
      )}
    </PageTransition>
  );
}
