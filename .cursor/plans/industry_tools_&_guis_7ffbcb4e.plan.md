---
name: Industry Tools & GUIs
overview: Standardize all 48 prompt files, add sophisticated per-industry GUI sections to each, introduce a practice exam system for the student tool, and fix omissions across all prompts.
todos:
  - id: fix-paths
    content: "Fix file path inconsistency in prompts 05-12 (24 files): change ~/OpenClaw/tools/ to /opt/openclaw/skills/local/ and ~/OpenClawWorkspace/"
    status: completed
  - id: fix-headers
    content: "Standardize section headers in prompts 05-12: change '## Tool Name & Overview' to '## Overview', convert tech stack to tables"
    status: completed
  - id: fix-telegram
    content: Add Telegram Bot API as secondary messaging channel to all 35+ messaging-enabled prompts
    status: completed
  - id: fix-security
    content: Add security baseline (encryption, auth, PII masking, retention policy) to all 48 prompts
    status: completed
  - id: fix-logging
    content: Add standardized logging configuration to all 48 prompts referencing /var/log/openclaw/
    status: completed
  - id: update-readme
    content: "Update prompts/README.md with: GUI framework spec, inter-tool communication protocol, Mona activity protocol, design philosophy, health check spec, data export requirement"
    status: completed
  - id: gui-real-estate
    content: Add GUI Specification section to all 4 real-estate prompts (PropertyGPT, ListingSync, TenancyDoc, ViewingBot)
    status: completed
  - id: gui-immigration
    content: Add GUI Specification section to all 4 immigration prompts (VisaDoc OCR, FormAutoFill, PolicyWatcher, ClientPortal Bot)
    status: completed
  - id: gui-fnb
    content: Add GUI Specification section to all 4 F&B prompts (TableMaster, NoShowShield, QueueBot, SommelierMemory)
    status: completed
  - id: gui-accounting
    content: Add GUI Specification section to all 4 accounting prompts (InvoiceOCR, ReconcileAgent, TaxCalendar, FXTracker)
    status: completed
  - id: gui-legal
    content: Add GUI Specification section to all 4 legal prompts (LegalDoc, Discovery, Deadline, Intake)
    status: completed
  - id: gui-medical
    content: Add GUI Specification section to all 4 medical prompts (ClinicScheduler, MedReminder, ScribeAI, InsuranceAgent)
    status: completed
  - id: gui-construction
    content: Add GUI Specification section to all 4 construction prompts (PermitTracker, SafetyForm, Defects, SiteCoordinator)
    status: completed
  - id: gui-import-export
    content: Add GUI Specification section to all 4 import/export prompts (TradeDoc, Supplier, Stock, FXInvoice)
    status: completed
  - id: gui-academic
    content: Add GUI Specification section to all 4 academic prompts (PaperSieve, CiteBot, TranslateAssist, GrantTracker)
    status: completed
  - id: gui-vibe-coder
    content: Add GUI Specification section to all 4 vibe-coder prompts (CodeQwen, HKDevKit, DocuWriter, GitAssistant)
    status: completed
  - id: gui-solopreneur
    content: Add GUI Specification section to all 4 solopreneur prompts (BizOwner, MPFCalc, SocialSync, SupplierLedger)
    status: completed
  - id: gui-student
    content: Add GUI Specification section to all 4 existing student prompts + the new ExamGenerator
    status: completed
  - id: create-exam-generator
    content: Create prompts/12-student/exam-generator.md with full prompt (overview, features, tech stack, file structure, data model, GUI, testing criteria, implementation notes)
    status: completed
  - id: update-study-buddy
    content: Update study-buddy.md with ExamGenerator cross-reference in Key Integrations and shared index note
    status: completed
  - id: add-onboarding
    content: Add First-Run Setup section to all 48 prompts describing initial configuration wizard
    status: completed
  - id: add-health-export
    content: Add health check endpoint spec and data export requirement to all 48 prompts
    status: completed
isProject: false
---

# Industry-Specific Tool Overhaul: Prompt Fixes, GUIs, and Practice Exams

## Phase 1: Prompt Standardization (All 48 Files)

