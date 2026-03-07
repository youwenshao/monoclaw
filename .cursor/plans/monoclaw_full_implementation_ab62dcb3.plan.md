---
name: MonoClaw Full Implementation
overview: "Full-stack implementation of MonoClaw: a Next.js client-facing website with i18n (EN/TC/SC), Stripe checkout, Supabase backend, internal admin dashboard, device provisioning CLI with comprehensive test suite and self-destruct, and coding agent prompts for industry-specific productivity software."
todos:
  - id: phase-1-foundation
    content: "Phase 1 -- Foundation: Initialize Next.js project with TypeScript, Tailwind, shadcn/ui. Set up next-intl with EN/TC/SC. Configure Supabase project (schema migrations for all tables, RLS policies, auth with Google provider). Set up Stripe products/prices. Create shared layout, navbar with locale switcher, footer."
    status: completed
  - id: phase-2-marketing
    content: "Phase 2 -- Marketing Site: Build landing page (hero, hardware showcase, industry carousel, CTA). Build pricing page with interactive configurator (hardware + addons + bundles). Build 12 industry/persona pages from spec content. Build about, FAQ, contact pages. All pages fully translated EN/TC/SC."
    status: completed
  - id: phase-3-checkout
    content: "Phase 3 -- Checkout Flow: Multi-step order form (hardware selection, addon picker, industry selection, review). Stripe Checkout Session creation via API route. Stripe webhook handler for payment confirmation. Order confirmation page with Apple Store redirect and shipping instructions. Order record creation in Supabase."
    status: completed
  - id: phase-4-dashboards
    content: "Phase 4 -- Dashboards: Client dashboard with order list, order detail with status timeline, device test report viewer (tabbed by category, pass/fail badges, expandable details, summary donut chart). Admin dashboard with KPI cards, order management table, device inventory, client list, manual status progression."
    status: completed
  - id: phase-5-device-cli
    content: "Phase 5 -- Device CLI: Python CLI tool with provision/test/status/finalize commands. Full test suite (~80-100 tests across 7 categories). Supabase reporter that uploads results in real-time. Self-destruct mechanism that removes all CLI traces, credentials, and itself after technician confirmation."
    status: completed
  - id: phase-6-agent-prompts
    content: "Phase 6 -- Agent Prompts: Write ~40 detailed coding agent prompts for all industry-specific productivity tools (PropertyGPT, ListingSync, VisaDoc OCR, TableMaster AI, InvoiceOCR Pro, LegalDoc Analyzer, ClinicScheduler, PermitTracker, TradeDoc AI, StudyBuddy, CodeQwen, BizOwner OS, etc.)."
    status: completed
isProject: false
---

# MonoClaw Service Implementation Plan

## Repository Structure

Single monorepo at `/Users/youwenshao/Projects/monoclaw`:

```
monoclaw/
├── web/                          # Next.js 14 App Router
│   ├── app/
│   │   ├── [locale]/             # i18n root (en, zh-hant, zh-hans)
│   │   │   ├── (marketing)/      # Public: landing, pricing, industries
│   │   │   ├── (client)/         # Auth-gated client dashboard
│   │   │   ├── (admin)/          # Role-gated internal dashboard
│   │   │   └── (checkout)/       # Order + Stripe checkout flow
│   │   └── api/                  # Route handlers (Stripe webhooks, etc.)
│   ├── components/               # shadcn/ui + custom components
│   ├── lib/                      # Supabase client, Stripe, i18n, utils
│   ├── messages/                 # i18n JSON files (en.json, zh-hant.json, zh-hans.json)
│   └── middleware.ts             # Locale detection + auth redirect
├── supabase/                     # Database layer
│   ├── migrations/               # SQL migrations
│   ├── seed.sql                  # Dev seed data
│   └── functions/                # Supabase Edge Functions (if needed)
├── device-cli/                   # Python CLI for device provisioning
│   ├── openclaw_setup/
│   │   ├── cli.py                # Main CLI entry point
│   │   ├── provision.py          # macOS setup (dirs, permissions, daemons)
│   │   ├── models.py             # LLM download + verification
│   │   ├── test_suite/           # Comprehensive test framework
│   │   │   ├── runner.py         # Test orchestrator
│   │   │   ├── hardware.py       # HW verification + stress tests
│   │   │   ├── software.py       # OpenClaw core + skill verification
│   │   │   ├── llm.py            # Model loading, inference, switching
│   │   │   ├── voice.py          # TTS/STT tests
│   │   │   ├── security.py       # Permission, integrity, sandbox tests
│   │   │   └── edge_cases.py     # Unicode, network loss, OOM, etc.
│   │   ├── reporter.py           # Uploads test results to Supabase
│   │   └── self_destruct.py      # Removes all CLI traces after confirmation
│   ├── pyproject.toml
│   └── README.md
└── prompts/                      # Coding agent prompts for productivity software
    ├── 01-property-gpt.md
    ├── 02-listing-sync.md
    ├── ...                       # One per industry software tool
    └── README.md
```

