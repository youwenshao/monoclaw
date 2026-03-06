---
name: Tools README Documentation
overview: Create README.md files for tools 03-fnb-hospitality through 12-student and for the shared library, following the structure established by 01-real-estate and 02-immigration.
todos: []
isProject: false
---

# Tools README Documentation Plan

## Scope

Create README documentation for **10 tool packages** (03 through 12) and **1 shared library** that currently lack documentation. Tools 01-real-estate and 02-immigration already have READMEs and serve as reference templates.

## Documentation Structure (per tool)

Each README will follow a consistent structure based on [tools/01-real-estate/README.md](tools/01-real-estate/README.md) and [tools/02-immigration/README.md](tools/02-immigration/README.md):

1. **Title and one-line description**
2. **Tools table** — Sub-tools with purpose
3. **Quick Start** — Prerequisites, installation, run command, first-run setup
4. **User Guide** — Brief feature overview per sub-tool
5. **Configuration** — Key `config.yaml` sections
6. **Architecture** — Directory structure and databases
7. **Running Tests** — `pytest` command
8. **Related** — Links to prompts and implementation plans

## Tools to Document


| Tool                   | Port | Sub-tools                                                             |
| ---------------------- | ---- | --------------------------------------------------------------------- |
| **03-fnb-hospitality** | 8003 | TableMaster AI, QueueBot, NoShowShield, SommelierMemory               |
| **04-accounting**      | 8004 | InvoiceOCR Pro, ReconcileAgent, FXTracker, TaxCalendar Bot            |
| **05-legal**           | 8005 | LegalDoc Analyzer, DeadlineGuardian, DiscoveryAssistant, IntakeBot    |
| **06-medical-dental**  | 8006 | InsuranceAgent, ScribeAI, ClinicScheduler, MedReminderBot             |
| **07-construction**    | 8503 | PermitTracker, SafetyForm Bot, DefectsManager, SiteCoordinator        |
| **08-import-export**   | 8008 | TradeDoc AI, SupplierBot, FXInvoice, StockReconcile                   |
| **09-academic**        | 8509 | PaperSieve, CiteBot, TranslateAssist, GrantTracker                    |
| **10-vibe-coder**      | 8010 | CodeQwen, DocuWriter, GitAssistant, HKDevKit                          |
| **11-solopreneur**     | 8506 | BizOwner OS, MPFCalc, SupplierLedger, SocialSync                      |
| **12-student**         | 8507 | StudyBuddy, ExamGenerator, ThesisFormatter, InterviewPrep, JobTracker |


## Shared Library README

[tools/shared/](tools/shared/) — Document `openclaw_shared`:

- **Purpose** — Shared utilities for all OpenClaw industry tools
- **Modules** — auth, config, database, export, health, llm, logging, messaging, mona_events
- **Installation** — `pip install -e ../shared` (from a tool dir)
- **Optional extras** — `[mlx]`, `[messaging]`, `[all]`
- **Usage** — How tools depend on it (import patterns)

## Key Files Reference

- **Config source**: Each tool's [config.yaml](tools/03-fnb-hospitality/config.yaml) for `extra` keys
- **App structure**: [fnb_hospitality/app.py](tools/03-fnb-hospitality/fnb_hospitality/app.py) for router includes
- **Implementation plans**: `.cursor/plans/*.plan.md` for detailed feature descriptions

## Implementation Approach

1. Create each README in a single pass, reusing the established structure
2. Keep content proportional: 2–4 sentences per sub-tool in the User Guide
3. Use consistent formatting (tables, code blocks, section headers)
4. Ensure run commands use the correct entry point (e.g. `python -m fnb_hospitality.app` or `uvicorn fnb_hospitality.app:app`)

