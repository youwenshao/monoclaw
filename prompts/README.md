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
- `12-student/` — StudyBuddy, InterviewPrep, JobTracker, ThesisFormatter

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
1. **Tool Name & Overview** — what it does in 2-3 sentences
2. **Target User** — who uses this tool
3. **Core Features** — 4-6 capabilities with descriptions
4. **Tech Stack** — Python libraries, APIs, frameworks
5. **File Structure** — where it lives in OpenClaw
6. **Key Integrations** — external services and APIs
7. **HK-Specific Requirements** — regulations, formats, conventions
8. **Data Model** — SQLite tables and schemas
9. **Testing Criteria** — verification checklist
10. **Implementation Notes** — hardware and privacy constraints

## Usage

Give any single prompt file to a coding agent. Each prompt is self-contained with enough context to implement the tool from scratch within the OpenClaw framework.

```bash
# Example: hand a prompt to your coding agent
cat prompts/01-real-estate/property-gpt.md
```
