import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { PageTransition, FadeUp, NeuCard, NeuButton } from "@/components/ui";
import {
  getSystemInfo,
  getInstalledTools,
  getInstalledModels,
  updateProgress,
} from "@/lib/api";
import type { SystemInfo, ToolInfo } from "@/lib/api";
import { childVariants } from "@/lib/animations";

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function BrainIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M12 2a4 4 0 0 1 4 4c0 1.1-.9 2-2 2h-4a2 2 0 0 1-2-2 4 4 0 0 1 4-4z" />
      <path d="M8 8v2a6 6 0 0 0 8 0V8" />
      <path d="M6 14a6 6 0 0 0 12 0" />
      <line x1="12" y1="14" x2="12" y2="22" />
      <line x1="9" y1="18" x2="15" y2="18" />
    </svg>
  );
}

function WrenchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <rect x="9" y="2" width="6" height="12" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="8" y1="22" x2="16" y2="22" />
    </svg>
  );
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  );
}

interface SummaryRow {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}

export function Summary() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<SummaryRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    updateProgress(10, "summary", true).catch(() => {});

    Promise.allSettled([
      getSystemInfo(),
      getInstalledTools(),
      getInstalledModels(),
    ]).then(([sysResult, toolsResult, modelsResult]) => {
      const profile = localStorage.getItem("mona_profile");
      const parsed = profile ? JSON.parse(profile) : null;

      const summaryRows: SummaryRow[] = [
        {
          icon: <UserIcon />,
          label: "Profile",
          value: parsed
            ? `${parsed.name ?? "Set up"}, ${parsed.language ?? "English"}, ${parsed.style ?? "Balanced"}`
            : "Set up",
        },
        {
          icon: <BrainIcon />,
          label: "Models",
          value:
            modelsResult.status === "fulfilled" && modelsResult.value.length > 0
              ? `${modelsResult.value.length} local models ready`
              : "Cloud API configured",
        },
        {
          icon: <WrenchIcon />,
          label: "Tools",
          value:
            toolsResult.status === "fulfilled"
              ? `${toolsResult.value.length} industry tools installed`
              : "Demo tools available",
        },
        {
          icon: <MicIcon />,
          label: "Voice",
          value: "3 languages supported",
        },
        {
          icon: <FolderIcon />,
          label: "Workspace",
          value: "~/OpenClawWorkspace/",
          mono: true,
        },
      ];

      setRows(summaryRows);
      setLoading(false);
    });
  }, []);

  return (
    <PageTransition fullHeight centered>
      <FadeUp className="mb-8">
        <h2 className="text-2xl font-light text-text-primary">
          Everything's configured.
        </h2>
      </FadeUp>

      <FadeUp className="w-full max-w-[480px]">
        <NeuCard variant="raised" padding="lg">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <motion.div
                className="h-6 w-6 rounded-full border-2 border-accent/30 border-t-accent"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />
            </div>
          ) : (
            <div className="flex flex-col">
              {rows.map((row, i) => (
                <div key={row.label}>
                  <div className="flex items-center gap-4 py-3">
                    <span className="flex-shrink-0 text-accent">
                      {row.icon}
                    </span>
                    <div className="flex flex-1 items-center justify-between gap-4">
                      <span className="text-sm font-medium text-text-secondary">
                        {row.label}
                      </span>
                      <span
                        className={`text-right text-sm text-text-primary ${
                          row.mono ? "font-mono text-xs" : ""
                        }`}
                      >
                        {row.value}
                      </span>
                    </div>
                  </div>
                  {i < rows.length - 1 && (
                    <div className="h-px bg-white/5" />
                  )}
                </div>
              ))}
            </div>
          )}
        </NeuCard>
      </FadeUp>

      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="mt-10"
      >
        <NeuButton size="lg" onClick={() => navigate("/welcome/launch")}>
          Launch Mona Hub →
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
