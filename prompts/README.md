# MonoClaw Coding Agent Prompts

Self-contained prompts for coding agents to implement MonoClaw's industry-specific productivity software. Each tool runs locally on Mac M4 (16GB RAM) within the OpenClaw framework.

## Directory Structure

Prompts are organized by industry vertical and client persona:

### Business Verticals
- `01-real-estate/` — PropertyGPT, ListingSync, TenancyDoc, ViewingBot
- `02-immigration/` — VisaDoc OCR, FormAutoFill, PolicyWatcher, ClientPortal Bot
- `03-fnb-hospitality/` — TableMaster AI, NoShowShield, QueueBot, SommelierMemory
- `04-accounting/` — InvoiceOCR Pro, ReconcileAgent, TaxCalendar Bot, FXTracker
- `05-legal/` — LegalDoc Analyzer, DiscoveryAssistant, DeadlineGuardian, IntakeBot
- `06-medical-dental/` — ClinicScheduler, MedReminder Bot, ScribeAI, InsuranceAgent
- `07-construction/` — PermitTracker, SafetyForm Bot, DefectsManager, SiteCoordinator
- `08-import-export/` — TradeDoc AI, SupplierBot, StockReconcile, FXInvoice

### Client Personas
- `09-academic/` — PaperSieve, CiteBot, TranslateAssist, GrantTracker
- `10-vibe-coder/` — CodeQwen-9B, HKDevKit, DocuWriter, GitAssistant
- `11-solopreneur/` — BizOwner OS, MPFCalc, SocialSync, SupplierLedger
- `12-student/` — StudyBuddy, ExamGenerator, InterviewPrep, JobTracker, ThesisFormatter

## Common Architecture

All tools share:
- **Runtime**: Python 3.11+ on macOS ARM64
- **LLM**: MLX-based local inference via `/opt/openclaw/models/`
- **Config**: `/opt/openclaw/skills/local/{tool-name}/`
- **Data**: `~/OpenClawWorkspace/{tool-name}/`
- **Logging**: `/var/log/openclaw/{tool-name}.log`
- **Communication**: WhatsApp Business API (Twilio), Telegram Bot API
- **Database**: Local SQLite for tool-specific data
- **OCR**: macOS Vision framework for document processing

## Prompt Format

Each prompt contains:
1. **Overview** — what the tool does in 2-3 sentences
2. **Target User** — who uses this tool
3. **Core Features** — 4-6 capabilities with descriptions
4. **Tech Stack** — Python libraries, APIs, frameworks (markdown table)
5. **File Structure** — where it lives in OpenClaw
6. **Key Integrations** — external services and APIs
7. **GUI Specification** — local web dashboard interface design
8. **HK-Specific Requirements** — regulations, formats, conventions
9. **Data Model** — SQLite tables and schemas
10. **First-Run Setup** — onboarding wizard and initial configuration
11. **Testing Criteria** — verification checklist
12. **Implementation Notes** — hardware, privacy, security, and logging constraints

## GUI Architecture

### Design Philosophy

Every tool GUI operates in two modes:

1. **Manual Mode**: The client can perform any task directly through the GUI without Mona — creating entries, uploading documents, running calculations, reviewing data. The GUI has standalone value as a polished, product-grade interface.
2. **Mona-Assisted Mode**: When Mona is active, the GUI becomes a verification and visualization layer. Mona auto-populates fields, triggers workflows, processes documents, and surfaces results. The GUI shows Mona's activity feed, highlights items needing human approval, and visualizes outputs that would otherwise only exist as WhatsApp messages.

### Shared UI Patterns

All dashboards implement these common patterns:

- **Activity Feed**: Real-time log of Mona's actions with timestamps (visible in both modes; empty in Manual Mode)
- **Approval Queue**: Items awaiting human review or override, shown as amber-badged cards
- **Status Cards**: At-a-glance KPIs for each tool (green/amber/red health indicators)
- **Quick Actions**: One-click buttons for the most common manual tasks
- **Settings Panel**: Per-tool configuration (API keys, thresholds, notification preferences)
- **Bilingual Toggle**: All UI text supports English and Traditional Chinese

### Unified Launcher — Mona Hub

A local FastAPI landing page (`http://mona.local:8000`) lists all installed industry tools with:
- Status indicator per tool (running / stopped / error)
- Quick-launch links to each industry dashboard
- Aggregated health checks from all tools
- System resource usage (RAM, disk, LLM model status)

