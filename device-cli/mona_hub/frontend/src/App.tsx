import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/welcome" element={<OnboardingLayout />}>
          <Route index element={<Welcome />} />
          <Route path="independence" element={<Independence />} />
          <Route path="meet" element={<Introduction />} />
          <Route path="voice" element={<VoiceDemo />} />
          <Route path="chat" element={<ChatDemo />} />
          <Route path="profile" element={<Profile />} />
          <Route path="mac-setup" element={<MacSetup />} />
          <Route path="api-keys" element={<ApiKeys />} />
          <Route path="tools" element={<ToolsOverview />} />
          <Route path="first-task" element={<GuidedFirstTask />} />
          <Route path="summary" element={<Summary />} />
          <Route path="launch" element={<Launch />} />
        </Route>
        <Route path="*" element={<Navigate to="/welcome" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