### 1A. File Path Inconsistency (Critical)

Prompts 01-04 use the correct canonical paths from the README:

- Code: `/opt/openclaw/skills/local/{tool-name}/`
- Data: `~/OpenClawWorkspace/{tool-name}/`
- Logs: `/var/log/openclaw/{tool-name}.log`

Prompts 05-12 use a **different, incorrect** path:

- `~/OpenClaw/tools/{tool-name}/` (wrong)

**Fix**: Update all 24 prompts in `05-legal/` through `12-student/` to use the canonical path structure from the README.

### 1B. Section Header Inconsistency

Prompts 01-04 use `## Overview`. Prompts 05-12 use `## Tool Name & Overview`.

**Fix**: Standardize all to `## Overview` (matches README's "Tool Name and Overview" description but keeps the H1 title as the tool name).

### 1C. Tech Stack Format Inconsistency

Prompts 01-04 use markdown tables for tech stack. Prompts 05-12 use bullet lists.

**Fix**: Standardize all to markdown tables (more scannable, matches prompts 01-04).

### 1D. Missing Telegram Support

The [README](prompts/README.md) states all tools use "WhatsApp Business API (Twilio), Telegram Bot API" but only `02-immigration/client-portal-bot.md` mentions Telegram. All client-facing messaging tools should include Telegram as a secondary channel.

**Fix**: Add Telegram Bot API as a secondary messaging channel to all tools that use WhatsApp (roughly 35 of 48 prompts). Add a `telegram.py` to each tool's messaging module.

### 1E. Missing Logging Configuration

README specifies `/var/log/openclaw/{tool-name}.log`. Only PropertyGPT references this.

**Fix**: Add a standard logging note to every prompt's Implementation Notes section referencing the canonical log path and recommending `logging` module with rotation.

### 1F. Missing Security Baseline

Some prompts mention SQLite encryption and PDPO compliance; most do not.

**Fix**: Add a "Security and Privacy" subsection to each prompt's Implementation Notes:

- All SQLite databases storing personal/financial data: encrypt at rest (sqlcipher or filesystem-level encryption)
- All local web dashboards: require local authentication (PIN or passphrase on first access)
- All logs: mask PII (phone numbers, HKID, names)
- Data retention policy: configurable auto-purge

---

## Phase 2: Common GUI Infrastructure

### 2A. Shared GUI Framework

Add a new section to [prompts/README.md](prompts/README.md) defining the shared GUI architecture:

- **Unified launcher**: A local "Mona Hub" landing page (simple FastAPI app) that lists all installed industry tools with status indicators (running/stopped/error) and links to each industry dashboard
- **Per-industry dashboards**: Each industry gets ONE unified dashboard (12 total) with tabbed/sidebar navigation for its 4 tools
- **Tech choice per complexity**:
  - Tools 01-04 (Real Estate, Immigration, F&B, Accounting): FastAPI + Jinja2 + htmx + Tailwind CSS (needs real-time updates, rich form interactions)
  - Tools 05-08 (Legal, Medical, Construction, Import/Export): Streamlit with custom components (data-heavy, chart-heavy)
  - Tools 09-12 (Academic, Coder, Solopreneur, Student): Streamlit with streamlit-ace and custom widgets (interactive editors, visualizations)
- **Shared design tokens**: Consistent color scheme, typography, spacing across all dashboards (MonoClaw brand: dark navy + warm gold accents)
- **Local network access**: All dashboards accessible via `http://mona.local:{port}` for access from any device on the same network (phone, tablet, laptop)

### 2B. GUI Design Philosophy (Add to README)

Every GUI operates in two modes:

1. **Manual Mode**: The client can perform any task directly through the GUI without Mona -- creating entries, uploading documents, running calculations, reviewing data. The GUI has standalone value as a polished SaaS-quality product.
2. **Mona-Assisted Mode**: When Mona is active, the GUI becomes a verification and visualization layer. Mona auto-populates fields, triggers workflows, processes documents, and surfaces results. The GUI shows Mona's activity feed, highlights items needing human approval, and visualizes outputs that would otherwise only exist as WhatsApp messages.

Key UI patterns across all dashboards:

- **Activity Feed**: Real-time log of Mona's actions with timestamps
- **Approval Queue**: Items awaiting human review/override (amber badges)
- **Status Cards**: At-a-glance KPIs for each tool (green/amber/red)
- **Quick Actions**: One-click buttons for the most common manual tasks
- **Settings Panel**: Per-tool configuration (API keys, thresholds, preferences)

### 2C. Inter-Tool Communication Protocol

Add a new section to the README specifying how sibling tools communicate:

- **Shared SQLite databases**: Tools within the same industry that reference each other (e.g., VisaDoc OCR to FormAutoFill) share a common database file for the data they exchange
- **Internal REST API**: Each tool exposes a lightweight FastAPI endpoint for cross-tool triggers (e.g., TableMaster notifies NoShowShield of a new booking via `POST /api/internal/booking-created`)
- **File system signals**: For simpler cases, tools watch shared directories (e.g., VisaDoc OCR writes extracted JSON to a folder that FormAutoFill monitors)

### 2D. Onboarding/Setup Wizard

Add a `## First-Run Setup` section to each prompt describing:

- Initial configuration wizard (business name, API keys, preferences)
- Sample data seeding for demo/testing
- Connection tests for external integrations (Twilio, accounting software, etc.)

---

## Phase 3: Per-Industry GUI Specifications

Each prompt gets a new `## GUI Specification` section inserted after `## Key Integrations`. Below are the 12 industry dashboard designs.

### 3.1 Real Estate Dashboard (FastAPI + htmx)

**Port**: 8001 | **URL**: `http://mona.local:8001`

**PropertyGPT Tab**:

- Semantic search bar with district/price/bedroom filters
- Property detail cards with transaction history sparklines
- Comparison table (side-by-side selected properties)
- Chat panel for natural language Q&A (streaming responses)
- Floor plan viewer with OCR-extracted room dimensions overlay

**ListingSync Tab**:

- Master listing editor (form with image drag-drop gallery)
- Multi-platform status grid: rows = listings, columns = platforms (28Hse, Squarefoot, WhatsApp), cells show post status with colored indicators
- Image processing preview: before/after watermark, per-platform resize thumbnails
- Performance charts: views and inquiries per platform over time
- One-click "Sync All" and per-platform manual post buttons

**TenancyDoc Tab**:

- Step-by-step tenancy agreement wizard (landlord details, tenant details, property, terms, special conditions)
- Live document preview pane (rendered PDF updating as fields are filled)
- Stamp duty calculator widget (auto-updates as term/rent change)
- Renewal calendar view with color-coded urgency (green >90 days, amber 30-90, red <30)
- Document archive table with version history and download links

**ViewingBot Tab**:

- Weekly calendar view with viewing appointments (color-coded by status)
- District map showing today's viewings with route optimization line
- Three-party coordination status board (viewer confirmed? landlord confirmed? agent available?)
- Follow-up tracker: post-viewing responses with interest level tags
- Typhoon/rainstorm auto-cancellation banner (live from HKO API)

### 3.2 Immigration Dashboard (FastAPI + htmx)

**Port**: 8002 | **URL**: `http://mona.local:8002`

**VisaDoc OCR Tab**:

- Document upload zone (drag-drop or WhatsApp-received queue)
- Side-by-side viewer: original document image (zoomable) | extracted structured data (editable fields)
- Per-field confidence indicators (green >85%, amber 70-85%, red <70%)
- Batch processing queue with progress bars
- "Approve and Send to FormAutoFill" action button

**FormAutoFill Tab**:

- Client selector dropdown with profile summary card
- Scheme/form type selector (GEP, ASMTP, QMAS, IANG, ID990A/B)
- Field-by-field form preview with validation state (green checkmark / red X per field)
- PDF preview pane showing the actual filled government form
- Submission checklist with check-off states and missing document alerts
- Batch processing view for corporate multi-visa filings

**PolicyWatcher Tab**:

- Policy change timeline (chronological feed of detected changes)
- Diff viewer for policy text changes (red deletions, green additions)
- Alert configuration panel (which schemes to monitor, notification preferences)
- Impact assessment cards: which active clients are affected by a policy change

**ClientPortal Bot Tab**:

- Client case list with status badges (submitted, processing, approved, rejected)
- Per-client timeline showing all milestones and communications
- Message history viewer (WhatsApp + Telegram threads)
- Quick-reply composer for manual client updates

### 3.3 F&B Dashboard (FastAPI + htmx + WebSocket)

**Port**: 8003 | **URL**: `http://mona.local:8003`

**TableMaster Tab**:

- **Interactive floor plan**: Drag-and-drop table layout editor. Tables colored by status (green=available, blue=reserved, orange=occupied, grey=clearing). Click table to see booking details. Combine tables by dragging one onto another.
- Booking list view with channel icons (WhatsApp, IG, OpenRice, phone, walk-in)
- Real-time channel inbox: incoming booking requests with parsed data preview and "Confirm/Decline/Suggest Alternative" buttons
- Daily/weekly booking heatmap showing peak times

**NoShowShield Tab**:

- Confirmation pipeline: visual board showing each booking's confirmation stage (sent -> delivered -> confirmed/unconfirmed)
- Guest reliability cards: search guests, view history, reliability grade (A/B/C/D), override controls
- Waitlist queue: ranked list with "Offer Table" manual trigger
- No-show prediction dashboard: today's bookings ranked by risk score with explanations

**QueueBot Tab**:

- Live queue display (designed for waiting room TV): position, estimated wait, party size
- QR code generator for queue joining
- Queue management controls: add walk-in, call next, skip, remove
- Wait time analytics chart

**SommelierMemory Tab**:

- Guest CRM cards with expandable preference details (dietary restrictions, favorite dishes, wine preferences, celebration dates)
- Upcoming celebrations calendar (birthdays, anniversaries)
- Guest tagging and search interface
- Visit history timeline per guest

### 3.4 Accounting Dashboard (FastAPI + htmx)

**Port**: 8004 | **URL**: `http://mona.local:8004`

**InvoiceOCR Tab**:

- Three-column layout: incoming queue | OCR result editor | accounting push controls
- Invoice viewer: zoomable image alongside extracted fields (supplier, date, amount, line items)
- Editable extraction results with auto-categorization (overridable dropdown)
- Duplicate detection banner with link to matching existing invoice
- Batch action bar: approve selected, push to Xero/ABSS/QuickBooks
- Processing statistics: today's count, accuracy rate, time saved estimate

**ReconcileAgent Tab**:

- Bank statement upload area (drag-drop CSV/PDF)
- Three-pane matching interface: unmatched bank entries | auto-matched pairs (review) | unmatched book entries
- Manual matching: drag a bank entry to a book entry to create a match
- Reconciliation summary: matched total, unmatched total, variance
- Historical reconciliation reports by month

**TaxCalendar Tab**:

- Calendar view with all HK tax deadlines (Profits Tax, Employer's Return, MPF, Business Registration renewal)
- Countdown cards for the next 3 upcoming deadlines
- Per-deadline checklist (required documents, preparation steps)
- Filing status tracker (not started, in progress, filed, acknowledged)

**FXTracker Tab**:

- Live exchange rate display for HKD/USD/CNY/EUR/GBP (from HKMA TMA)
- Multi-currency transaction log with auto-converted HKD equivalents
- Realized/unrealized FX gains and losses report
- Rate alert configuration (notify when a rate crosses a threshold)

### 3.5 Legal Dashboard (Streamlit)

**Port**: 8501 | **URL**: `http://mona.local:8501`

**LegalDoc Analyzer Tab**:

- Document upload with type selector (tenancy, employment, NDA, service agreement)
- Clause-by-clause view: clause text with colored sidebar (green=standard, amber=unusual, red=anomalous)
- Anomaly detail panel: when a clause is flagged, show the reference standard clause side-by-side with the deviation explanation
- Comparison mode: two-document side-by-side with diff highlighting
- Annotated document export (.docx with track changes)

**DiscoveryAssistant Tab**:

- Document collection browser with search and filter
- Privilege tagger: flag documents as privileged, confidential, or responsive
- Keyword search with highlighted results
- Timeline view of document dates for chronological discovery

**DeadlineGuardian Tab**:

- Matter list with active limitation periods and court deadlines
- Calendar view with deadline types color-coded (court filing, limitation, contractual)
- Limitation period calculator: select ordinance + trigger event, get deadline
- Reminder configuration per matter

**IntakeBot Tab**:

- New client intake form (contact details, matter type, brief description)
- Conflict check results panel (shows potential conflicts with existing clients/matters)
- WhatsApp/WeChat conversation viewer for intake messages
- Client onboarding status tracker

### 3.6 Medical Dashboard (Streamlit)

**Port**: 8502 | **URL**: `http://mona.local:8502`

**ClinicScheduler Tab**:

- Doctor schedule grid: rows = time slots, columns = doctors, cells = appointments (click to view/edit)
- Appointment booking form (manual entry for phone/walk-in)
- Waitlist panel with priority indicators
- Walk-in queue view (for waiting room display mode: fullscreen, large fonts)
- Today's statistics: total appointments, no-shows, walk-ins

**MedReminder Tab**:

- Patient medication schedule table
- Reminder status: sent, acknowledged, missed
- Refill tracking with days-remaining indicators
- Bulk reminder configuration

**ScribeAI Tab**:

- **Recording interface**: Start/stop recording button, live waveform display, real-time transcription text stream
- SOAP note editor with four collapsible sections (Subjective, Objective, Assessment, Plan)
- Entity extraction sidebar: auto-detected medications, diagnoses, and procedures as clickable tags
- ICD-10 code suggestions with search
- Finalization workflow: review -> approve -> lock (with immutable audit trail)
- Template selector for common consultation types

**InsuranceAgent Tab**:

- Insurance verification form (policy number, insurer, patient details)
- Coverage lookup results: covered procedures, co-pay amounts, exclusions
- Pre-authorization request builder and status tracker
- Claim submission helper with required document checklist

### 3.7 Construction Dashboard (Streamlit)

**Port**: 8503 | **URL**: `http://mona.local:8503`

**PermitTracker Tab**:

- Gantt chart: all submissions plotted against expected BD timelines (actual progress overlaid)
- Submission detail cards: BD reference, type, status, last checked, days elapsed
- Status change alert history log
- Document archive per submission (correspondence, plans, amendments)

**SafetyForm Tab**:

- Daily safety checklist interface (checkboxes + photo attachment per item)
- SSSS report generator: one-click generation from completed checklists
- Toolbox talk record form with attendance tracking
- Compliance calendar: required inspection dates, audit dates

**DefectsManager Tab**:

- Defect log with photo gallery (take photo from device, annotate, submit)
- Defect detail view: photo, description, location, severity, assigned party, resolution status
- Work order generation from defect entries
- DMC responsibility matrix view
- Analytics: defects by type, resolution time trends

**SiteCoordinator Tab**:

- Subcontractor schedule (weekly view, rows = subcontractors, columns = days)
- WhatsApp dispatch log: sent instructions and read receipts
- Delivery schedule with ETA tracking
- Site access log

### 3.8 Import/Export Dashboard (Streamlit)

**Port**: 8504 | **URL**: `http://mona.local:8504`

**TradeDoc AI Tab**:

- HS code lookup/classifier: product description input, suggested codes with confidence, manual override
- TDEC form builder: guided form with auto-populated fields from product catalog
- Commercial invoice builder with Incoterms dropdown and multi-currency support
- CO application form with CEPA eligibility check
- Strategic commodities screening alert banner (red warning if flagged)
- Filing status tracker (draft/filed/accepted/rejected)

**SupplierBot Tab**:

- Supplier directory with contact details and communication history
- Message composer with auto-translation (EN to ZH-SC for mainland suppliers)
- Order status board per supplier
- Price comparison across suppliers for the same product

**StockReconcile Tab**:

- Manifest upload and parsing interface
- Receipt matching view: manifest items vs received items, highlight discrepancies
- Shortage/overage report with per-item details
- Historical reconciliation accuracy trend

**FXInvoice Tab**:

- Multi-currency invoice builder (line items can be in different currencies)
- Live FX rate lookup and conversion
- Payment tracking per invoice
- FX gain/loss calculation on settlement

### 3.9 Academic Dashboard (Streamlit)

**Port**: 8505 | **URL**: `http://mona.local:8505`

**PaperSieve Tab**:

- Paper library browser with search, tag filters, and sort options
- Full-text semantic search with highlighted passage results and citations
- Q&A chat interface (RAG pipeline) with inline citations that link to source passages
- Knowledge graph visualization (interactive node graph, zoomable)
- Systematic review workflow: PRISMA flow diagram, screening interface, data extraction forms

**CiteBot Tab**:

- Bibliography manager: add papers manually or import from PaperSieve
- Citation style selector (APA, IEEE, Harvard, GB/T 7714, Vancouver)
- Formatted bibliography preview with copy-to-clipboard
- In-text citation generator

**TranslateAssist Tab**:

- Side-by-side translation editor (source left, translation right)
- Domain term glossary panel (editable, auto-populated from paper corpus)
- Translation memory: previously translated phrases for consistency
- Quality indicators for machine translation confidence

**GrantTracker Tab**:

- Grant deadline calendar (RGC, ITF, NSFC, ECS, GRF)
- Application status board per grant
- Budget calculator and co-PI management
- Form auto-fill for common RGC grant applications

### 3.10 Vibe Coder Dashboard (FastAPI + custom web UI)

**Port**: 8010 | **URL**: `http://mona.local:8010`

**CodeQwen Tab**:

- Code editor (Monaco-based) with inline completions and suggestion panel
- Side panel: explanation view, refactoring suggestions, bug detection results
- Chat interface for code Q&A (streaming responses)
- Session history with replayable conversations

**HKDevKit Tab**:

- API connector gallery: FPS, Octopus, GovHK, eTAX
- Boilerplate generator: select framework + APIs, generate project scaffold
- Integration documentation viewer
- API testing interface (send test requests, view responses)

**DocuWriter Tab**:

- Project file tree browser
- Generated documentation viewer (rendered markdown)
- Documentation style configuration (API docs, user guides, READMEs)
- Diff view: current docs vs regenerated version

**GitAssistant Tab**:

- Repo selector and recent commits list
- PR description generator: select commits, generate summary
- Release notes builder: select version range, generate changelog
- Issue labeling suggestions for open issues

### 3.11 Solopreneur Dashboard (Streamlit)

**Port**: 8506 | **URL**: `http://mona.local:8506`

**BizOwner OS Tab**:

- **Boss Mode** (default view): Three big numbers -- today's revenue, pending messages, cash position
- Revenue trend chart (daily/weekly/monthly toggle)
- WhatsApp inbox with auto-response status indicators
- Quick action buttons: record expense, add sale, broadcast message

**MPFCalc Tab**:

- Employee table with salary and classification details
- Monthly contribution calculator (auto-calculated, editable overrides)
- Remittance statement preview and PDF download
- Compliance dashboard: upcoming contribution day countdown, late payment warnings
- "What-if" calculator for new hire cost estimation

**SocialSync Tab**:

- Post composer: rich text editor with image upload
- Multi-platform preview: side-by-side IG, FB, WhatsApp renderings
- Content calendar (drag-drop posts to schedule)
- Engagement analytics per platform

**SupplierLedger Tab**:

- Supplier directory with outstanding balances
- Payables aging report (current, 30 days, 60 days, 90+ days)
- Receivables tracker with invoice status
- Cash flow forecast chart (projected inflows/outflows)

### 3.12 Student Dashboard (Streamlit)

**Port**: 8507 | **URL**: `http://mona.local:8507`

**StudyBuddy Tab**:

- Course organizer: semester/course/topic hierarchy browser
- Document uploader with batch import
- Semantic search with citation-linked results
- Q&A chat (RAG) with source highlighting
- Flashcard review mode: spaced repetition with flip animation
- Summary viewer: chapter summaries at configurable detail levels

**ExamGenerator Tab (NEW)** -- see Phase 4 below.

**InterviewPrep Tab**:

- Problem browser with topic/difficulty filters
- Code editor (streamlit-ace) with syntax highlighting and test case runner
- Progressive hint system (3-level reveal buttons)
- Solution explanation panel with complexity analysis
- Mock interview mode: timer, no-hint lock, performance scorecard
- Progress dashboard: solve rate per topic, weak area radar chart, streak counter

**JobTracker Tab**:

- Kanban board: Saved | Applied | Screening | Interview | Offer | Accepted/Rejected (drag-drop cards)
- Job detail panel: parsed JD, match score gauge, missing keywords list
- Cover letter editor with AI draft generation
- Interview calendar with reminder status
- Analytics: application funnel chart, response rate trend, time-to-response distribution

**ThesisFormatter Tab**:

- University template selector (HKU, CUHK, HKUST, PolyU, CityU, HKBU, LingU, EdUHK)
- Document upload and validation results (margin check, font check, citation format check)
- Table of contents auto-generator
- Formatting fix suggestions with one-click apply

---

## Phase 4: Practice Exam System (12-student)

### 4A. New Prompt: `exam-generator.md`

Create a new prompt file at [prompts/12-student/exam-generator.md](prompts/12-student/exam-generator.md) OR extend [prompts/12-student/study-buddy.md](prompts/12-student/study-buddy.md) with a major new feature section. Given the scope, a **standalone prompt** is cleaner.

### 4B. Core Features

- **Exam Generation Engine**:
  - **From Past Papers**: Upload past exam PDFs (scanned or digital). OCR and parse into structured question format. Detect question types, point values, and sections. Optionally randomize question order for fresh practice.
  - **From Course Materials**: Using the StudyBuddy RAG index, generate questions from indexed content. LLM produces questions targeting specific knowledge points. Uses Bloom's taxonomy levels to control difficulty (Remember, Understand, Apply, Analyze, Evaluate, Create).
  - **Custom Requirements**: Student specifies scope constraints -- chapter range, specific topics, difficulty distribution (e.g., "40% easy, 40% medium, 20% hard"), question count, time limit.
  - **Question Types**:
    - Multiple Choice (4 options, 1 correct): LLM generates plausible distractors based on common misconceptions
    - Multiple Select (4-6 options, 2+ correct): for nuanced understanding
    - Short Answer: 1-3 sentence response expected
    - Long Answer / Essay: paragraph-level response, rubric-graded
    - Calculation / Problem-Solving: for STEM subjects, with step-by-step solution
    - True/False with justification
  - **Subject Flexibility**: The system must be discipline-agnostic. The question generation prompts adapt based on the course subject: STEM (formulas, calculations, diagrams), humanities (essay analysis, source interpretation), social sciences (case studies, theory application), languages (translation, grammar), business (case analysis, calculations), law (issue spotting, case application).
- **Exam Taking Interface**:
  - Clean, distraction-free exam view (fullscreen option)
  - Question navigation sidebar with answered/unanswered/flagged indicators
  - Timer display (configurable: countdown, count-up, or hidden)
  - MCQ: radio/checkbox selection
  - Free answer: rich text editor with basic formatting
  - Calculation: text input with LaTeX rendering for math expressions
  - "Flag for Review" button per question
  - Auto-save every 30 seconds to prevent data loss
  - Submit button with confirmation dialog
- **Grading and Feedback**:
  - MCQ/True-False: instant auto-grade on submission
  - Free answer grading: LLM evaluates against a rubric derived from source material. Scores on a scale (full marks, partial, zero) with written justification.
  - Calculation: LLM checks final answer AND intermediate steps; partial credit for correct methodology
  - Per-question feedback: what was correct, what was wrong, reference to the source material (page, section) where the answer can be found
  - Overall score, breakdown by topic and difficulty, comparison with past attempts
  - Grade trend chart across multiple exam attempts
- **Post-Exam Discussion Mode**:
  - Chat interface with Mona focused on the completed exam
  - Mona has context: the questions, student's answers, correct answers, grading rubric, and source materials
  - Student can ask about any specific question ("Why was option B wrong?")
  - Mona uses Socratic method: guides the student to understand rather than just giving answers
  - Mona can generate follow-up questions on weak areas identified in the exam
  - Conversation is saved and linked to the exam attempt for future review

### 4C. Data Model Addition

```sql
CREATE TABLE exams (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    title TEXT,
    generation_source TEXT CHECK(generation_source IN ('past_paper','course_materials','custom','mixed')),
    scope_config TEXT,  -- JSON: chapters, topics, difficulty distribution
    question_count INTEGER,
    time_limit_minutes INTEGER,
    status TEXT CHECK(status IN ('generating','ready','in_progress','completed','reviewed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE exam_questions (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exams(id),
    question_index INTEGER,
    question_type TEXT CHECK(question_type IN ('mcq','multi_select','short_answer','long_answer','calculation','true_false')),
    question_text TEXT,
    options TEXT,          -- JSON array (for MCQ/multi-select)
    correct_answer TEXT,   -- JSON (answer key or rubric)
    source_chunks TEXT,    -- JSON array of chunk IDs from StudyBuddy index
    difficulty TEXT CHECK(difficulty IN ('easy','medium','hard')),
    topic TEXT,
    points REAL DEFAULT 1.0,
    bloom_level TEXT
);

CREATE TABLE exam_attempts (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exams(id),
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    time_spent_seconds INTEGER,
    total_score REAL,
    max_score REAL,
    percentage REAL,
    topic_breakdown TEXT,  -- JSON: per-topic scores
    feedback_summary TEXT,
    status TEXT CHECK(status IN ('in_progress','submitted','graded','reviewed'))
);

CREATE TABLE attempt_answers (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER REFERENCES exam_attempts(id),
    question_id INTEGER REFERENCES exam_questions(id),
    student_answer TEXT,
    is_correct BOOLEAN,
    score REAL,
    max_score REAL,
    feedback TEXT,
    source_reference TEXT,  -- citation to source material
    flagged_for_review BOOLEAN DEFAULT FALSE
);

CREATE TABLE exam_discussions (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER REFERENCES exam_attempts(id),
    question_id INTEGER,   -- NULL if general discussion
    role TEXT CHECK(role IN ('student','mona')),
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4D. Integration with StudyBuddy

ExamGenerator reuses StudyBuddy's ChromaDB index and course organization:

- Questions are generated from the same indexed chunks that power Q&A
- Source references link back to the same documents
- The exam performance data feeds into StudyBuddy's flashcard generation (weak areas get more flashcards)
- Course organization (semester/course/topic) is shared

### 4E. Update `study-buddy.md`

Add a cross-reference to the new ExamGenerator tool:

- "ExamGenerator (sibling tool)" in Key Integrations
- Shared ChromaDB index and course database
- Exam performance feeds flashcard priority

---

## Phase 5: Additional Improvements

### 5A. Mona Activity Protocol (Add to README)

Add a specification for how Mona communicates with the GUI:

- Each tool writes structured events to a local event bus (SQLite `mona_events` table or Unix socket)
- Events include: `action_started`, `action_completed`, `approval_needed`, `error`, `alert`
- The GUI polls or subscribes to the event bus for the Activity Feed and Approval Queue

### 5B. Data Export/Portability (Add to each prompt)

Every tool must support exporting all client data in a portable format (JSON + files) for:

- Client migration (switching away from MonoClaw)
- Backup to external storage
- Compliance with PDPO data access requests

### 5C. Health Check Endpoint (Add to each prompt)

Every tool's FastAPI/Streamlit server exposes a `/health` endpoint returning:

- Tool name and version
- Uptime
- Database status
- Last successful operation timestamp
- LLM model status (loaded/unloaded/error)
- Memory usage

The Mona Hub launcher aggregates these health checks for the client dashboard.

---

## Files to Create / Modify

**New files**:

- `prompts/12-student/exam-generator.md` (new tool prompt)

**Modified files (all 48 + README)**:

- `prompts/README.md` -- add GUI framework, inter-tool protocol, Mona activity protocol, design philosophy sections
- All 24 prompts in `05-`* through `12-`* -- fix file paths, section headers, tech stack format
- All 48 prompts -- add `## GUI Specification`, `## First-Run Setup`, security baseline, logging config, Telegram support, data export, health check
- `prompts/12-student/study-buddy.md` -- add ExamGenerator cross-reference

