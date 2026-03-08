import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { getOnboardingState } from "@/lib/api";
import { Orb } from "@/components/ui";
import { OnboardingLayout } from "@/components/onboarding/OnboardingLayout";
import { Welcome } from "@/components/onboarding/phases/Welcome";
import { Independence } from "@/components/onboarding/phases/Independence";
import { Introduction } from "@/components/onboarding/phases/Introduction";
import { VoiceDemo } from "@/components/onboarding/phases/VoiceDemo";
import { ChatDemo } from "@/components/onboarding/phases/ChatDemo";
import { Profile } from "@/components/onboarding/phases/Profile";
import { MacSetup } from "@/components/onboarding/phases/MacSetup";
import { ApiKeys } from "@/components/onboarding/phases/ApiKeys";
import { ToolsOverview } from "@/components/onboarding/phases/ToolsOverview";
import { GuidedFirstTask } from "@/components/onboarding/phases/GuidedFirstTask";
import { Summary } from "@/components/onboarding/phases/Summary";
import { Launch } from "@/components/onboarding/phases/Launch";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { ChatInterface } from "@/components/dashboard/ChatInterface";
import { ToolsGrid } from "@/components/dashboard/ToolsGrid";

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <Orb size="md" state="idle" />
      </motion.div>
    </div>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [onboardingCompleted, setOnboardingCompleted] = useState(false);

  useEffect(() => {
    getOnboardingState()
      .then((state) => {
        setOnboardingCompleted(state.onboarding_completed);
        setReady(true);
      })
      .catch(() => {
        setReady(true);
      });
  }, []);

  if (!ready) return <LoadingScreen />;

  return (
    <BrowserRouter>
      <Routes>
        {onboardingCompleted ? (
          <>
            <Route path="/" element={<DashboardLayout />}>
              <Route index element={<ChatInterface />} />
              <Route path="tools" element={<ToolsGrid />} />
            </Route>
            <Route path="/welcome/*" element={<Navigate to="/" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        ) : (
          <>
            <Route path="/welcome" element={<OnboardingLayout />}>
              <Route index element={<Welcome />} />
              <Route path="independence" element={<Independence />} />
              <Route path="meet" element={<Introduction />} />
              <Route path="profile" element={<Profile />} />
              <Route path="mac-setup" element={<MacSetup />} />
              <Route path="api-keys" element={<ApiKeys />} />
              <Route path="voice" element={<VoiceDemo />} />
              <Route path="chat" element={<ChatDemo />} />
              <Route path="tools" element={<ToolsOverview />} />
              <Route path="first-task" element={<GuidedFirstTask />} />
              <Route path="summary" element={<Summary />} />
              <Route path="launch" element={<Launch />} />
            </Route>
            <Route path="*" element={<Navigate to="/welcome" replace />} />
          </>
        )}
      </Routes>
    </BrowserRouter>
  );
}