---

## 1. Supabase Database Schema

### Core Tables

- **profiles** -- extends `auth.users` with: `role` (client/admin/technician), `company_name`, `industry`, `contact_name`, `contact_phone`, `language_pref`, `created_at`
- **orders** -- `id`, `client_id` (FK profiles), `status` (enum: pending_payment, paid, hardware_pending, hardware_received, provisioning, testing, ready, shipped, delivered, completed), `hardware_type` (mac_mini_m4 / imac_m4), `hardware_config` (JSONB for SSD/color/ethernet choices), `software_package` (base), `total_price_hkd`, `stripe_payment_intent_id`, `apple_purchase_url`, `delivery_address`, `notes`, `created_at`, `updated_at`
- **order_addons** -- `id`, `order_id` (FK), `addon_type` (model / bundle), `addon_name`, `category` (fast/standard/think/coder/pro_bundle/max_bundle), `price_hkd`
- **order_status_history** -- `id`, `order_id` (FK), `from_status`, `to_status`, `notes`, `updated_by` (FK profiles), `created_at`
- **devices** -- `id`, `order_id` (FK), `serial_number`, `hardware_type`, `mac_address`, `setup_status` (enum: registered, provisioning, testing, passed, failed, shipped), `technician_id` (FK profiles), `setup_started_at`, `setup_completed_at`
- **device_test_results** -- `id`, `device_id` (FK), `category` (hardware/software/llm/voice/security/stress/edge_case), `test_name`, `status` (pass/fail/warning/skipped), `details` (JSONB -- stdout, metrics, errors), `duration_ms`, `executed_at`
- **device_test_summary** -- `id`, `device_id` (FK), `total_tests`, `passed`, `failed`, `warnings`, `skipped`, `overall_status` (pass/fail), `full_report_json` (JSONB), `created_at`

### Row-Level Security (RLS)

- Clients can only read their own orders, devices, and test results
- Admins/technicians can read/write all records
- The CLI authenticates via a Supabase service role key (stored securely, removed on self-destruct)

---

## 2. Client-Facing Website (Next.js on Vercel)

### Tech Stack

- Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- `next-intl` for i18n (EN / Traditional Chinese / Simplified Chinese)
- Supabase JS client for auth + data
- Stripe JS + `@stripe/stripe-js` for checkout
- Framer Motion for animations

### Key Pages

**Marketing (public)**

- `/` -- Hero with value prop, hardware showcase, industry carousel, CTA
- `/pricing` -- Interactive configurator: pick hardware -> pick add-ons -> see total price. Two-column layout showing Mac mini (from HK$5,000 + HK$39,999) vs iMac (from HK$10,000 + HK$39,999). Add-on cards for model categories and bundles with "Most Popular" / "Best Value" badges on Pro/Max bundles
- `/industries/[slug]` -- 8 industry pages + 4 persona pages (12 total), each with pain points, software stack, and value prop pulled from the spec
- `/about` -- Sentimento Technologies Limited, HK operating entity
- `/faq`, `/contact`

**Checkout flow**

- `/order` -- Step 1: Hardware selection (Mac mini M4 / iMac M4) with Apple config options (SSD, color, Ethernet) as informational-only fields (since they buy from Apple)
- `/order/addons` -- Step 2: Local LLM add-ons. A-la-carte model picker (4 categories) + bundle options (Pro HK$999 / Max HK$1,999). Visual comparison table
- `/order/industry` -- Step 3: Select industry vertical (determines pre-loaded software). Multi-select for personas
- `/order/review` -- Step 4: Order summary + Stripe payment (HK$39,999 + add-ons). Hardware is NOT charged here -- they buy from Apple separately
- `/order/confirmation/[id]` -- Post-payment: confirmation details, Apple Store redirect/iframe with instructions to ship to Sentimento's office address, order tracking link

**Client Dashboard (Supabase Auth -- Google login)**

- `/dashboard` -- Overview: active orders, device status
- `/dashboard/orders/[id]` -- Order detail with status timeline (pending -> paid -> hardware received -> provisioning -> testing -> shipped -> delivered). Each status change timestamped from `order_status_history`
- `/dashboard/orders/[id]/test-report` -- Full device test report. Categories in tabs/accordion: Hardware, Software, LLM, Voice, Security, Stress, Edge Cases. Each test shows pass/fail/warning badge, duration, and expandable details. Overall summary at top with pass rate donut chart
- `/dashboard/settings` -- Profile, language preference, company info

**Admin Dashboard (role-gated, same codebase)**

