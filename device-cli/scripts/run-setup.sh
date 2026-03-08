#!/usr/bin/env bash
# MonoClaw one-click device setup: provision, test, auto-finalize on success.
# Run from pendrive: double-click "Run OpenClaw Setup.command" or run this script.
# Layout: ROOT = volume root (e.g. /Volumes/MONOCLAW_SETUP); contains device-cli/, .env.provision, optional job.txt.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "MonoClaw one-click setup"
echo "Root: $ROOT"
echo ""

if [[ ! -d "$ROOT/device-cli" ]] || [[ ! -f "$ROOT/.openclaw-setup" ]]; then
  echo "Error: Expected pendrive layout with device-cli/ and .openclaw-setup at: $ROOT"
  echo "Rename the USB volume to MONOCLAW_SETUP and copy device-cli there, or run from the correct path."
  exit 1
fi

# Python selection: bundled on pendrive (primary) or system 3.11+ (contingency)
PYTHON=""
PIP=""
if [[ -x "$ROOT/python/bin/python3" ]] && "$ROOT/python/bin/python3" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
  BUNDLED_PYTHON="$ROOT/python/bin/python3"
  echo "Using bundled Python: $BUNDLED_PYTHON"
  # Use a fresh venv on the Mac so we never touch the pendrive's broken site-packages.
  # Suppress stderr during venv creation: pendrive Python often has ._* (AppleDouble) files
  # in its venv template that fail to copy as UTF-8; the venv still works.
  VENV_DIR="${TMPDIR:-/tmp}/openclaw-setup-venv.$$"
  echo "Creating temporary environment at $VENV_DIR ..."
  "$BUNDLED_PYTHON" -m venv "$VENV_DIR" 2>/dev/null || true
  if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
    echo "Error: Temporary environment was not created. Re-run to see details."
    "$BUNDLED_PYTHON" -m venv "$VENV_DIR" || exit 1
  fi
  PYTHON="$VENV_DIR/bin/python3"
  PIP="$PYTHON -m pip"
  export PATH="$VENV_DIR/bin:$PATH"
elif command -v python3 &>/dev/null && python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
  PYTHON="python3"
  PIP="$PYTHON -m pip"
  echo "Using system Python: $PYTHON"
fi
if [[ -z "$PYTHON" ]]; then
  echo "Error: Python 3.11+ not found."
  echo "  - Add a relocatable Python to the pendrive at $ROOT/python/ (see README), or"
  echo "  - Run: xcode-select --install"
  echo "    Wait for the install to finish, then double-click Run OpenClaw Setup.command again."
  exit 1
fi

# Ensure pip/setuptools are up to date
echo "Ensuring pip and setuptools are up to date..."
$PIP install --upgrade pip setuptools wheel -q

# Install CLI: copy device-cli to a temp dir on the Mac so the build runs from local disk
# (avoids pendrive filesystem issues). Use non-editable install to avoid setuptools editable backend.
DEVICE_CLI_SRC="$ROOT/device-cli"
if [[ -n "${VENV_DIR:-}" ]]; then
  COPY_DIR="${TMPDIR:-/tmp}/openclaw-device-cli.$$"
  echo "Copying device-cli to $COPY_DIR for install..."
  cp -R "$ROOT/device-cli" "$COPY_DIR"
  DEVICE_CLI_SRC="$COPY_DIR"
fi
echo "Installing openclaw-setup from $DEVICE_CLI_SRC ..."
$PIP install "$DEVICE_CLI_SRC" -q

# Load env
if [[ ! -f "$ROOT/.env.provision" ]]; then
  echo "Error: $ROOT/.env.provision not found. Create it with SUPABASE_URL and SUPABASE_SERVICE_KEY."
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "$ROOT/.env.provision"
set +a
if [[ -z "${SUPABASE_URL:-}" ]] || [[ -z "${SUPABASE_SERVICE_KEY:-}" ]]; then
  echo "Error: .env.provision must set SUPABASE_URL and SUPABASE_SERVICE_KEY."
  exit 1
fi

# Order ID, email, and serial: job.txt or env or prompt
# job.txt: Line 1 = Order UUID or EMAIL:client@example.com, Line 2 = serial
ORDER_ID=""
EMAIL=""
SERIAL=""
if [[ -f "$ROOT/job.txt" ]]; then
  LINE1=$(sed -n '1p' "$ROOT/job.txt" | tr -d '\r')
  SERIAL=$(sed -n '2p' "$ROOT/job.txt" | tr -d '\r')
  if [[ "$LINE1" == EMAIL:* ]]; then
    EMAIL="${LINE1#EMAIL:}"
  else
    ORDER_ID="$LINE1"
  fi
