import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { NeuButton, FadeUp } from "@/components/ui";
import { containerVariants, childVariants } from "@/lib/animations";

const gradientKeyframes = `
@keyframes drift {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
`;

export function Welcome() {
  const navigate = useNavigate();

  return (
    <>
      <style>{gradientKeyframes}</style>

      <div
        className="pointer-events-none fixed inset-0 -z-10 opacity-60"
        style={{
          background:
            "radial-gradient(ellipse at 30% 40%, var(--surface-raised), transparent 60%), " +
            "radial-gradient(ellipse at 70% 60%, var(--accent-subtle), transparent 50%), " +
            "linear-gradient(135deg, var(--surface), var(--surface-raised), var(--surface))",
          backgroundSize: "200% 200%",
          animation: "drift 18s ease-in-out infinite",
        }}
      />

      <motion.div
        variants={containerVariants}
        initial="initial"
        animate="enter"
        className="flex min-h-screen flex-col items-center justify-center px-6 text-center"
      >
        <FadeUp className="mb-10">
          <span className="text-sm uppercase tracking-widest text-text-tertiary">
            MonoClaw
          </span>
        </FadeUp>

        <FadeUp className="mb-4">
          <h1 className="text-4xl font-light tracking-tight text-text-primary">
            Your new team member has arrived.
          </h1>
        </FadeUp>

        <FadeUp className="mb-12">
          <p className="text-lg text-text-secondary">
            Let's get you two acquainted.
          </p>
        </FadeUp>

        <FadeUp>
          <NeuButton size="lg" onClick={() => navigate("/welcome/independence")}>
            Begin
          </NeuButton>
        </FadeUp>
      </motion.div>
    </>
  );
}
