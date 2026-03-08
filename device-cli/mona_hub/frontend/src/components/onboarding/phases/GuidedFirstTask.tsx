import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  PageTransition,
  FadeUp,
  NeuCard,
  NeuButton,
  Orb,
} from "@/components/ui";
import { startGuidedTask, updateProgress } from "@/lib/api";
import { childVariants } from "@/lib/animations";

export function GuidedFirstTask() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [response, setResponse] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    startGuidedTask("general", "quick-demo")
      .then((res) => {
        setResponse(res.response);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  async function handleContinue() {
    await updateProgress(9, 9, true).catch(() => {});
    navigate("/welcome/summary");
  }

  return (
    <PageTransition fullHeight centered>
      <FadeUp className="mb-8">
        <Orb state={loading ? "speaking" : "idle"} size="md" />
      </FadeUp>

      <FadeUp className="mb-4">
        <h2 className="text-2xl font-light text-text-primary">
          Let me show you what I can do.
        </h2>
      </FadeUp>

      <FadeUp className="mb-10">
        <p className="text-text-secondary">
          Here's a quick example based on your profile.
        </p>
      </FadeUp>

      <div className="w-full max-w-[560px]">
        {loading && (
          <FadeUp>
            <NeuCard variant="raised" padding="lg">
              <div className="flex items-center justify-center gap-3 py-6">
                <motion.div
                  className="h-5 w-5 rounded-full border-2 border-accent/30 border-t-accent"
                  animate={{ rotate: 360 }}
                  transition={{
                    duration: 1,
                    repeat: Infinity,
                    ease: "linear",
                  }}
                />
                <p className="text-sm text-text-secondary">
                  Mona is thinking...
                </p>
              </div>
            </NeuCard>
          </FadeUp>
        )}

        {!loading && error && (
          <FadeUp>
            <NeuCard variant="raised" padding="lg">
              <p className="text-center text-text-secondary">
                Couldn't generate a demo right now — that's okay, you can
                explore freely after setup.
              </p>
            </NeuCard>
          </FadeUp>
        )}

        {!loading && !error && response && (
          <FadeUp>
            <NeuCard variant="raised" padding="lg">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex-shrink-0 text-accent">
                  <Orb state="idle" size="sm" />
                </span>
                <div className="flex-1">
                  <p className="mb-1 text-xs font-medium uppercase tracking-wider text-accent">
                    Mona
                  </p>
                  <p className="whitespace-pre-wrap leading-relaxed text-text-primary">
                    {response}
                  </p>
                </div>
              </div>
            </NeuCard>
          </FadeUp>
        )}
      </div>

      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="mt-10 flex flex-col items-center gap-3"
      >
        <NeuButton size="lg" onClick={handleContinue}>
          {loading ? "Skip for now" : "Continue →"}
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
