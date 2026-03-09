import { useState, useEffect, useCallback } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Orb, NeuCard, NeuButton } from "@/components/ui";
import { listConversations, deleteConversation, type ConversationInfo } from "@/lib/api";

function ChatIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

function GridIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function GearIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function PlusIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function TrashIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  );
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border-0 cursor-pointer select-none transition-colors ${
    isActive ? "text-accent" : "text-text-secondary hover:text-text-primary"
  }`;

const navLinkStyle = ({ isActive }: { isActive: boolean }) => ({
  background: isActive ? "var(--surface-inset)" : "transparent",
  boxShadow: isActive
    ? "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)"
    : "none",
});

export function DashboardLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const isChat = location.pathname === "/" || location.pathname.startsWith("/chat");
  const currentChatId = location.pathname.startsWith("/chat/") ? location.pathname.split("/")[2] : null;

  const [conversations, setConversations] = useState<ConversationInfo[]>([]);

  const refreshConversations = useCallback(() => {
    listConversations().then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    if (isChat) {
      refreshConversations();
    }
  }, [isChat, refreshConversations, location.pathname]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (confirm("Delete this conversation?")) {
      try {
        await deleteConversation(id);
        refreshConversations();
        if (currentChatId === id) {
          navigate("/");
        }
      } catch {}
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header
        className="sticky top-0 z-40 flex items-center gap-4 px-6 py-3 sm:px-8"
        style={{
          background: "var(--surface)",
          borderBottom: "1px solid color-mix(in srgb, var(--shadow-dark) 30%, transparent)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div className="flex items-center gap-3">
          <Orb size="sm" state="idle" />
          <span className="text-lg font-light text-text-primary tracking-wide">
            Mona
          </span>
        </div>

        <nav className="ml-6 flex items-center gap-2">
          <NavLink to="/" end className={navLinkClass} style={navLinkStyle}>
            <ChatIcon className="h-4 w-4" />
            Chat
          </NavLink>
          <NavLink to="/tools" className={navLinkClass} style={navLinkStyle}>
            <GridIcon className="h-4 w-4" />
            Tools
          </NavLink>
        </nav>

        <div className="flex-1" />

        <NavLink to="/settings" className={navLinkClass} style={navLinkStyle}>
          <GearIcon className="h-4 w-4" />
          Settings
        </NavLink>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          {isChat && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 280, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="flex flex-col border-r bg-surface overflow-hidden"
              style={{ borderColor: "color-mix(in srgb, var(--shadow-dark) 20%, transparent)" }}
            >
              <div className="p-4">
                <NeuButton
                  className="w-full flex items-center justify-center gap-2"
                  onClick={() => navigate("/chat/new")}
                >
                  <PlusIcon className="h-4 w-4" />
                  New Chat
                </NeuButton>
              </div>
              <div className="flex-1 overflow-y-auto px-2 pb-4">
                <div className="flex flex-col gap-1">
                  {conversations.map((conv) => (
                    <NavLink
                      key={conv.id}
                      to={`/chat/${conv.id}`}
                      className={({ isActive }) =>
                        `group flex flex-col gap-1 p-3 rounded-xl transition-colors ${
                          isActive
                            ? "bg-surface-inset text-accent"
                            : "text-text-secondary hover:bg-surface-inset hover:text-text-primary"
                        }`
                      }
                      style={({ isActive }) => ({
                        boxShadow: isActive
                          ? "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)"
                          : "none",
                      })}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-medium">
                          {conv.title}
                        </span>
                        <button
                          onClick={(e) => handleDelete(e, conv.id)}
                          className="opacity-0 group-hover:opacity-100 p-1 hover:text-error transition-all"
                        >
                          <TrashIcon className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <span className="text-[10px] opacity-50">
                        {new Date(conv.updated_at).toLocaleDateString()}
                      </span>
                    </NavLink>
                  ))}
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
