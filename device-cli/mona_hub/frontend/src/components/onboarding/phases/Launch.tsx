import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { PageTransition, FadeUp, NeuButton } from "@/components/ui";
import { completeOnboarding } from "@/lib/api";
import { containerVariants, childVariants } from "@/lib/animations";

function SuccessCheckmark({ onComplete }: { onComplete: () => void }) {
  return (
    <motion.svg
      width="96"
      height="96"
      viewBox="0 0 96 96"
      fill="none"
      className="mx-auto"
    >
      <motion.circle
        cx="48"
        cy="48"
        r="42"
        stroke="var(--success)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.7, ease: "easeOut" }}
      />
      <motion.path
        d="M30 49l12 12 22-26"
        stroke="var(--success)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.5, ease: "easeOut" }}
        onAnimationComplete={onComplete}
      />
    </motion.svg>
  );
}

export function Launch() {
  const [animDone, setAnimDone] = useState(false);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    completeOnboarding()
      .then(() => setCompleted(true))
      .catch(() => setCompleted(true));
  }, []);

  return (
    <PageTransition fullHeight centered>
      <motion.div
        variants={containerVariants}
        initial="initial"
        animate="enter"
        className="flex flex-col items-center text-center"
      >
        <FadeUp className="mb-10">
          <SuccessCheckmark onComplete={() => setAnimDone(true)} />
        </FadeUp>

        {animDone && (
          <>
            <motion.h1
              variants={childVariants}
              initial="initial"
              animate="enter"
              className="mb-4 text-3xl font-light text-text-primary"
            >
              Mona is ready.
            </motion.h1>

            <motion.p
              variants={childVariants}
              initial="initial"
              animate="enter"
              className="mb-2 max-w-sm text-lg text-text-secondary"
            >
              Your AI assistant is set up and running on this Mac.
            </motion.p>

            <motion.p
              variants={childVariants}
              initial="initial"
              animate="enter"
              className="mb-12 max-w-sm text-sm text-text-tertiary"
            >
              Open the <strong>Mona</strong> app from Spotlight or the
              Applications folder anytime.
            </motion.p>

            {completed && (
              <motion.div
                variants={childVariants}
                initial="initial"
                animate="enter"
              >
                <NeuButton
                  variant="secondary"
                  size="sm"
                  onClick={() => window.location.assign("/")}
                >
                  Open Mona Hub
                </NeuButton>
              </motion.div>
            )}
          </>
        )}
      </motion.div>
    </PageTransition>
  );
}
