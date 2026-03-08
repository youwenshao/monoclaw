import { Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";

const PHASES = [
  "",
  "independence",
  "meet",
  "profile",
  "mac-setup",
  "api-keys",
  "voice",
  "chat",
  "tools",
  "first-task",
  "summary",
  "launch",
];

export function OnboardingLayout() {
  const { pathname } = useLocation();
  const segment = pathname.split("/").pop() ?? "";
  const currentIndex = Math.max(0, PHASES.indexOf(segment));
  const progress = ((currentIndex + 1) / PHASES.length) * 100;

  return (
    <div className="relative min-h-screen">
      <div className="fixed inset-x-0 top-0 z-50 h-1 bg-surface-inset">
        <motion.div
          className="h-full bg-accent"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        />
      </div>
      <Outlet />
    </div>
  );
}