### Per-Industry Dashboards

Each industry gets ONE unified dashboard with tabbed or sidebar navigation for its 4-5 tools. Tech choice per complexity:

| Industries | Tech Stack | Ports |
|---|---|---|
| 01 Real Estate, 02 Immigration, 03 F&B, 04 Accounting | FastAPI + Jinja2 + htmx + Tailwind CSS | 8001-8004 |
| 05 Legal, 06 Medical, 07 Construction, 08 Import/Export | Streamlit with custom components | 8501-8504 |
| 09 Academic, 11 Solopreneur, 12 Student | Streamlit with streamlit-ace and custom widgets | 8505-8507 |
| 10 Vibe Coder | FastAPI + Monaco editor + custom web UI | 8010 |

### Shared Design Tokens

All dashboards use consistent MonoClaw branding:
- **Primary**: Dark navy (#1a1f36)
- **Accent**: Warm gold (#d4a843)
- **Success/Warning/Error**: Standard green/amber/red
- **Typography**: Inter (UI), JetBrains Mono (code), Noto Sans CJK (Chinese text)
- **Spacing**: 8px grid system

### Local Network Access

All dashboards are accessible via `http://mona.local:{port}` from any device on the same local network (phone, tablet, laptop), enabling clients to interact from their preferred device.

## Inter-Tool Communication Protocol

Tools within the same industry may reference each other as "sibling tools." They communicate through:

1. **Shared SQLite databases**: Tools that exchange data (e.g., VisaDoc OCR → FormAutoFill) share a common database file located at `~/OpenClawWorkspace/{industry}/shared.db` for the data they exchange.
2. **Internal REST API**: Each tool exposes a lightweight FastAPI endpoint at `/api/internal/` for cross-tool event triggers (e.g., TableMaster notifies NoShowShield of a new booking via `POST /api/internal/booking-created`).
3. **File system signals**: For document handoffs, tools write to shared directories that sibling tools monitor via `watchdog` (e.g., VisaDoc OCR writes extracted JSON to a folder that FormAutoFill watches).

## Mona Activity Protocol

Each tool writes structured events to a local SQLite table (`~/OpenClawWorkspace/{tool-name}/mona_events.db`) for the GUI to consume:

```sql
CREATE TABLE mona_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT CHECK(event_type IN ('action_started','action_completed','approval_needed','error','alert','info')),
    tool_name TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT,
    requires_human_action BOOLEAN DEFAULT FALSE,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

The GUI polls this table (or subscribes via filesystem notify) to populate the Activity Feed and Approval Queue. Events with `requires_human_action = TRUE` appear as amber-badged items in the Approval Queue until acknowledged.

## Health Check Endpoint

Every tool exposes a `GET /health` endpoint (FastAPI) or equivalent (Streamlit component) returning:

```json
{
  "tool": "property-gpt",
  "version": "1.0.0",
  "status": "healthy",
  "uptime_seconds": 3600,
  "database": "ok",
  "llm_model": "loaded",
  "memory_mb": 5200,
  "last_operation": "2026-03-05T10:30:00+08:00"
}
```

The Mona Hub launcher aggregates these for the system-wide health dashboard.

## Data Export & Portability

Every tool must support exporting all client data in a portable format for:
- **Client migration**: Full JSON + file export of all tool data
- **Backup**: Scheduled export to external storage
- **PDPO compliance**: Data access requests under Hong Kong's Personal Data (Privacy) Ordinance

Export is triggered via the GUI Settings panel or the API endpoint `POST /api/export`.

## Security Baseline

All tools implement:
- **Database encryption**: SQLite databases storing personal or financial data use SQLCipher or filesystem-level encryption
- **Dashboard authentication**: Local PIN or passphrase required on first access; session persists for configurable duration
- **PII masking in logs**: Phone numbers, HKID, names, and financial data are masked in all log output
- **Data retention**: Configurable auto-purge policy per tool (default: 24 months for business data, 90 days for processed images)
- **Audit trail**: All data access and modifications logged to `/var/log/openclaw/{tool-name}.log`

## Usage

Give any single prompt file to a coding agent. Each prompt is self-contained with enough context to implement the tool from scratch within the OpenClaw framework.

```bash
# Example: hand a prompt to your coding agent
cat prompts/01-real-estate/property-gpt.md
```