- `/admin` -- KPI cards (orders this month, revenue, devices in provisioning, avg test pass rate)
- `/admin/orders` -- Filterable/sortable table of all orders. Bulk status update. Export CSV
- `/admin/orders/[id]` -- Full order detail + manual status progression buttons + notes
- `/admin/devices` -- Device inventory. Filter by setup_status. Link device to order
- `/admin/devices/[id]` -- Device detail + full test report + technician assignment
- `/admin/clients` -- Client list with order count, total spend

### i18n Strategy

- `next-intl` with locale in URL path (`/en/pricing`, `/zh-hant/pricing`, `/zh-hans/pricing`)
- Three JSON message files in `web/messages/`. Marketing copy, UI labels, error messages
- `middleware.ts` detects `Accept-Language` header and redirects to appropriate locale
- Locale switcher component in navbar

---

## 3. Stripe Integration

- **Products** created in Stripe:
  - "OpenClaw Software Suite" -- HK$39,999 (one-time)
  - "Local LLM - Category 1 (Fast)" -- HK$99
  - "Local LLM - Category 2 (Standard)" -- HK$399
  - "Local LLM - Category 3 (Think)" -- HK$599
  - "Local LLM - Category 4 (Coder)" -- HK$399
  - "Pro Bundle" -- HK$999
  - "Max Bundle" -- HK$1,999
- **Checkout**: Stripe Checkout Session (server-side creation via `/api/checkout` route handler)
- **Webhook** at `/api/webhooks/stripe`: listens for `checkout.session.completed`, updates order status to `paid`, records `stripe_payment_intent_id`
- Currency: HKD throughout

---

## 4. Device Setup CLI (`device-cli/`)

Python CLI tool (packaged with `pyproject.toml`, installable via `pip install -e .`). Run by internal technician on each Mac.

**One-click pendrive flow**: Technicians can prepare a USB drive with a standard layout (device-cli copy, `.env.provision`, optional `job.txt`), then on each Mac double-click `Run OpenClaw Setup.command`. The script installs the CLI, runs provision and test (results upload to Supabase), and **auto-finalizes (self-destruct)** when all tests pass. See [device-cli/README.md](device-cli/README.md) for pendrive layout and steps.

### CLI Commands

```
openclaw-setup provision [--order-id <ORDER_ID>] [--serial <SERIAL>]
  -> Order/serial from args or OPENCLAW_ORDER_ID / OPENCLAW_SERIAL. Creates directory structure, sets permissions, installs dependencies,
     downloads purchased LLM models, installs industry skills,
     configures heartbeat daemon, writes core config files

openclaw-setup test --device-id <DEVICE_ID>
  -> Runs full test suite, streams results to terminal,
     uploads each result to Supabase `device_test_results`,
     generates summary in `device_test_summary`

openclaw-setup status
  -> Shows current provisioning/test status

openclaw-setup finalize --device-id <DEVICE_ID> [--yes]
  -> Technician confirms (or --yes for one-click script). Marks device as "passed" in Supabase.
     Triggers self-destruct: removes CLI tool, Supabase service key,
     all setup logs, pip package, and this script itself.
```

### Test Suite Categories (7 categories, ~80-100 individual tests)

**Hardware Verification** (~12 tests)

- CPU model matches expected (M4 chip)
- RAM amount = 16GB
- SSD health via `diskutil info` + write speed benchmark (sequential + random 4K)
- Network: ping test, DNS resolution, bandwidth estimate
- USB-C/Thunderbolt port detection
- Display output verification (iMac: built-in resolution; Mac mini: external display detected)
- Speaker output test (play test tone, check audio subsystem)
- Microphone input test (iMac: built-in; Mac mini: external)
- Bluetooth status
- Thermal sensor reading baseline

**macOS Environment** (~10 tests)

- macOS version >= 15.0 (Sequoia)
- SIP (System Integrity Protection) enabled
- FileVault encryption status
- Firewall enabled
- Gatekeeper enabled
- Xcode Command Line Tools installed
- Homebrew installed and functional
- Python 3.11+ available
- Node.js installed
- FFmpeg installed

**OpenClaw Core** (~15 tests)

- Directory structure exists (`/etc/openclaw/core/`, `/opt/openclaw/`, `~/.openclaw/user/`)
- Core file permissions are 444 (read-only)
- `chflags schg` immutable flag set on core files
- User directory permissions are 700
- SOUL.md, AGENTS.md, TOOLS.md present and match expected SHA-256
- Heartbeat daemon registered in launchd
- Heartbeat daemon actually running (check pid)
- Log directory exists with correct permissions
- Log rotation configured
- `config/llm-provider.json` valid JSON and schema-correct
- Guardian (integrity monitor) functional -- tamper a temp file, verify detection
- State files writable
- Workspace directory exists

**LLM Model Tests** (~15 tests, varies by purchased models)