fi
if [[ -z "$ORDER_ID" ]]; then ORDER_ID="${OPENCLAW_ORDER_ID:-}"; fi
if [[ -z "$EMAIL" ]]; then EMAIL="${OPENCLAW_EMAIL:-}"; fi
if [[ -z "$SERIAL" ]]; then SERIAL="${OPENCLAW_SERIAL:-}"; fi
if [[ -z "$ORDER_ID" ]] && [[ -z "$EMAIL" ]] || [[ -z "$SERIAL" ]]; then
  echo "Enter Order ID (Supabase UUID) or Client email (to look up order):"
  read -r INPUT
  if [[ "$INPUT" == *@* ]]; then
    EMAIL="$INPUT"
  else
    ORDER_ID="$INPUT"
  fi
  echo "Enter Mac serial number:"
  read -r SERIAL
fi
if [[ -z "$ORDER_ID" ]] && [[ -z "$EMAIL" ]]; then
  echo "Error: Order ID or client email is required."
  exit 1
fi
if [[ -z "$SERIAL" ]]; then
  echo "Error: Mac serial number is required."
  exit 1
fi

# Provision (requires sudo to create /etc/openclaw, /opt/openclaw, and write configs)
echo ""
echo "Running provision (you may be prompted for your password)..."
if [[ -n "$ORDER_ID" ]]; then
  PROV_CMD="openclaw-setup provision --order-id $ORDER_ID --serial $SERIAL"
else
  PROV_CMD="openclaw-setup provision --email $EMAIL --serial $SERIAL"
fi
if ! sudo env PATH="$PATH" SUPABASE_URL="$SUPABASE_URL" SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" HF_TOKEN="${HF_TOKEN:-}" CLAWHUB_TOKEN="${CLAWHUB_TOKEN:-}" OPENCLAW_ORDER_ID="${ORDER_ID:-}" OPENCLAW_EMAIL="${EMAIL:-}" OPENCLAW_SERIAL="$SERIAL" $PROV_CMD; then
  echo "Provision failed. Exiting."
  exit 1
fi

# Deploy Mona Hub to /opt/openclaw/mona_hub from the setup source
echo ""
echo "Deploying Mona Hub..."
REAL_USER="${SUDO_USER:-$(whoami)}"
sudo mkdir -p /opt/openclaw/mona_hub
sudo cp -R "$DEVICE_CLI_SRC/mona_hub/"* /opt/openclaw/mona_hub/
sudo chown -R "$REAL_USER:" /opt/openclaw/mona_hub
echo "Mona Hub deployed to /opt/openclaw/mona_hub"

# Ensure Homebrew bin is in PATH (Node.js/npm were installed via brew in provision step)
if [[ -d "/opt/homebrew/bin" ]]; then
  export PATH="/opt/homebrew/bin:$PATH"
elif [[ -d "/usr/local/bin" ]]; then
  # Homebrew on Intel often links to /usr/local/bin
  export PATH="/usr/local/bin:$PATH"
fi

# Build the frontend so the server can serve the production SPA
echo ""
echo "Building Mona Hub frontend..."
sudo -u "$REAL_USER" env PATH="$PATH" bash -c "cd /opt/openclaw/mona_hub/frontend && npm install --production=false 2>&1 && npm run build 2>&1"
if [[ ! -d /opt/openclaw/mona_hub/frontend/dist ]]; then
  echo "Error: Frontend build failed — /opt/openclaw/mona_hub/frontend/dist not found."
  exit 1
fi
echo "Frontend built successfully"

# Install openclaw-setup into the permanent venv so we can run tests from it
echo "Installing setup CLI into permanent environment..."
sudo -u "$REAL_USER" /opt/openclaw/venv/bin/pip install "$DEVICE_CLI_SRC" -q

# Device ID from credentials (file is root-owned after provision)
CRED_PATH="/opt/openclaw/.setup-credentials"
if [[ ! -f "$CRED_PATH" ]]; then
  echo "Error: $CRED_PATH not found after provision."
  exit 1
fi
DEVICE_ID=$(sudo /opt/openclaw/venv/bin/python3 -c "import json; print(json.load(open('/opt/openclaw/.setup-credentials'))['device_id'])")
if [[ -z "$DEVICE_ID" ]]; then
  echo "Error: Could not read device_id from $CRED_PATH."
  exit 1
fi

# Test (reporter uploads results to Supabase)
echo ""
echo "Running test suite (results upload to Supabase)..."
TEST_EXIT=0
/opt/openclaw/venv/bin/openclaw-setup test --device-id "$DEVICE_ID" || TEST_EXIT=$?

# Auto-finalize only if all tests passed
if [[ $TEST_EXIT -eq 0 ]]; then
  echo ""
  echo "All tests passed. Finalizing — building Mona.app and launching Hub..."
  sudo env PATH="$PATH" SUPABASE_URL="$SUPABASE_URL" SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" /opt/openclaw/venv/bin/openclaw-setup finalize --device-id "$DEVICE_ID" --yes
  echo ""
  echo "Setup complete. Mona Hub is running and the onboarding page should be open."
  echo "You may now eject the setup drive and close this terminal."
else
  echo ""
  echo "Some tests failed. Fix issues and run finalize manually when ready, or re-run this script."
  exit $TEST_EXIT
fi
