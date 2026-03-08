import { Outlet, NavLink } from "react-router-dom";
import { Orb } from "@/components/ui";

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

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