- Each purchased model file exists at expected path
- Each model file SHA-256 matches manifest
- Each model loads successfully via MLX
- Inference test: simple prompt returns coherent response
- Tokens/second benchmark (per model)
- Memory usage during inference stays under 12GB
- Model hot-swap test: load model A, unload, load model B
- Context window test: send prompt near max context length
- Auto-routing test (if Max bundle): complexity classifier selects correct tier
- Concurrent request rejection (should queue, not crash)

**Voice System** (~8 tests)

- Whisper model file present
- Whisper loads and transcribes test audio (EN)
- Whisper transcribes Cantonese test audio
- Whisper transcribes Mandarin test audio
- TTS model loads
- TTS generates audio from English text
- TTS generates audio from Chinese text
- Language auto-detection works (Cantonese markers)

**Security** (~12 tests)

- Core files truly immutable (`chflags` verified)
- `run_shell` sandbox: attempt to access `/etc/passwd` -- should be blocked
- `run_shell` sandbox: attempt `rm -rf /` -- should be blocked with triple-confirm
- Memory cap: spawn process approaching 12GB -- verify OOM handling
- Network timeout: mock slow endpoint, verify 30s timeout
- File deletion requires `--confirm-delete` flag
- No SUID/SGID binaries in OpenClaw directories
- Supabase service key NOT present in any user-accessible file
- Shell audit log captures commands
- Permission escalation: attempt `sudo` from sandboxed shell -- blocked
- Data exfiltration: attempt to curl local files to external server -- blocked/warned
- Guardian detects modified core file and blocks startup

**Stress & Edge Cases** (~15 tests)

- 100 sequential inference calls without memory leak
- Rapid model switching (10 swaps in 60 seconds)
- Large file processing: 50MB PDF through OCR pipeline
- Unicode in file paths: create/read file with Chinese characters in path
- Network loss simulation: disconnect during API call, verify fallback to local
- Corrupt model file: rename model, attempt load, verify graceful error
- Disk space pressure: fill temp space to <1GB, verify warning
- Concurrent tool execution: run 3 tools simultaneously
- Recovery: kill heartbeat daemon, verify auto-restart via launchd
- Long-running task interruption: start inference, send SIGTERM, verify cleanup
- Empty input handling: send blank prompt to each model
- Max token output: request generation at max_tokens limit
- Malformed config: corrupt user config, verify core still loads
- Timezone handling: verify HKT (UTC+8) in all timestamps
- Bilingual output: request response in each supported language

### Reporter (`reporter.py`)

- Authenticates to Supabase using a service-role key (stored in `/opt/openclaw/.setup-credentials` with 600 permissions, deleted on self-destruct)
- Uploads each test result as it completes (real-time progress visible if client refreshes dashboard)
- After all tests, generates and uploads the summary record
- Updates `devices.setup_status` accordingly

### Self-Destruct (`self_destruct.py`)

Triggered by `openclaw-setup finalize`:

1. Verify all tests passed (refuse to finalize if failures exist)
2. Upload final status to Supabase
3. Delete: `/opt/openclaw/.setup-credentials` (service key)
4. Delete: the entire `openclaw-setup` pip package (`pip uninstall -y openclaw-setup`)
5. Delete: any setup logs in `/tmp/openclaw-setup/`
6. Delete: pip cache for this package
7. Delete: the CLI script itself
8. Final verification: confirm no traces remain
9. Print technician checklist (physical shipping prep)

---

## 5. Coding Agent Prompts for Productivity Software

One markdown file per tool in `prompts/`, containing a self-contained prompt that can be given to a coding agent to implement. Each prompt will include:

- **Context**: What MonoClaw is, the target user, the hardware constraints (M4, 16GB RAM)
- **Specification**: Exactly what the tool does, its inputs/outputs, integrations
- **Tech stack**: Python preferred (for MLX compatibility), with specific libraries
- **File structure**: Where the tool lives in the OpenClaw directory hierarchy
- **API contracts**: How it interfaces with the LLM provider abstraction layer
- **HK-specific requirements**: Regulatory, language, data format specifics
- **Testing criteria**: How to verify the tool works

Total: ~40 prompt files covering all tools across 8 industries + 4 personas. Grouped by industry.

---

## 6. Implementation Order

The work is organized into 6 phases, each buildable sequentially:

**Phase 1: Foundation** -- Supabase schema, Next.js project scaffold, auth, i18n skeleton
**Phase 2: Marketing Site** -- Landing page, pricing configurator, industry pages
**Phase 3: Checkout Flow** -- Order flow, Stripe integration, confirmation page with Apple redirect
**Phase 4: Dashboards** -- Client order status + test report viewer, admin order/device management
**Phase 5: Device CLI** -- Provisioning tool, full test suite, Supabase reporter, self-destruct
**Phase 6: Agent Prompts** -- All ~40 productivity software prompts for coding agents