---
name: Install OpenClaw in Setup
overview: Modify the device-cli setup flow to install OpenClaw from a pre-built bundle on the pendrive, configure it as the core agent runtime, install its gateway as a LaunchAgent daemon, and rewire Mona Hub's backend to proxy all AI/chat requests through OpenClaw's gateway API instead of doing direct LLM calls.
todos:
  - id: pendrive-layout
    content: Update run-setup.sh to validate and copy openclaw-bundle/ from pendrive to /opt/openclaw/openclaw/
    status: completed
  - id: node22-check
    content: Add Node 22+ version check in _install_dependencies(); install node@22 via Homebrew if needed
    status: completed
  - id: install-openclaw
    content: "Add _install_openclaw() method to provisioner.py: copy bundle, create /usr/local/bin/openclaw wrapper, set ownership"
    status: completed
  - id: openclaw-config
    content: Rewrite _write_openclaw_config() to generate ~/.openclaw/openclaw.json (gateway config, skills dirs, auth token) and ~/.openclaw/.env
    status: completed
  - id: gateway-daemon
    content: Add _install_openclaw_gateway() to write LaunchAgent plist for ai.openclaw.gateway and start it
    status: completed
  - id: skill-md
    content: Modify _install_all_tool_suites() to write SKILL.md alongside manifest.json for OpenClaw skill discovery
    status: completed
  - id: llm-service-rewrite
    content: Rewrite services/llm.py as an OpenClaw gateway HTTP client (proxy /v1/chat/completions)
    status: completed
  - id: chat-router-update
    content: Simplify routers/chat.py to work with the new gateway-backed LLM service
    status: completed
  - id: test-suite
    content: Add OpenClaw installation and gateway health tests to test_suite/openclaw_core.py
    status: completed
  - id: setup-script-gateway
    content: Update run-setup.sh to bootstrap the gateway LaunchAgent and verify health after provision
    status: completed
isProject: false
---

# Install OpenClaw in Device Setup and Rewire Mona Hub

## Architecture Overview

```mermaid
flowchart TB
    subgraph pendrive [USB Pendrive Layout]
        deviceCli[device-cli/]
        openclawBundle[openclaw-bundle/]
        envFile[.env.provision]
    end

    subgraph device [Target Mac Device]
        subgraph optOpenclaw [/opt/openclaw/]
            openclawCore[openclaw/ - Node.js app]
            models[models/]
            skills[skills/local/ + skills/clawhub/]
            state[state/]
            monaHub[mona_hub/]
            venv[venv/]
        end

        subgraph userHome [~/.openclaw/]
            openclawJson[openclaw.json]
            dotEnv[.env]
            sessions[sessions/]
        end

        subgraph daemons [LaunchAgents]
            gatewayDaemon["ai.openclaw.gateway (port 18789)"]
            monaHubDaemon["com.monoclaw.monahub (port 8000)"]
        end
    end

    openclawBundle -->|copy| openclawCore
    monaHub -->|"HTTP proxy /v1/chat/completions"| gatewayDaemon
    gatewayDaemon -->|loads| skills
    gatewayDaemon -->|uses| models
    gatewayDaemon -->|reads| openclawJson
```



## Key Files to Modify

- [device-cli/scripts/run-setup.sh](device-cli/scripts/run-setup.sh) -- add openclaw-bundle copy and gateway start
- [device-cli/openclaw_setup/provisioner.py](device-cli/openclaw_setup/provisioner.py) -- add `_install_openclaw()` and `_write_openclaw_config()` rewrite
- [device-cli/openclaw_setup/app_builder.py](device-cli/openclaw_setup/app_builder.py) -- gateway env vars in Mona Hub LaunchAgent
- [device-cli/mona_hub/backend/routers/chat.py](device-cli/mona_hub/backend/routers/chat.py) -- rewrite to proxy through OpenClaw gateway
- [device-cli/mona_hub/backend/services/llm.py](device-cli/mona_hub/backend/services/llm.py) -- replace with OpenClaw gateway client

## 1. Pendrive Layout Change

Add a pre-built OpenClaw bundle alongside `device-cli/`. The bundle contains the full OpenClaw repo with `dist/` and `node_modules/` pre-built. Expected layout:

```
MONOCLAW_SETUP/
  .openclaw-setup
  .env.provision
  device-cli/
  openclaw-bundle/       <-- NEW: pre-built OpenClaw
    openclaw.mjs
    dist/
    node_modules/
    skills/
    package.json
    ...
```

`run-setup.sh` will validate `openclaw-bundle/` exists and has `dist/entry.js`.

## 2. Provisioner: Install OpenClaw (`_install_openclaw()`)

New method in `provisioner.py`, called in `run()` after `_install_dependencies()`:

