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
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
