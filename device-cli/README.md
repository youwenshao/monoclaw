# OpenClaw Device Setup CLI

Python CLI for provisioning, testing, and finalizing Mac devices (Mac mini M4 / iMac M4) for MonoClaw. The setup flow is **order-aware**: it fetches the client's order from Supabase and automatically installs the correct LLM models, industry skills, and configuration for that order—no manual configuration needed.

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `openclaw-setup provision --order-id <UUID> --serial <SERIAL>` | Provision a new device (order ID + serial) |
| `openclaw-setup provision --email <CLIENT_EMAIL> --serial <SERIAL>` | Provision using client email (looks up most recent order) |
| `openclaw-setup test --device-id <UUID>` | Run full test suite, upload results to Supabase |
| `openclaw-setup finalize --device-id <UUID> [--yes]` | Mark device ready and remove CLI |
| `openclaw-setup device-id` | Print device_id from credentials |
| `openclaw-setup status` | Show current provisioning state |

---

## Prerequisites (Before You Start)

1. **Mac to be provisioned** — Mac mini M4 or iMac M4, 16GB RAM minimum, macOS 15+ (Sequoia).
2. **Supabase credentials** — `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (service role key). Get these from the MonoClaw admin or project settings.
3. **Order identification** — You need **one** of:
   - **Order UUID** — From the MonoClaw admin dashboard (order detail page) or from the client's order confirmation email.
   - **Client email** — The email the client used to sign up. The CLI will look up their most recent paid order.
4. **Mac serial number** — Find it: Apple menu → About This Mac → Serial Number. Or run: `system_profiler SPHardwareDataType | grep "Serial Number"`.

---

## One-Click Pendrive Setup (Recommended)

The fastest way to set up a new device: prepare a USB drive once, then on each Mac plug it in and double-click one file. The script runs **provision → test → auto-finalize** when all tests pass. Test results are uploaded to Supabase automatically.

### Step 1: Prepare the USB Drive

1. **Format the USB drive** (optional but recommended): Disk Utility → Erase → Format: APFS or Mac OS Extended (Journaled). Name the volume something like `MONOCLAW_SETUP`.

2. **Create the marker file** at the volume root:
   - Create an empty file named `.openclaw-setup` (the leading dot matters).
   - This tells the script that this is a MonoClaw setup drive.

3. **Copy the `device-cli` folder** from this repo onto the volume:
   - You should have: `MONOCLAW_SETUP/device-cli/` containing `openclaw_setup/`, `scripts/`, `pyproject.toml`, etc.

4. **Copy the launcher** to the volume root:
   - From: `device-cli/scripts/Run OpenClaw Setup.command`
   - To: `MONOCLAW_SETUP/Run OpenClaw Setup.command`
   - Make sure it is executable (it usually is by default).

5. **Create `.env.provision`** at the volume root with:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your-service-role-key
   HF_TOKEN=hf_YourHuggingFaceAccessToken
   CLAWHUB_TOKEN=clh_YourClawHubToken
   ```
   Replace with your actual Supabase project URL, service role key, HuggingFace access token, and ClawHub API token.
   `HF_TOKEN` enables authenticated model downloads with higher rate limits and faster speeds.
   `CLAWHUB_TOKEN` avoids rate limiting when installing community skills.
   The tokens are also persisted on the device so Mona can download additional models and skills in the future.