- Copies the pre-built openclaw-bundle from the source (pendrive or temp copy) to `/opt/openclaw/openclaw/`
- Ensures Node 22+ is installed (already handled by `_install_dependencies()` via `brew install node`, but add a version check -- if Homebrew's default `node` formula is <22, install `node@22` specifically)
- Creates a wrapper at `/usr/local/bin/openclaw` that runs `node /opt/openclaw/openclaw/openclaw.mjs`
- Sets ownership to the real user

## 3. Provisioner: Generate OpenClaw Config (`_write_openclaw_config()` rewrite)

The existing `_write_openclaw_config()` writes `~/.openclaw/config.json` (a Mona-internal config). Rewrite it to produce OpenClaw's native config format:

`**~/.openclaw/openclaw.json**` (JSON5-compatible):

```json
{
  "gateway": {
    "port": 18789,
    "bind": "loopback",
    "auth": {
      "mode": "token",
      "token": "<generated-random-token>"
    },
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true },
        "responses": { "enabled": true }
      }
    }
  },
  "skills": {
    "load": {
      "extraDirs": [
        "/opt/openclaw/skills/local",
        "/opt/openclaw/skills/clawhub"
      ]
    }
  },
  "agents": {
    "defaults": {
      "workspace": "~/OpenClawWorkspace"
    }
  }
}
```

`**~/.openclaw/.env**` -- populated from the order's API keys (DeepSeek, Kimi, etc.) mapped to OpenClaw env var names. Also include `OPENCLAW_GATEWAY_TOKEN`.

The generated gateway token is also saved to `/opt/openclaw/state/gateway-token.txt` so Mona Hub can read it to authenticate its proxy requests.

## 4. Provisioner: Install OpenClaw Gateway Daemon

New method `_install_openclaw_gateway_daemon()`:

- Write a LaunchAgent plist at `~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- Runs: `node /opt/openclaw/openclaw/openclaw.mjs gateway run`
- `RunAtLoad: true`, `KeepAlive: true`
- Environment: `PATH` includes `/opt/homebrew/bin`, plus `OPENCLAW_STATE_DIR=~/.openclaw`
- Logs: `~/.openclaw/gateway.log` and `~/.openclaw/gateway.err.log`

This replaces the existing heartbeat daemon (`_setup_heartbeat_daemon`) or runs alongside it.

## 5. Tool Suites to OpenClaw Skills

The existing `_install_all_tool_suites()` writes `manifest.json` + YAML per suite to `/opt/openclaw/skills/local/`. OpenClaw expects `SKILL.md` files. Modify `_install_all_tool_suites()` to also write a `SKILL.md` per suite so OpenClaw can discover them:

```markdown
---
name: real-estate
description: "Real estate tools: Property Valuation, Market Analysis, ..."
---
# Real Estate Tools
Tools: Property Valuation, Market Analysis, ...
```

Keep the existing `manifest.json` for Mona Hub's tool routing UI. The `SKILL.md` is the OpenClaw-facing interface.

## 6. run-setup.sh Changes

After the existing provision step:

- Validate `openclaw-bundle/` exists on the pendrive with `dist/entry.js`
- The provisioner's `_install_openclaw()` handles copy and setup
- After Mona Hub deploy and build, start the OpenClaw gateway:

```bash
  sudo -u "$REAL_USER" launchctl bootstrap "gui/$(id -u "$REAL_USER")" \
    ~/Library/LaunchAgents/ai.openclaw.gateway.plist
  

```

- Verify gateway health: poll `http://127.0.0.1:18789/health` until ready

## 7. Mona Hub Backend: Proxy to OpenClaw Gateway

### `services/llm.py` -- rewrite as gateway client

Replace the entire `LLMService` with an `OpenClawGatewayClient` that:

- Reads the gateway token from `/opt/openclaw/state/gateway-token.txt`
- For `generate()`: sends `POST http://127.0.0.1:18789/v1/chat/completions` with `Authorization: Bearer <token>`, model `"openclaw"`, streaming off
- For `generate_stream()`: same endpoint with `stream: true`, parses SSE chunks
- `abort_generation()`: not directly supported by the HTTP API; can close the httpx stream
- `get_available_models()` / `get_routing_config()`: can query OpenClaw's `/v1/models` or retain local file reads for the UI
- Falls back gracefully if gateway is not yet running (return helpful error message)

### `routers/chat.py` -- simplify

The chat router stays mostly the same but the system prompt and tool context is now handled by OpenClaw's skills system. The `_build_system_prompt()` function passes Mona's identity prompt as the system message; OpenClaw appends skill context automatically.

### Keep unchanged

- `routers/onboarding.py`, `routers/system.py` (onboarding and Mac system settings are Mona-specific)
- `services/voice.py` (local STT/TTS stays in Mona Hub -- these are Mac-native mlx features)
- `services/tool_router.py` (keep for UI tool dropdown display, but actual tool execution goes through OpenClaw)
- `services/mac_config.py`, `services/profile.py`, `services/messaging.py`

## 8. Test Suite Updates

Update `openclaw_setup/test_suite/openclaw_core.py` to add tests:

- Verify `/opt/openclaw/openclaw/dist/entry.js` exists
- Verify `openclaw` CLI responds to `openclaw --version`
- Verify `~/.openclaw/openclaw.json` is valid JSON
- Verify gateway health endpoint responds at `http://127.0.0.1:18789/health`

## Provisioner `run()` Updated Flow

```python
def run(self):
    # ... existing: fetch order, register device, create directories ...
    self._install_dependencies()      # Homebrew, Node 22+, Python venv, pip packages
    self._install_openclaw()           # NEW: copy bundle, create wrapper
    self._write_core_configs()         # SOUL.md, AGENTS.md, TOOLS.md
    self._set_permissions()
    self._download_models()
    self._download_voice_models()
    self._install_all_tool_suites()    # MODIFIED: also write SKILL.md per suite
    self._install_clawhub_skills()
    self._setup_auto_routing()
    self._setup_tool_routing()
    self._write_active_work_json()
    self._setup_messaging_config()
    self._write_llm_provider_config()
    self._write_openclaw_config()      # REWRITTEN: produces openclaw.json + .env
    self._install_openclaw_gateway()   # NEW: LaunchAgent for gateway
    self._setup_log_rotation()
    self._store_setup_credentials()
    # ...
```

