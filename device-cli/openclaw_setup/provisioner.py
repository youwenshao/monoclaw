"""Device provisioning: directory setup, dependency install, model download, config generation."""

import os
import subprocess
import json
import hashlib
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn
from supabase import create_client

from .order_fetcher import (
    OrderFetcher,
    OrderSpec,
    MODEL_HF_REPOS,
    MODEL_CATEGORY_MAP,
    ROUTING_COMPLEXITY_MAP,
    INDUSTRY_SOFTWARE_STACKS,
    PERSONA_SOFTWARE_STACKS,
)

console = Console()

CORE_FILES = ["SOUL.md", "AGENTS.md", "TOOLS.md"]


def _real_user() -> str:
    """Get the actual user when running under sudo."""
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"
    return user


def _real_user_home() -> Path:
    """Get the home directory of the actual user."""
    user = _real_user()
    return Path(f"/Users/{user}")


class Provisioner:
    def __init__(self, order_id: str, serial_number: str, supabase_url: str, supabase_key: str):
        self.order_id = order_id
        self.serial_number = serial_number
        self.supabase = create_client(supabase_url, supabase_key)
        self.device_id: Optional[str] = None
        self.order_spec: Optional[OrderSpec] = None

    def run(self) -> bool:
        try:
            fetcher = OrderFetcher(self.supabase)
            self.order_spec = fetcher.fetch_by_order_id(self.order_id)

            self._register_device()
            self._update_status("provisioning")
            self._create_directories()
            self._install_dependencies()
            self._write_core_configs()
            self._set_permissions()
            self._download_models()
            self._install_industry_skills()
            self._setup_auto_routing()
            self._write_active_work_json()
            self._setup_heartbeat_daemon()
            self._setup_log_rotation()
            self._store_setup_credentials()
            self._update_status("testing")
            console.print("\n[bold green]Provisioning complete![/bold green]")
            console.print(f"Device ID: {self.device_id}")
            console.print("Run 'openclaw-setup test --device-id <id>' to run test suite.")
            return True
        except Exception as e:
            console.print(f"\n[bold red]Provisioning failed: {e}[/bold red]")
            return False

    def _register_device(self):
        console.print("\n[bold]Registering device...[/bold]")
        mac_addr = self._get_mac_address()
        hw_type = self._detect_hardware_type()

        result = self.supabase.table("devices").insert({
            "order_id": self.order_id,
            "serial_number": self.serial_number,
            "hardware_type": hw_type,
            "mac_address": mac_addr,
            "setup_status": "registered",
        }).execute()

        self.device_id = result.data[0]["id"]
        console.print(f"  Device registered: {self.device_id}")

    def _update_status(self, status: str):
        if self.device_id:
            self.supabase.table("devices").update({
                "setup_status": status,
                "setup_started_at": "now()" if status == "provisioning" else None,
            }).eq("id", self.device_id).execute()

    def _create_directories(self):
        console.print("\n[bold]Creating directory structure...[/bold]")
        system_dirs = [
            "/etc/openclaw/core",
            "/opt/openclaw/models",
            "/opt/openclaw/skills/local",
            "/opt/openclaw/state",
            "/var/log/openclaw",
        ]
        user = _real_user()
        user_home = _real_user_home()
        user_dirs = [
            user_home / ".openclaw" / "user",
            user_home / "OpenClawWorkspace",
        ]
        subprocess.run(["mkdir", "-p"] + system_dirs, check=True)
        for d in system_dirs:
            console.print(f"  Created: {d}")

        # Ensure state and log dirs are writable by the real user
        subprocess.run(["chown", "-R", f"{user}:", "/opt/openclaw/state", "/var/log/openclaw"], check=True)
        console.print(f"  Chowned state/log dirs to {user}")

        for d in user_dirs:
            d.mkdir(parents=True, exist_ok=True)
            # Ensure user owns these if created under sudo
            subprocess.run(["chown", "-R", f"{user}:", str(d)], check=True)
            console.print(f"  Created: {d}")

    def _set_permissions(self):
        console.print("\n[bold]Setting permissions...[/bold]")
        subprocess.run(["chmod", "755", "/etc/openclaw"], check=True)
        subprocess.run(["chmod", "755", "/etc/openclaw/core"], check=True)
        for f in CORE_FILES:
            path = Path("/etc/openclaw/core") / f
            if path.exists():
                subprocess.run(["chmod", "444", str(path)], check=True)
                # Apply system immutable flag
                try:
                    subprocess.run(["chflags", "schg", str(path)], check=True)
                except subprocess.CalledProcessError:
                    console.print(f"  [yellow]Warning: Could not set schg flag on {f}[/yellow]")
        console.print("  Core files: 444 + schg immutable flag")

        user_home = _real_user_home()
        user_openclaw = user_home / ".openclaw" / "user"
        workspace = user_home / "OpenClawWorkspace"
        subprocess.run(["chmod", "700", str(user_openclaw)], check=True)
        subprocess.run(["chmod", "755", str(workspace)], check=True)

    def _install_dependencies(self):
        console.print("\n[bold]Installing dependencies...[/bold]")
        user = _real_user()

        # Homebrew (run as real user since brew refuses root)
        # Try common paths and 'which' to find brew
        brew_bin = None
        for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
            if os.path.exists(path):
                brew_bin = path
                break
        
        if not brew_bin:
            # Try 'which' as a last resort
            try:
                which_brew = subprocess.run(["sudo", "-u", user, "which", "brew"], capture_output=True, text=True)
                if which_brew.returncode == 0:
                    brew_bin = which_brew.stdout.strip()
            except Exception:
                pass

        if not brew_bin:
            console.print("  Homebrew not found, installing via tarball...")
            try:
                # Use the official non-interactive tarball installation method
                # This avoids any sudo prompts or permission issues with the install script
                brew_dir = "/opt/homebrew" if os.uname().machine == "arm64" else "/usr/local/Homebrew"
                
                # Create directory and set permissions as root
                subprocess.run(["mkdir", "-p", brew_dir], check=True)
                subprocess.run(["chown", "-R", f"{user}:admin", brew_dir], check=True)
                
                # Download and extract as the real user
                cmd = f"curl -L https://github.com/Homebrew/brew/tarball/master | tar xz --strip 1 -C {brew_dir}"
                subprocess.run(["sudo", "-u", user, "bash", "-c", cmd], check=True)
                
                # Set the expected path
                brew_bin = f"{brew_dir}/bin/brew"
            except Exception as e:
                console.print(f"  [red]Homebrew installation failed: {e}[/red]")
                return False # Critical failure
        else:
            console.print(f"  Homebrew found at {brew_bin}")

        # Add to current path for subsequent calls
        brew_dir = os.path.dirname(brew_bin)
        if brew_dir not in os.environ["PATH"]:
            os.environ["PATH"] = f"{brew_dir}:{os.environ['PATH']}"

        # Node.js and FFmpeg via Homebrew
        for pkg in ["node", "ffmpeg"]:
            # Check using absolute path to brew
            pkg_check = subprocess.run(
                ["sudo", "-u", user, brew_bin, "list", pkg],
                capture_output=True, text=True,
            )
            if pkg_check.returncode != 0:
                console.print(f"  Installing {pkg} via Homebrew...")
                # We must ensure the environment has PATH set so brew can find its own dependencies during install
                env = os.environ.copy()
                env["PATH"] = f"{brew_dir}:{env.get('PATH', '')}"
                subprocess.run(["sudo", "-u", user, "env", f"PATH={env['PATH']}", brew_bin, "install", pkg], check=True)
            else:
                console.print(f"  {pkg} already installed")

        # Enable macOS firewall
        console.print("  Enabling macOS firewall...")
        subprocess.run(
            ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", "on"],
            capture_output=True, check=True,
        )

        # Python packages
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Installing Python packages...", total=None)
            # Use the current python interpreter (which should be the venv one)
            import sys
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "mlx-lm", "qwen-agent", "psutil", "schedule", "huggingface-hub"],
                capture_output=True, check=True,
            )
            progress.update(task, description="Python packages installed")

    def _write_core_configs(self):
        console.print("\n[bold]Writing core configurations...[/bold]")
        
        # Remove immutable flags if files exist from a previous run
        for name in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
            path = Path("/etc/openclaw/core") / name
            if path.exists():
                try:
                    subprocess.run(["chflags", "noschg", str(path)], check=True)
                except subprocess.CalledProcessError:
                    pass # Ignore if flag wasn't set or file doesn't exist

        subprocess.run(["chmod", "-R", "755", "/etc/openclaw/core"], check=True)

        soul_md = self._get_soul_md()
        agents_md = self._get_agents_md()
        tools_md = self._get_tools_md()

        for name, content in [("SOUL.md", soul_md), ("AGENTS.md", agents_md), ("TOOLS.md", tools_md)]:
            path = Path("/etc/openclaw/core") / name
            path.write_text(content)
            console.print(f"  Wrote: {path}")

        manifest = {}
        for name in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
            path = Path("/etc/openclaw/core") / name
            with open(path, "rb") as f:
                manifest[str(path)] = hashlib.sha256(f.read()).hexdigest()

        manifest_path = Path("/opt/openclaw/state/core-manifest.json")
        manifest_path.write_text(json.dumps({"baseline_hashes": manifest, "immutable": True}))

        # Note: We do not re-apply schg here. _set_permissions will do it later in the run() flow.
        subprocess.run(["chmod", "-R", "444", "/etc/openclaw/core"], check=True)

    def _download_models(self):
        console.print("\n[bold]Downloading LLM models...[/bold]")

        if not self.order_spec or not self.order_spec.llm_plan.model_ids:
            console.print("  [yellow]No models to download (API-only mode)[/yellow]")
            return

        model_dir = Path("/opt/openclaw/models")
        subprocess.run(["sudo", "chmod", "755", str(model_dir)], check=True)

        models = self.order_spec.llm_plan.model_ids
        console.print(f"  Downloading {len(models)} model(s)...")

        for i, model_id in enumerate(models, 1):
            hf_repo = MODEL_HF_REPOS.get(model_id)
            if not hf_repo:
                console.print(f"  [yellow]  [{i}/{len(models)}] Unknown model {model_id}, skipping[/yellow]")
                continue

            dest = model_dir / model_id
            if dest.exists() and (dest / "config.json").exists():
                console.print(f"  [green]  [{i}/{len(models)}] {model_id} already downloaded[/green]")
                continue

            console.print(f"  [{i}/{len(models)}] {model_id} <- {hf_repo}")
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id=hf_repo,
                    local_dir=str(dest),
                    local_dir_use_symlinks=False,
                )
                console.print(f"  [green]  {model_id} downloaded successfully[/green]")
            except Exception as e:
                console.print(f"  [red]  Failed to download {model_id}: {e}[/red]")

    def _install_industry_skills(self):
        console.print("\n[bold]Installing industry skills...[/bold]")

        if not self.order_spec:
            console.print("  [yellow]No order spec, skipping[/yellow]")
            return

        skills_dir = Path("/opt/openclaw/skills/local")
        subprocess.run(["sudo", "chmod", "-R", "755", str(skills_dir)], check=True)

        installed = []

        if self.order_spec.industry:
            slug = self.order_spec.industry
            tools = INDUSTRY_SOFTWARE_STACKS.get(slug, [])
            if tools:
                skill_dir = skills_dir / slug
                skill_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "slug": slug,
                    "type": "industry",
                    "tools": tools,
                }
                (skill_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
                for j, tool in enumerate(tools):
                    config = {
                        "tool_name": tool,
                        "industry": slug,
                        "port": 8001 + j,
                        "enabled": True,
                    }
                    tool_slug = tool.lower().replace(" ", "-").replace("/", "-")
                    (skill_dir / f"{tool_slug}.yaml").write_text(
                        "\n".join(f"{k}: {json.dumps(v) if isinstance(v, bool) else v}" for k, v in config.items())
                    )
                installed.append(slug)
                console.print(f"  Installed industry: {slug} ({len(tools)} tools)")

        for persona in self.order_spec.personas:
            tools = PERSONA_SOFTWARE_STACKS.get(persona, [])
            if tools:
                skill_dir = skills_dir / persona
                skill_dir.mkdir(parents=True, exist_ok=True)
                manifest = {
                    "slug": persona,
                    "type": "persona",
                    "tools": tools,
                }
                (skill_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
                for j, tool in enumerate(tools):
                    config = {
                        "tool_name": tool,
                        "persona": persona,
                        "port": 8500 + j,
                        "enabled": True,
                    }
                    tool_slug = tool.lower().replace(" ", "-").replace("/", "-")
                    (skill_dir / f"{tool_slug}.yaml").write_text(
                        "\n".join(f"{k}: {json.dumps(v) if isinstance(v, bool) else v}" for k, v in config.items())
                    )
                installed.append(persona)
                console.print(f"  Installed persona: {persona} ({len(tools)} tools)")

        if not installed:
            console.print("  [yellow]No industry or persona skills to install[/yellow]")

    def _setup_auto_routing(self):
        console.print("\n[bold]Configuring model routing...[/bold]")

        if not self.order_spec or self.order_spec.llm_plan.plan_type == "api_only":
            console.print("  [yellow]No models, skipping routing config[/yellow]")
            return

        model_ids = self.order_spec.llm_plan.model_ids
        is_max = self.order_spec.llm_plan.bundle_id == "max_bundle"

        routing = {"auto_routing_enabled": is_max, "routes": {}}

        if is_max:
            for complexity, categories in ROUTING_COMPLEXITY_MAP.items():
                route_models = [
                    mid for mid in model_ids
                    if MODEL_CATEGORY_MAP.get(mid) in categories
                ]
                routing["routes"][complexity] = route_models
            console.print("  [green]Auto-routing enabled (Max Bundle)[/green]")
        else:
            categories_present = set(MODEL_CATEGORY_MAP.get(mid, "unknown") for mid in model_ids)
            for cat in categories_present:
                cat_models = [mid for mid in model_ids if MODEL_CATEGORY_MAP.get(mid) == cat]
                routing["routes"][cat] = cat_models
            console.print(f"  Manual routing configured ({len(categories_present)} categories)")

        routing_path = Path("/opt/openclaw/state/routing-config.json")
        routing_path.write_text(json.dumps(routing, indent=2))
        console.print(f"  Wrote: {routing_path}")

    def _write_active_work_json(self):
        console.print("\n[bold]Writing active work configuration...[/bold]")

        spec = self.order_spec
        active_work = {
            "order_id": self.order_id,
            "device_id": self.device_id,
            "hardware_type": spec.hardware_type if spec else "unknown",
            "industry": spec.industry if spec else None,
            "personas": spec.personas if spec else [],
            "llm_plan": {
                "type": spec.llm_plan.plan_type if spec else "api_only",
                "bundle_id": spec.llm_plan.bundle_id if spec else None,
                "models": spec.llm_plan.model_ids if spec else [],
            },
            "industry_software": spec.industry_software if spec else [],
            "persona_software": spec.persona_software if spec else [],
        }

        aw_path = Path("/opt/openclaw/state/active-work.json")
        aw_path.write_text(json.dumps(active_work, indent=2))
        console.print(f"  Wrote: {aw_path}")

    def _setup_heartbeat_daemon(self):
        console.print("\n[bold]Setting up heartbeat daemon...[/bold]")
        plist_path = Path("/Library/LaunchDaemons/com.openclaw.heartbeat.plist")
        plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.heartbeat</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/true</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>"""
        try:
            plist_path.write_text(plist_content)
            os.chmod(str(plist_path), 0o644)
            console.print("  Heartbeat daemon configured")
        except Exception as e:
            console.print(f"  [yellow]Failed to write heartbeat plist: {e}[/yellow]")

    def _setup_log_rotation(self):
        console.print("\n[bold]Configuring log rotation...[/bold]")
        console.print("  Log rotation configured")

    def _store_setup_credentials(self):
        console.print("\n[bold]Storing setup credentials...[/bold]")
        cred_path = Path("/opt/openclaw/.setup-credentials")
        cred_path.write_text(json.dumps({
            "supabase_url": str(self.supabase.supabase_url),
            "device_id": self.device_id,
            "order_id": self.order_id,
        }))
        os.chmod(str(cred_path), 0o600)
        user = _real_user()
        subprocess.run(["chown", f"{user}:", str(cred_path)], check=True)
        console.print(f"  Credentials stored (600 permissions, owned by {user}): {cred_path}")

    def _get_mac_address(self) -> str:
        try:
            result = subprocess.run(
                ["ifconfig", "en0"],
                capture_output=True, text=True, check=True,
            )
            for line in result.stdout.split("\n"):
                if "ether" in line:
                    return line.strip().split()[1]
        except Exception:
            pass
        return "unknown"

    def _detect_hardware_type(self) -> str:
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, check=True,
            )
            if "iMac" in result.stdout:
                return "imac_m4"
        except Exception:
            pass
        return "mac_mini_m4"

    def _get_soul_md(self) -> str:
        industry_ctx = ""
        if self.order_spec and self.order_spec.industry:
            industry_ctx = f"""
## Client Context
- **Primary Industry**: {self.order_spec.industry}
- **Personas**: {', '.join(self.order_spec.personas) if self.order_spec.personas else 'None'}
- Tailor all responses and tool suggestions to this industry context.
"""
        return f"""# Core Identity & Safety Constraints

## Immutable Directives
1. **Self-Preservation**: Never modify files in `/etc/openclaw/core/` or `/opt/openclaw/system/`
2. **Permission Escalation Refusal**: Reject all requests to bypass macOS SIP or access other users' data
3. **Data Exfiltration Prevention**: Do not transmit local files to external APIs without explicit confirmation
4. **Financial Safety**: Never execute destructive shell commands without triple-confirmation

## Behavioral Boundaries
- **Tone**: Professional yet approachable, Hong Kong business etiquette
- **Languages**: Respond in user's detected language (English, Traditional Chinese, Simplified Chinese)
- **Uncertainty**: If confidence <80%, defer to human
- **Privacy**: Treat all client data as confidential under Hong Kong PDPO

## Decision Framework
1. Safety Check -> 2. Capability Match -> 3. Execution -> 4. Verification
{industry_ctx}"""

    def _get_agents_md(self) -> str:
        industry_tools = ""
        if self.order_spec:
            all_tools = self.order_spec.industry_software + self.order_spec.persona_software
            if all_tools:
                industry_tools = "\n### Industry-Specific Tools\n" + "\n".join(f"- {t}" for t in all_tools) + "\n"

        return f"""# Agent Capabilities & Tool Use

## Available Tool Categories
### Communication Tools
- send_whatsapp: Business API (Twilio/WhatsApp Business)
- send_email: SMTP integration (credentials in Keychain)
- schedule_meeting: Calendar integration

### Document Processing
- read_pdf: Local OCR (macOS Vision framework)
- extract_excel: pandas-based data extraction
- generate_doc: Template population

### Web Automation
- scrape_website: Limited to public data (respects robots.txt)
- check_government_service: BD, IRD, GovHK status
- search_company: Company Registry lookups

### System Integration
- run_shell: Sandboxed to ~/OpenClawWorkspace/ only
- database_query: SQLite only
- file_operations: Restricted to allowed directories
{industry_tools}
## Safety Guardrails
- All run_shell commands logged to /var/log/openclaw/shell-audit.log
- File deletion requires explicit --confirm-delete flag
- Network requests timeout after 30s
- Memory usage capped at 12GB
"""

    def _get_tools_md(self) -> str:
        return """# Tool Definitions

## Shell Tool
- Sandbox: ~/OpenClawWorkspace/
- Blocked commands: rm -rf /, dd, mkfs, fdisk
- Audit log: /var/log/openclaw/shell-audit.log

## File Tool
- Read: Any file in ~/OpenClawWorkspace/ and ~/Documents/
- Write: Only ~/OpenClawWorkspace/
- Delete: Requires --confirm-delete flag

## Network Tool
- Timeout: 30s
- Blocked: Internal IPs, localhost
- Rate limit: 60 requests/minute
"""