6. **(Optional) Bundled Python** — If the Mac may not have Python or Xcode Command Line Tools:
   - Download a relocatable Python 3.11+ for arm64 macOS (e.g. [python-build-standalone](https://github.com/indygreg/python-build-standalone/releases) — pick **macos-aarch64**).
   - Extract so you have: `MONOCLAW_SETUP/python/bin/python3`
   - If present, the script uses it and no system Python is required.

7. **(Optional) Non-interactive: job file** — For one pendrive per order, create `job.txt` at the volume root:
   - Line 1: Order UUID **or** `EMAIL:client@example.com` (to look up the client's most recent order)
   - Line 2: Mac serial number
   - If present, the script will not prompt for these.

   Or set in `.env.provision`:
   ```
   OPENCLAW_ORDER_ID=order-uuid-here
   OPENCLAW_SERIAL=Mac-serial-here
   ```
   Or use client email instead of order ID:
   ```
   OPENCLAW_EMAIL=client@example.com
   OPENCLAW_SERIAL=Mac-serial-here
   ```

### Step 2: On the Mac to Be Provisioned

1. **Plug in the USB drive.**

2. **If you did NOT include bundled Python** on the pendrive:
   - Run `xcode-select --install` if prompted or if Python is missing.
   - Wait for the install to finish before continuing.

3. **Double-click `Run OpenClaw Setup.command`** (from the USB drive).

4. **If you didn't use `job.txt` or env vars**, you will be prompted:
   - **Order ID or Client email** — Enter the Supabase order UUID, or the client's email address (the script will look up their most recent order).
   - **Mac serial number** (from About This Mac).

5. **Enter your Mac password** when prompted (needed for creating `/etc/openclaw`, `/opt/openclaw`, etc.).

6. **Wait for the process to complete.** The script will:
   - Install the CLI
   - Fetch the order from Supabase (client, LLM plan, industry, personas)
   - Register the device
   - Create directories and install dependencies
   - Download the LLM models specified in the order (this can take 10–30+ minutes depending on plan)
   - Install industry skills (software stack for the client's industry and persona add-ons)
   - Write configuration and routing
   - Run the full test suite (results upload to Supabase)
   - If all tests pass: **auto-finalize** (remove CLI, mark device ready)
   - If any test fails: stop and report. Fix issues, then re-run or finalize manually.

7. **Press Enter** when prompted to close the terminal window.

---

## What Happens During Provisioning (Detail)

Understanding the flow helps when troubleshooting. The provisioner does the following in order:

### 1. Order Lookup

- Fetches the full order from Supabase: client, hardware type, LLM plan (bundle or à la carte models), industry, and persona add-ons.
- **LLM plan types:**
  - **Pro Bundle** — 1 Fast + 1 Think + 1 Coder model (client chose which)
  - **Max Bundle** — All 16 models + auto-routing
  - **À la carte** — Specific models the client selected
  - **API only** — No local models (skips model download)

### 2. Device Registration

- Inserts a row into the `devices` table with order ID, serial number, hardware type (detected), and MAC address.
- This links the physical Mac to the order in Supabase.

### 3. Directory Structure

- Creates `/etc/openclaw/core`, `/opt/openclaw/models`, `/opt/openclaw/skills/local`, `/opt/openclaw/state`, `/var/log/openclaw`, `~/.openclaw/user`, `~/OpenClawWorkspace`.

### 4. Dependencies

- Installs Python packages: `mlx-lm`, `mlx-whisper`, `mlx-audio`, `qwen-agent`, `psutil`, `schedule`, `huggingface-hub`, `sentence-transformers` (for tool auto-routing). The embedding model (`paraphrase-multilingual-MiniLM-L12-v2`) is pre-downloaded during setup to avoid first-request latency.

### 5. Core Configs

- Writes `SOUL.md`, `AGENTS.md`, `TOOLS.md` in `/etc/openclaw/core` with industry context and available tools.
- Communication tools now include native support for **Telegram** and **Discord** alongside WhatsApp.

### 6. Model Download

- For each model in the order's LLM plan, downloads from Hugging Face Hub to `/opt/openclaw/models/{model-id}/`.
- **Voice Models**: Automatically downloads `whisper-large-v3-turbo` (STT) and `Qwen3-TTS-12Hz-1.7B` (TTS) for fully offline voice interaction.
- Uses 4-bit quantized MLX-compatible models. Progress is shown per model.

### 7. Industry & Community Skills

- Creates skill directories under `/opt/openclaw/skills/local/{slug}/` for industry and persona stacks.
- **ClawHub Integration**: Automatically installs 16 vetted, high-trust community skills from `clawhub.ai` (e.g., `self-improving-agent`, `agent-browser`, `find-skills`) via the ClawHub CLI.

### 8. Configuration & Routing

- **Auto-Routing (Max Bundle Only)**: Writes `/opt/openclaw/state/routing-config.json` for task-based model selection.
- **LLM Provider Config**: Writes `/opt/openclaw/state/llm-provider.json` defining the offline/hybrid mode.
- **Global Config**: Writes `~/.openclaw/config.json` to point the OpenClaw engine to local system paths.
- **Messaging Stubs**: Creates credential stubs for WhatsApp, Telegram, and Discord in `/opt/openclaw/config/messaging/`.

### 9. Active Work State

- Writes `/opt/openclaw/state/active-work.json` with order ID, industry, personas, model list. Used by the test suite and runtime.

### 10. Credentials

- Stores `/opt/openclaw/.setup-credentials` with `device_id`, `order_id`, and Supabase URL (for the test reporter and finalize step).

---

## Test Suite

The test suite validates:

- **Hardware** — CPU (M4), RAM ≥16GB, SSD health, network, display, audio, etc.
- **macOS environment** — macOS version, SIP, FileVault, Xcode CLI, Homebrew, Python, Node, FFmpeg.
- **OpenClaw core** — Directories, config files, permissions, manifest integrity, industry skills.
- **LLM models** — Expected models present, config integrity, load and inference per model.
- **Voice** — Whisper Large V3 Turbo (STT) and Qwen3-TTS (TTS) model presence, inference verification, and language detection (English, Cantonese, Mandarin).
- **Security** — Core immutability, sandbox, credentials permissions.
- **Stress/edge cases** — Inference, model switching, Unicode, network fallback, etc.

Results are uploaded to Supabase (`device_test_results`, `device_test_summaries`). The client can view the test report in their dashboard.

---

## Post-Provisioning: User Onboarding

Once finalized, the device is ready for the client. The onboarding flow is fully local and designed to introduce Mona as a warm, capable colleague.

### 1. Preparing the Device for the Client
Before closing the device and shipping it, the technician must ensure the **Mona Hub** application is configured to launch automatically upon the client's first login.

**Technician Action (Final Step):**
Run the following command to register the Mona Hub as a login item for the user:
```bash
# Run this as the technician, it will target the real user's login items
openclaw-setup setup-onboarding-launch
```
This command creates a macOS LaunchAgent in `~/Library/LaunchAgents/com.monoclaw.monahub.plist` that starts the Mona Hub server and opens the onboarding interface in the default browser as soon as the client logs in.

### 2. Initial Login
- **Credentials**: Clients log into the Mac using the default password: `1234`.
- **Dashboard**: This password is shown on their MonoClaw web dashboard once the order is shipped.
- **Security**: Clients are instructed to change this password immediately after their first login.

### 3. Mona Hub Onboarding (12 Phases)
As soon as the client logs in, their default browser will open to `http://localhost:8000`, presenting the Mona Hub onboarding app. It guides the user through a carefully paced introduction.

| Phase | Screen | Emotional Beat | Purpose |
|-------|--------|----------------|---------|
| 0 | **Welcome** | Anticipation | Mona introduces herself as a new colleague. |
| 1 | **Independence** | Empowerment | Celebrating 100% local, private ownership of the agent. |
| 2 | **Introduction** | Warmth | Setting the tone for a human-like relationship. |
| 3 | **Voice Interaction** | Delight | Testing real-time, offline STT/TTS (Whisper + Qwen3-TTS). |
| 4 | **Chat Experience** | Connection | Demonstrating streaming responses and model selection. |
| 5 | **Profile** | Personalization | Defining Mona's name, tone, and personality. |
| 6 | **Mac Setup** | Ownership | Customizing the Mac's account name and appearance. |
| 7 | **API Keys** | Configuration | Guided wizards for optional cloud LLMs and messaging. |
| 8 | **Tools & Skills** | Confidence | Reviewing industry tools and ClawHub community skills. |
| 9 | **First Task** | Competence | Performing a guided industry-specific task with Mona. |
| 10 | **Summary** | Reassurance | Reviewing the configuration and readiness state. |
| 11 | **Launch** | Celebration | Final handover of the device to the client. |

### 4. Guided Configuration Wizards
For services requiring external setup, Mona provides step-by-step hand-holding:

- **Cloud LLMs**: Detailed instructions for **DeepSeek**, **Kimi K2.5**, and **GLM-5**, including account creation and credit top-up links.
- **Messaging**: Native integration for **WhatsApp (Twilio)**, **Telegram (BotFather)**, and **Discord (Developer Portal)**.
- **Validation**: Every key entered is automatically validated against the provider's API with informative error messages for incorrect keys or missing credits.

### 5. Interaction Management
Mona is designed to handle complex interactions without technical friction:
- **Interaction Manager**: A backend service ensures voice and text modes never conflict (e.g., Mona won't start speaking while you are still typing).
- **Model Routing**: For Max Bundle users, Mona automatically routes tasks to the best local model (Fast, Think, Coder, or Complex).
- **Privacy First**: All core interactions (Voice, Chat, Local Skills) happen entirely on-device with zero external data transmission.

---

## Manual CLI Usage

If you prefer not to use the one-click pendrive flow, you can run the CLI manually.

### Install

```bash
cd device-cli
pip install -e .
```

### Provision

You need **either** `--order-id` **or** `--email`, plus `--serial`. Supabase credentials must be in the environment or `.env.provision`.

**By order ID:**
```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_KEY=your-service-role-key

openclaw-setup provision --order-id a1b2c3d4-e5f6-4789-a012-3456789abcde --serial H0N9QH6W4K
```

**By client email:**
```bash
openclaw-setup provision --email client@example.com --serial H0N9QH6W4K
```

The email lookup finds the client's most recent paid order. Use this when you have the client's email but not the order UUID.

**With sudo** (required for creating system directories):
```bash
sudo env PATH="$PATH" SUPABASE_URL="$SUPABASE_URL" SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" \
  openclaw-setup provision --order-id <ORDER_ID> --serial <SERIAL>
```

### Test

After provision, get the device ID from credentials, then run the test suite:

```bash
DEVICE_ID=$(openclaw-setup device-id)
openclaw-setup test --device-id "$DEVICE_ID"
```

Or if credentials are root-owned:
```bash
DEVICE_ID=$(sudo python3 -c "import json; print(json.load(open('/opt/openclaw/.setup-credentials'))['device_id'])")
openclaw-setup test --device-id "$DEVICE_ID"
```

### Finalize

When all tests pass, finalize marks the device ready and removes the CLI:

```bash
openclaw-setup finalize --device-id "$DEVICE_ID"
```

Use `--yes` or `-y` to skip the confirmation prompt (e.g. in automated scripts).

### Status

View the current provisioning state (from `active-work.json`):

```bash
openclaw-setup status
```

---

## Pendrive Script: Order ID vs Email

The `run-setup.sh` script supports both order ID and client email:

- **job.txt** — Line 1: Order UUID **or** `EMAIL:client@example.com` (to look up order by email). Line 2: Mac serial number.
- **Environment** — Set `OPENCLAW_ORDER_ID` or `OPENCLAW_EMAIL` in `.env.provision`, plus `OPENCLAW_SERIAL`.
- **Interactive prompt** — When neither is pre-set, you can enter either an order UUID or a client email. The script detects email by the `@` character.

---

## Troubleshooting

### "No order found" or "Order not found"

- Verify the order exists in Supabase and has status `paid` or later.
- If using email: ensure the client has a profile (signed up) and at least one order. The lookup uses the most recent order.
- Check that `client_id` on the order matches a valid profile (not the zero UUID).

### "Provide --order-id or --email"

- You must supply one of these. Use order UUID from the admin dashboard, or the client's sign-up email.

### Provision fails with permission errors

- The provision step needs `sudo` to create `/etc/openclaw` and `/opt/openclaw`. Run with `sudo env ...` as shown above, or use the pendrive script which prompts for your password.

### Model download is very slow

- Model downloads can be several GB. Ensure a stable network connection.
- First-time download per model is cached in `~/.cache/huggingface/`. Subsequent provisions of the same model are faster.

### Tests fail: "Expected model X not found"

- The order's LLM plan specifies which models to install. If a model failed to download, check the provision logs.
- For API-only orders, no models are installed; some LLM tests will be skipped.

### Tests fail: "Industry skill directory missing"

- The provisioner creates skill dirs from the order's `industry` and `personas` columns. If the order has no industry set, industry skills may be minimal. Re-provision after ensuring the order has industry/personas in the admin dashboard.

### Finalize says "Tests did not pass"

- Run `openclaw-setup test --device-id <ID>` again and fix any failures before finalizing.
- Check the test report in the client dashboard or Supabase for details.

---

## Requirements

- **macOS 15+** (Sequoia)
- **Python 3.11+** — from bundled pendrive Python, or from Xcode Command Line Tools (`xcode-select --install`)
- **Network access** — Supabase, Hugging Face Hub (model downloads)
- **~20–50 GB free disk** — for models (depends on LLM plan)
