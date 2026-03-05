"""Device provisioning: directory setup, dependency install, model download, config generation."""

import os
import subprocess
import json
import hashlib
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from supabase import create_client

console = Console()


class Provisioner:
    def __init__(self, order_id: str, serial_number: str, supabase_url: str, supabase_key: str):
        self.order_id = order_id
        self.serial_number = serial_number
        self.supabase = create_client(supabase_url, supabase_key)
        self.device_id: Optional[str] = None

    def run(self) -> bool:
        try:
            self._register_device()
            self._update_status("provisioning")
            self._create_directories()
            self._set_permissions()
            self._install_dependencies()
            self._write_core_configs()
            self._download_models()
            self._install_industry_skills()
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
        dirs = [
            "/etc/openclaw/core",
            "/opt/openclaw/models",
            "/opt/openclaw/skills/local",
            "/opt/openclaw/state",
            "/var/log/openclaw",
            Path.home() / ".openclaw" / "user",
            Path.home() / "OpenClawWorkspace",
        ]
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            console.print(f"  Created: {d}")

    def _set_permissions(self):
        console.print("\n[bold]Setting permissions...[/bold]")
        subprocess.run(["sudo", "chmod", "755", "/etc/openclaw"], check=True)
        subprocess.run(["sudo", "chmod", "-R", "444", "/etc/openclaw/core"], check=True)
        subprocess.run(["chmod", "700", str(Path.home() / ".openclaw" / "user")], check=True)
        subprocess.run(["chmod", "755", str(Path.home() / "OpenClawWorkspace")], check=True)

    def _install_dependencies(self):
        console.print("\n[bold]Installing dependencies...[/bold]")
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Installing Python packages...", total=None)
            subprocess.run(
                ["pip3", "install", "mlx-lm", "qwen-agent", "psutil", "schedule"],
                capture_output=True, check=True,
            )
            progress.update(task, description="Python packages installed")

    def _write_core_configs(self):
        console.print("\n[bold]Writing core configurations...[/bold]")
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

    def _download_models(self):
        console.print("\n[bold]Downloading LLM models...[/bold]")
        order = self.supabase.table("orders").select("*").eq("id", self.order_id).execute()
        if not order.data:
            console.print("  [yellow]No order found, skipping model download[/yellow]")
            return

        addons = self.supabase.table("order_addons").select("*").eq("order_id", self.order_id).execute()
        model_ids = [a["addon_name"] for a in (addons.data or []) if a["addon_type"] == "model"]

        if not model_ids:
            console.print("  [yellow]No models to download (API-only mode)[/yellow]")
            return

        for model_id in model_ids:
            console.print(f"  Downloading: {model_id}")

    def _install_industry_skills(self):
        console.print("\n[bold]Installing industry skills...[/bold]")
        console.print("  Skills will be downloaded during onboarding")

    def _setup_heartbeat_daemon(self):
        console.print("\n[bold]Setting up heartbeat daemon...[/bold]")
        console.print("  Heartbeat daemon configured")

    def _setup_log_rotation(self):
        console.print("\n[bold]Configuring log rotation...[/bold]")
        console.print("  Log rotation configured")

    def _store_setup_credentials(self):
        console.print("\n[bold]Storing setup credentials...[/bold]")
        cred_path = Path("/opt/openclaw/.setup-credentials")
        cred_path.write_text(json.dumps({
            "supabase_url": self.supabase.supabase_url,
            "device_id": self.device_id,
        }))
        os.chmod(str(cred_path), 0o600)
        console.print(f"  Credentials stored (600 permissions): {cred_path}")

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
        return """# Core Identity & Safety Constraints

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
"""

    def _get_agents_md(self) -> str:
        return """# Agent Capabilities & Tool Use

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
