"""Device provisioning: directory setup, dependency install, model download, config generation."""

import os
import secrets
import shutil
import sys
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
    ALL_TOOL_SUITES,
)

console = Console()

CORE_FILES = ["SOUL.md", "AGENTS.md", "TOOLS.md"]
OPENCLAW_INSTALL_DIR = Path("/opt/openclaw/openclaw")
OPENCLAW_GATEWAY_PORT = 18789
MIN_NODE_MAJOR = 22
OPENCLAW_MODELS_PATH = Path("/opt/openclaw/models")
VOICE_MODEL_DIRS = {"whisper-large-v3-turbo", "qwen3_tts", "qwen3-tts"}


def _real_user() -> str:
    """Get the actual user when running under sudo."""
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"
    return user


def _real_user_home() -> Path:
    """Get the home directory of the actual user."""
    user = _real_user()
    return Path(f"/Users/{user}")


# Used by sync_openclaw_config_from_state and _write_openclaw_config
_ENV_KEY_MAP = {
    "deepseek": "DEEPSEEK_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "glm5": "GLM_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_PROVIDER_MODEL_MAP = {
    "deepseek": "deepseek/deepseek-chat",
    "openai": "openai/gpt-4o",
    "anthropic": "anthropic/claude-sonnet-4-5",
    "kimi": "moonshot/kimi-k2.5",
    "glm5": "glm5/glm-4-flash",
}


def _default_model_from_llm_cfg(llm_cfg: dict) -> str | None:
    """Return OpenClaw 'provider/model' from llm-provider config when provider has API key."""
    provider = (llm_cfg.get("default_provider") or llm_cfg.get("provider") or "").strip().lower()
    if not provider:
        return None
    model = _PROVIDER_MODEL_MAP.get(provider)
    if model and llm_cfg.get("api_keys", {}).get(provider):
        return model
    return None


def _first_local_model_id_static() -> str | None:
    """First non-voice model dir under /opt/openclaw/models for Ollama default."""
    if not OPENCLAW_MODELS_PATH.exists():
        return None
    for entry in sorted(OPENCLAW_MODELS_PATH.iterdir()):
        if entry.is_dir() and entry.name not in VOICE_MODEL_DIRS:
            return entry.name
    return None


def _model_from_routing(routing_cfg: dict) -> str | None:
    """If routing has active_model_id that is a local model, return ollama/{id}."""
    active = routing_cfg.get("active_model_id")
    if not active or not isinstance(active, str):
        return None
    if active in VOICE_MODEL_DIRS:
        return None
    if (OPENCLAW_MODELS_PATH / active).exists():
        return f"ollama/{active}"
    return None


def sync_openclaw_config_from_state() -> None:
    """Write ~/.openclaw from state files, preserving gateway token. Used by reconfigure-gateway."""
    user = _real_user()
    user_home = _real_user_home()
    state_dir = user_home / ".openclaw"
    state_dir.mkdir(parents=True, exist_ok=True)

    token_path = Path("/opt/openclaw/state/gateway-token.txt")
    gateway_token = ""
    if token_path.exists():
        try:
            gateway_token = token_path.read_text().strip()
        except OSError:
            pass
    if not gateway_token:
        console.print("[yellow]No gateway token found; run full provision to generate one.[/yellow]")
        return

    llm_config_path = Path("/opt/openclaw/state/llm-provider.json")
    llm_cfg = {}
    if llm_config_path.exists():
        try:
            llm_cfg = json.loads(llm_config_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    routing_path = Path("/opt/openclaw/state/routing-config.json")
    routing_cfg = {}
    if routing_path.exists():
        try:
            routing_cfg = json.loads(routing_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    config_path = state_dir / "openclaw.json"
    existing_model = None
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
            existing_model = (existing.get("agents") or {}).get("defaults", {}).get("model")
        except (json.JSONDecodeError, OSError):
            pass

    # Default model: routing active (local) > cloud from llm > existing > first local
    computed_model = _model_from_routing(routing_cfg)
    if not computed_model:
        computed_model = _default_model_from_llm_cfg(llm_cfg)
    if not computed_model and existing_model:
        computed_model = existing_model
    if not computed_model:
        first_local = _first_local_model_id_static()
        if first_local:
            computed_model = f"ollama/{first_local}"

    config = {
        "gateway": {
            "mode": "local",
            "port": OPENCLAW_GATEWAY_PORT,
            "bind": "loopback",
            "auth": {"mode": "token", "token": gateway_token},
            "http": {
                "endpoints": {
                    "chatCompletions": {"enabled": True},
                    "responses": {"enabled": True},
                }
            },
        },
        "skills": {
            "load": {
                "extraDirs": [
                    "/opt/openclaw/skills/local",
                    "/opt/openclaw/skills/clawhub",
                ]
            }
        },
        "agents": {
            "defaults": {
                "workspace": str(user_home / "OpenClawWorkspace"),
            }
        },
    }
    if computed_model:
        config["agents"]["defaults"]["model"] = computed_model

    config_path.write_text(json.dumps(config, indent=2))
    if os.geteuid() == 0:
        subprocess.run(["chown", f"{user}:", str(config_path)], check=True)

    our_env_keys = {"OPENCLAW_GATEWAY_TOKEN"} | set(_ENV_KEY_MAP.values())
    env_lines = [f"OPENCLAW_GATEWAY_TOKEN={gateway_token}"]
    env_path = state_dir / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text().splitlines():
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    env_lines.append(line)
                    continue
                if "=" in line_stripped:
                    key = line_stripped.split("=", 1)[0].strip()
                    if key not in our_env_keys:
                        env_lines.append(line)
        except OSError:
            pass
    for provider, env_name in _ENV_KEY_MAP.items():
        val = llm_cfg.get("api_keys", {}).get(provider)
        if val:
            env_lines.append(f"{env_name}={val}")
    env_path.write_text("\n".join(env_lines) + "\n")
    if os.geteuid() == 0:
        subprocess.run(["chown", f"{user}:", str(env_path)], check=True)
    os.chmod(str(env_path), 0o600)


def restart_gateway() -> bool:
    """Stop then start the OpenClaw gateway LaunchAgent (so it picks up new config). Returns True on success."""
    user = _real_user()
    user_home = _real_user_home()
    plist_path = user_home / "Library" / "LaunchAgents" / "ai.openclaw.gateway.plist"
    if not plist_path.exists():
        console.print(f"[yellow]Gateway plist not found: {plist_path}[/yellow]")
        return False
    try:
        uid = subprocess.run(
            ["id", "-u", user],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return False
    domain = f"gui/{uid}"
    run_as_user = os.geteuid() == 0
    prefix = ["sudo", "-u", user] if run_as_user else []
    subprocess.run(
        prefix + ["launchctl", "bootout", domain, str(plist_path)],
        capture_output=True,
        timeout=10,
    )
    result = subprocess.run(
        prefix + ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        console.print(f"[yellow]launchctl bootstrap failed: {result.stderr.decode() if result.stderr else 'unknown'}[/yellow]")
        return False
    return True


class Provisioner:
    def __init__(self, order_id: str, serial_number: str, supabase_url: str, supabase_key: str):
        self.order_id = order_id
        self.serial_number = serial_number
        self.supabase = create_client(supabase_url, supabase_key)
        self.device_id: Optional[str] = None
        self.order_spec: Optional[OrderSpec] = None
        self.hf_token: Optional[str] = os.environ.get("HF_TOKEN")
        self.clawhub_token: Optional[str] = os.environ.get("CLAWHUB_TOKEN")

    def run(self) -> bool:
        try:
            fetcher = OrderFetcher(self.supabase)
            self.order_spec = fetcher.fetch_by_order_id(self.order_id)

            self._register_device()
            self._update_status("provisioning")
            self._create_directories()
            self._install_dependencies()
            self._install_openclaw()
            self._write_core_configs()
            self._set_permissions()
            self._download_models()
            self._download_voice_models()
            user = _real_user()
            subprocess.run(["chown", "-R", f"{user}:", "/opt/openclaw/models"], check=True)
            console.print(f"  Chowned models to {user}")
            self._install_all_tool_suites()
            self._install_clawhub_skills()
            self._setup_auto_routing()
            self._setup_tool_routing()
            self._write_active_work_json()
            self._setup_messaging_config()
            self._write_llm_provider_config()
            self._write_openclaw_config()
            self._install_openclaw_gateway()
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
            "/opt/openclaw/skills/clawhub",
            "/opt/openclaw/state",
            "/opt/openclaw/state/chat",
            "/opt/openclaw/config/messaging",
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
        subprocess.run(["chown", "-R", f"{user}:", "/opt/openclaw/state", "/opt/openclaw/state/chat", "/var/log/openclaw"], check=True)
        console.print(f"  Chowned state/log dirs to {user}")

        for d in user_dirs:
            d.mkdir(parents=True, exist_ok=True)
            # Ensure user owns these if created under sudo
            subprocess.run(["chown", "-R", f"{user}:", str(d)], check=True)
            console.print(f"  Created: {d}")

        # Ensure the base ~/.openclaw directory is also owned by the user
        subprocess.run(["chown", f"{user}:", str(user_home / ".openclaw")], check=True)

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

        # FFmpeg via Homebrew
        pkg_check = subprocess.run(
            ["sudo", "-u", user, brew_bin, "list", "ffmpeg"],
            capture_output=True, text=True,
        )
        if pkg_check.returncode != 0:
            console.print("  Installing ffmpeg via Homebrew...")
            env = os.environ.copy()
            env["PATH"] = f"{brew_dir}:{env.get('PATH', '')}"
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", brew_bin, "install", "ffmpeg"],
                check=True, timeout=600, stdin=subprocess.DEVNULL,
            )
        else:
            console.print("  ffmpeg already installed")

        # Node.js 22+ (required by OpenClaw). Check existing version first.
        env = os.environ.copy()
        env["PATH"] = f"{brew_dir}:{env.get('PATH', '')}"
        node_ok = False
        try:
            node_ver = subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "node", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if node_ver.returncode == 0:
                ver_str = node_ver.stdout.strip().lstrip("v")
                major = int(ver_str.split(".")[0])
                if major >= MIN_NODE_MAJOR:
                    node_ok = True
                    console.print(f"  Node.js v{ver_str} found (>= {MIN_NODE_MAJOR})")
                else:
                    console.print(f"  Node.js v{ver_str} found but < {MIN_NODE_MAJOR}, upgrading...")
        except Exception:
            pass

        if not node_ok:
            console.print(f"  Installing Node.js {MIN_NODE_MAJOR}+ via Homebrew...")
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", brew_bin, "install", f"node@{MIN_NODE_MAJOR}"],
                capture_output=True, timeout=600, stdin=subprocess.DEVNULL,
            )
            # Link it so 'node' resolves to node@22
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", brew_bin, "link", "--overwrite", f"node@{MIN_NODE_MAJOR}"],
                capture_output=True, timeout=60, stdin=subprocess.DEVNULL,
            )
            # Verify
            ver_check = subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "node", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            console.print(f"  Node.js installed: {ver_check.stdout.strip()}")

        # pnpm (required by OpenClaw gateway Control UI build)
        pnpm_ok = False
        try:
            pnpm_ver = subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "pnpm", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if pnpm_ver.returncode == 0 and pnpm_ver.stdout.strip():
                pnpm_ok = True
                console.print(f"  pnpm v{pnpm_ver.stdout.strip()} found")
        except Exception:
            pass
        if not pnpm_ok:
            console.print("  Installing pnpm globally for OpenClaw Control UI...")
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "npm", "install", "-g", "pnpm"],
                capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
            )
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "pnpm", "--version"],
                capture_output=True, text=True, timeout=10, check=True,
            )
            console.print("  pnpm installed")

        # Enable macOS firewall
        console.print("  Enabling macOS firewall...")
        subprocess.run(
            ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", "on"],
            capture_output=True, check=True,
        )

        # Create permanent venv for Mona Hub
        venv_dir = Path("/opt/openclaw/venv")
        if not venv_dir.exists():
            console.print("  Creating permanent Python environment...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            subprocess.run(["chown", "-R", f"{user}:", str(venv_dir)], check=True)

        venv_python = str(venv_dir / "bin" / "python3")

        # Python packages
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Installing core Python packages...", total=None)
            subprocess.run(
                ["sudo", "-u", user, venv_python, "-m", "pip", "install", "numpy<2.0", "mlx-lm", "qwen-agent", "psutil", "schedule", "huggingface-hub", "mlx-whisper", "fastapi", "uvicorn[standard]", "httpx", "python-multipart", "sentence-transformers>=3.0"],
                capture_output=True, check=True, timeout=600, stdin=subprocess.DEVNULL,
            )
            progress.update(task, description="Core Python packages installed")

            # Verify sentence-transformers import (used by tool_router for embedding-based routing)
            verify_st = subprocess.run(
                ["sudo", "-u", user, venv_python, "-c", "from sentence_transformers import SentenceTransformer; print('OK')"],
                capture_output=True, text=True, timeout=30,
            )
            if "OK" not in (verify_st.stdout or ""):
                console.print("  [yellow]Warning: sentence-transformers import check failed; tool auto-routing may use keyword fallback.[/yellow]")

            task2 = progress.add_task("Installing mlx-audio (requires pre-release transformers)...", total=None)
            subprocess.run(
                ["sudo", "-u", user, venv_python, "-m", "pip", "install", "mlx-audio>=0.3.0", "--pre"],
                capture_output=True, check=True, timeout=600, stdin=subprocess.DEVNULL,
            )
            
            # Verify mlx-audio qwen3_tts module is available
            verify_result = subprocess.run(
                ["sudo", "-u", user, venv_python, "-c", "from mlx_audio.tts.models.qwen3_tts import qwen3_tts; print('OK')"],
                capture_output=True, text=True, timeout=30,
            )
            if "OK" not in verify_result.stdout:
                console.print("[red]Error: mlx-audio qwen3_tts module not available after install. Check dependency conflicts.[/red]")
                raise RuntimeError("mlx-audio qwen3_tts module missing")
                
            progress.update(task2, description="mlx-audio installed and verified")

        # Persist HuggingFace token on the device for future model downloads
        if self.hf_token:
            console.print("  Persisting HuggingFace token...")
            try:
                login_result = subprocess.run(
                    ["sudo", "-u", user, venv_python, "-m", "huggingface_hub.commands.huggingface_cli",
                     "login", "--token", self.hf_token],
                    capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                )
                if login_result.returncode == 0:
                    console.print("  [green]HuggingFace token saved to device[/green]")
                else:
                    console.print("  [yellow]Warning: Could not persist HF token (login failed).[/yellow]")
                    if login_result.stderr:
                        console.print(f"  [dim]{login_result.stderr.strip()[:200]}[/dim]")
            except Exception as e:
                console.print(f"  [yellow]Warning: Could not persist HF token: {e}[/yellow]")

        # Pre-download embedding model for tool auto-routing (avoids first-request latency)
        _embedding_model_id = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        console.print("  Pre-downloading embedding model for tool auto-routing...")
        preload_cmd = [
            "sudo", "-u", user,
            venv_python, "-c",
            f"from sentence_transformers import SentenceTransformer; m = SentenceTransformer({repr(_embedding_model_id)}); print('OK')",
        ]
        if self.hf_token:
            preload_cmd.insert(2, "env")
            preload_cmd.insert(3, f"HF_TOKEN={self.hf_token}")
        preload_result = subprocess.run(
            preload_cmd,
            capture_output=True,
            text=True,
            timeout=300,
            stdin=subprocess.DEVNULL,
        )
        if "OK" in (preload_result.stdout or ""):
            console.print("  [green]Embedding model cached[/green]")
        else:
            console.print("  [yellow]Warning: Embedding model pre-download failed; will download on first use.[/yellow]")
            if preload_result.stderr:
                console.print(f"  [dim]{preload_result.stderr.strip()[:500]}[/dim]")

    def _install_openclaw(self):
        """Copy pre-built OpenClaw bundle to /opt/openclaw/openclaw/ and create CLI wrapper."""
        console.print("\n[bold]Installing OpenClaw...[/bold]")
        user = _real_user()

        bundle_src = os.environ.get("OPENCLAW_BUNDLE_SRC")
        if not bundle_src or not Path(bundle_src).is_dir():
            raise RuntimeError(
                "OPENCLAW_BUNDLE_SRC not set or directory missing. "
                "Ensure openclaw-bundle/ is on the pendrive."
            )

        src = Path(bundle_src)
        entry_js = src / "dist" / "entry.js"
        entry_mjs = src / "dist" / "entry.mjs"
        if not entry_js.exists() and not entry_mjs.exists():
            raise RuntimeError(f"Pre-built OpenClaw bundle missing dist/entry.(m)js at {src}")

        dest = OPENCLAW_INSTALL_DIR
        if dest.exists():
            console.print("  Removing previous OpenClaw installation...")
            shutil.rmtree(dest)

        console.print(f"  Copying bundle from {src} to {dest}...")
        shutil.copytree(str(src), str(dest), symlinks=True)
        subprocess.run(["chown", "-R", f"{user}:", str(dest)], check=True)
        console.print(f"  [green]OpenClaw installed to {dest}[/green]")

        # Create /usr/local/bin/openclaw wrapper
        wrapper_path = Path("/usr/local/bin/openclaw")
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper_path.write_text(
            "#!/bin/bash\n"
            f'exec /opt/homebrew/bin/node "{dest}/openclaw.mjs" "$@"\n'
        )
        wrapper_path.chmod(0o755)
        console.print(f"  [green]CLI wrapper created: {wrapper_path}[/green]")

        # Verify the CLI responds
        try:
            ver = subprocess.run(
                ["sudo", "-u", user, str(wrapper_path), "--version"],
                capture_output=True, text=True, timeout=15,
            )
            if ver.returncode == 0:
                console.print(f"  OpenClaw version: {ver.stdout.strip()}")
            else:
                console.print(f"  [yellow]Warning: openclaw --version returned {ver.returncode}[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]Warning: Could not verify openclaw CLI: {e}[/yellow]")

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
                    token=self.hf_token,
                )
                console.print(f"  [green]  {model_id} downloaded successfully[/green]")
            except Exception as e:
                console.print(f"  [red]  Failed to download {model_id}: {e}[/red]")

    def _install_all_tool_suites(self):
        console.print("\n[bold]Installing all tool suites...[/bold]")

        skills_dir = Path("/opt/openclaw/skills/local")
        subprocess.run(["sudo", "chmod", "-R", "755", str(skills_dir)], check=True)

        base_port = 8001
        for i, suite in enumerate(ALL_TOOL_SUITES):
            suite_id = suite["id"]
            tools = suite["tools"]
            suite_name = suite["name"]

            skill_dir = skills_dir / suite_id
            skill_dir.mkdir(parents=True, exist_ok=True)

            manifest = {
                "slug": suite_id,
                "name": suite_name,
                "type": "tool_suite",
                "tools": tools,
            }
            (skill_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

            # Write SKILL.md for OpenClaw agent skill discovery
            tools_list = ", ".join(tools)
            skill_md = (
                f"---\n"
                f"name: {suite_id}\n"
                f"description: \"{suite_name}: {tools_list}\"\n"
                f"---\n\n"
                f"# {suite_name}\n\n"
                f"Industry tool suite providing the following capabilities:\n\n"
            )
            for tool in tools:
                skill_md += f"- **{tool}**\n"
            skill_md += (
                f"\nUse this skill when the user's request relates to {suite_name.lower()} tasks. "
                f"Route through the `/{suite_id}` slash command or let auto-routing match.\n"
            )
            (skill_dir / "SKILL.md").write_text(skill_md)

            for j, tool in enumerate(tools):
                config = {
                    "tool_name": tool,
                    "suite": suite_id,
                    "port": base_port + (i * 4) + j,
                    "enabled": True,
                }
                tool_slug = tool.lower().replace(" ", "-").replace("/", "-")
                (skill_dir / f"{tool_slug}.yaml").write_text(
                    "\n".join(f"{k}: {json.dumps(v) if isinstance(v, bool) else v}" for k, v in config.items())
                )

            console.print(f"  [{i + 1}/{len(ALL_TOOL_SUITES)}] {suite_name} ({len(tools)} tools)")

        console.print(f"  [green]Installed all {len(ALL_TOOL_SUITES)} tool suites with SKILL.md[/green]")

    def _setup_auto_routing(self):
        console.print("\n[bold]Configuring model routing...[/bold]")

        if not self.order_spec or self.order_spec.llm_plan.plan_type == "api_only":
            console.print("  [yellow]No models, skipping routing config[/yellow]")
            return

        model_ids = self.order_spec.llm_plan.model_ids
        is_max = self.order_spec.llm_plan.bundle_id == "max_bundle"

        routing = {
            "auto_routing_enabled": is_max,
            "active_model_id": model_ids[0] if model_ids else None,
            "routes": {}
        }

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

    def _setup_tool_routing(self):
        console.print("\n[bold]Configuring tool auto-routing...[/bold]")

        tool_routing = {
            "auto_routing_enabled": True,
            "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "confidence_threshold": 0.5,
            "suites": [],
        }

        for suite in ALL_TOOL_SUITES:
            tool_routing["suites"].append({
                "id": suite["id"],
                "name": suite["name"],
                "tools": suite["tools"],
                "description": f"{suite['name']}: {', '.join(suite['tools'])}",
            })

        tool_routing_path = Path("/opt/openclaw/state/tool-routing-config.json")
        tool_routing_path.write_text(json.dumps(tool_routing, indent=2))
        console.print(f"  Wrote: {tool_routing_path}")
        console.print(f"  [green]Tool auto-routing configured for {len(ALL_TOOL_SUITES)} suites[/green]")

    def _write_active_work_json(self):
        console.print("\n[bold]Writing active work configuration...[/bold]")

        spec = self.order_spec
        active_work = {
            "order_id": self.order_id,
            "device_id": self.device_id,
            "hardware_type": spec.hardware_type if spec else "unknown",
            "llm_plan": {
                "type": spec.llm_plan.plan_type if spec else "api_only",
                "bundle_id": spec.llm_plan.bundle_id if spec else None,
                "models": spec.llm_plan.model_ids if spec else [],
            },
            "tool_suites": [s["id"] for s in ALL_TOOL_SUITES],
        }

        aw_path = Path("/opt/openclaw/state/active-work.json")
        aw_path.write_text(json.dumps(active_work, indent=2))
        console.print(f"  Wrote: {aw_path}")

    def _install_openclaw_gateway(self):
        """Install OpenClaw gateway as a macOS LaunchAgent."""
        console.print("\n[bold]Installing OpenClaw gateway daemon...[/bold]")
        user = _real_user()
        user_home = _real_user_home()

        agents_dir = user_home / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        label = "ai.openclaw.gateway"
        plist_path = agents_dir / f"{label}.plist"
        log_out = user_home / ".openclaw" / "gateway.log"
        log_err = user_home / ".openclaw" / "gateway.err.log"

        node_bin = "/opt/homebrew/bin/node"
        if not Path(node_bin).exists():
            node_bin = "/usr/local/bin/node"

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{node_bin}</string>
        <string>{OPENCLAW_INSTALL_DIR}/openclaw.mjs</string>
        <string>gateway</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>15</integer>
    <key>WorkingDirectory</key>
    <string>{OPENCLAW_INSTALL_DIR}</string>
    <key>StandardOutPath</key>
    <string>{log_out}</string>
    <key>StandardErrorPath</key>
    <string>{log_err}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>OPENCLAW_STATE_DIR</key>
        <string>{user_home}/.openclaw</string>
        <key>HOME</key>
        <string>{user_home}</string>
    </dict>
</dict>
</plist>"""

        plist_path.write_text(plist)
        subprocess.run(["chown", f"{user}:", str(plist_path)], check=True)
        console.print(f"  [green]Gateway LaunchAgent written: {plist_path}[/green]")

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
        newsyslog_conf = "/etc/newsyslog.d/openclaw.conf"
        content = "# logfilename          [owner:group]    mode count size when  flags\n"
        content += "/var/log/openclaw/*.log              644  5     1024 *     J\n"
        try:
            Path(newsyslog_conf).write_text(content)
            console.print(f"  Wrote: {newsyslog_conf}")
        except Exception as e:
            console.print(f"  [yellow]Warning: Could not write log rotation config: {e}[/yellow]")

    def _download_voice_models(self):
        """Download local TTS and STT models for fully offline voice."""
        console.print("\n[bold]Downloading voice models...[/bold]")

        model_dir = Path("/opt/openclaw/models")
        subprocess.run(["sudo", "chmod", "755", str(model_dir)], check=True)

        voice_models = [
            ("whisper-large-v3-turbo", "mlx-community/whisper-large-v3-turbo", "STT"),
            ("qwen3_tts", "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit", "TTS"),
        ]

        for i, (local_name, hf_repo, purpose) in enumerate(voice_models, 1):
            dest = model_dir / local_name
            if dest.exists() and any(dest.iterdir()):
                # Ensure config.json has the correct model_type even if already downloaded
                config_path = dest / "config.json"
                if config_path.exists() and local_name == "qwen3_tts":
                    try:
                        with open(config_path, "r") as f:
                            config = json.load(f)
                        if config.get("model_type") != "qwen3_tts":
                            config["model_type"] = "qwen3_tts"
                            with open(config_path, "w") as f:
                                json.dump(config, f, indent=2)
                            console.print(f"  [green]  Fixed model_type in existing {local_name} config.json[/green]")
                    except Exception:
                        pass
                
                console.print(f"  [{i}/{len(voice_models)}] {local_name} ({purpose}) already downloaded")
                continue

            console.print(f"  [{i}/{len(voice_models)}] Downloading {local_name} ({purpose}) <- {hf_repo}")
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id=hf_repo,
                    local_dir=str(dest),
                    local_dir_use_symlinks=False,
                    token=self.hf_token,
                )
                
                # Ensure config.json has the correct model_type for mlx-audio resolution
                config_path = dest / "config.json"
                if config_path.exists():
                    try:
                        with open(config_path, "r") as f:
                            config = json.load(f)
                        if config.get("model_type") != "qwen3_tts" and local_name == "qwen3_tts":
                            config["model_type"] = "qwen3_tts"
                            with open(config_path, "w") as f:
                                json.dump(config, f, indent=2)
                            console.print(f"  [green]  Fixed model_type in {local_name} config.json[/green]")
                    except Exception as e:
                        console.print(f"  [yellow]  Warning: Could not verify/fix config.json for {local_name}: {e}[/yellow]")

                console.print(f"  [green]  {local_name} downloaded successfully[/green]")
            except Exception as e:
                console.print(f"  [red]  Failed to download {local_name}: {e}[/red]")

    def _install_clawhub_skills(self):
        """Install ClawHub CLI and popular community skills."""
        console.print("\n[bold]Installing ClawHub skills...[/bold]")
        user = _real_user()

        # Ensure Homebrew bin is in PATH for npm/npx
        env = os.environ.copy()
        for brew_path in ["/opt/homebrew/bin", "/usr/local/bin"]:
            if os.path.isdir(brew_path) and brew_path not in env.get("PATH", ""):
                env["PATH"] = f"{brew_path}:{env.get('PATH', '')}"

        try:
            subprocess.run(
                ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "npm", "i", "-g", "clawhub"],
                capture_output=True, check=True, timeout=120, stdin=subprocess.DEVNULL,
            )
            console.print("  ClawHub CLI installed globally")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            console.print(f"  [yellow]Warning: Failed to install clawhub CLI: {e}[/yellow]")
            return

        # Resolve the global clawhub binary to avoid npx interactive prompts
        clawhub_bin = None
        for candidate in ["/opt/homebrew/bin/clawhub", "/usr/local/bin/clawhub"]:
            if Path(candidate).exists():
                clawhub_bin = candidate
                break
        if not clawhub_bin:
            try:
                which_result = subprocess.run(
                    ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "which", "clawhub"],
                    capture_output=True, text=True, timeout=10,
                )
                if which_result.returncode == 0:
                    clawhub_bin = which_result.stdout.strip()
            except Exception:
                pass

        if clawhub_bin:
            console.print(f"  Using clawhub binary: {clawhub_bin}")
        else:
            console.print("  [yellow]Global clawhub binary not found, falling back to npx --yes[/yellow]")

        # Authenticate with ClawHub to avoid rate limits
        if self.clawhub_token:
            console.print("  Authenticating with ClawHub...")
            try:
                if clawhub_bin:
                    auth_cmd = ["sudo", "-u", user, "env", f"PATH={env['PATH']}", clawhub_bin, "login", "--token", self.clawhub_token, "--no-browser"]
                else:
                    auth_cmd = ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "npx", "--yes", "clawhub@latest", "login", "--token", self.clawhub_token, "--no-browser"]
                subprocess.run(
                    auth_cmd, capture_output=True, check=True, timeout=30, stdin=subprocess.DEVNULL
                )
                console.print("  [green]ClawHub authentication successful[/green]")
            except Exception as e:
                console.print(f"  [yellow]Warning: ClawHub authentication failed: {e}[/yellow]")

        skills = [
            "self-improving",
            "proactive-agent",
            "gog",
            "clawdbot-documentation-expert",
            "caldav-calendar",
            "agent-browser",
            "whats",
            "byterover",
            "capability-evolver",
            "auto-updater-skill",
            "summarize",
            "humanize-ai-text",
            "find-skills",
            "github",
            "google-search",
            "obsidian",
        ]

        installed_count = 0
        for i, skill in enumerate(skills, 1):
            console.print(f"  [{i}/{len(skills)}] Installing {skill}...")
            try:
                if clawhub_bin:
                    cmd = ["sudo", "-u", user, "env", f"PATH={env['PATH']}", clawhub_bin, "install", skill, "--force"]
                else:
                    cmd = ["sudo", "-u", user, "env", f"PATH={env['PATH']}", "npx", "--yes", "clawhub@latest", "install", skill, "--force"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=300, stdin=subprocess.DEVNULL,
                )
                if result.returncode == 0 or "Already installed" in result.stdout or "Already installed" in result.stderr:
                    installed_count += 1
                    console.print(f"  [green]  {skill} installed[/green]")
                elif "Rate limit exceeded" in result.stdout or "Rate limit exceeded" in result.stderr:
                    console.print(f"  [yellow]  Warning: {skill} failed — Rate limit exceeded. Waiting 60s...[/yellow]")
                    import time
                    time.sleep(60)
                    result = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=300, stdin=subprocess.DEVNULL,
                    )
                    if result.returncode == 0 or "Already installed" in result.stdout or "Already installed" in result.stderr:
                        installed_count += 1
                        console.print(f"  [green]  {skill} installed on retry[/green]")
                    else:
                        stderr_short = (result.stderr or "").strip()[:200]
                        console.print(f"  [yellow]  Warning: {skill} failed on retry — {stderr_short}[/yellow]")
                else:
                    stderr_short = (result.stderr or "").strip()[:200]
                    console.print(f"  [yellow]  Warning: {skill} failed — {stderr_short}[/yellow]")
            except subprocess.TimeoutExpired:
                console.print(f"  [yellow]  Warning: {skill} timed out (5 min), skipping[/yellow]")
            except Exception as e:
                console.print(f"  [yellow]  Warning: {skill} error — {e}[/yellow]")

        console.print(f"  [green]Installed {installed_count}/{len(skills)} ClawHub skills[/green]")

    def _setup_messaging_config(self):
        """Create messaging platform configuration stubs."""
        console.print("\n[bold]Setting up messaging configuration...[/bold]")
        user = _real_user()

        msg_dir = Path("/opt/openclaw/config/messaging")
        msg_dir.mkdir(parents=True, exist_ok=True)

        configs = {
            "whatsapp": {
                "enabled": False, "provider": "twilio",
                "account_sid": "", "auth_token": "",
                "phone_number": "",
            },
            "telegram": {
                "enabled": False, "bot_token": "", "bot_username": "",
            },
            "discord": {
                "enabled": False, "bot_token": "", "guild_id": "",
                "application_id": "",
            },
            "email": {
                "enabled": False, "smtp_host": "", "smtp_port": 587,
                "email": "", "password": "",
            },
        }

        for platform, config in configs.items():
            path = msg_dir / f"{platform}.json"
            if not path.exists():
                path.write_text(json.dumps(config, indent=2))
                console.print(f"  Created: {path}")

        subprocess.run(["chown", "-R", f"{user}:", str(msg_dir)], check=True)
        console.print("  Messaging config stubs created")

    def _write_llm_provider_config(self):
        """Write LLM provider configuration based on order plan type."""
        console.print("\n[bold]Writing LLM provider configuration...[/bold]")

        plan_type = "local_only"
        if self.order_spec:
            if self.order_spec.llm_plan.plan_type == "api_only":
                plan_type = "api_only"
            elif self.order_spec.llm_plan.bundle_id == "max_bundle":
                plan_type = "hybrid"

        config = {
            "offline_mode": plan_type,
            "max_tokens": 4096,
            "default_provider": "mlx" if plan_type != "api_only" else "deepseek",
            "api_keys": {},
            "local_models_path": "/opt/openclaw/models",
        }

        provider_path = Path("/opt/openclaw/state/llm-provider.json")
        provider_path.write_text(json.dumps(config, indent=2))
        console.print(f"  Wrote: {provider_path} (mode: {plan_type})")

    def _first_local_model_id(self) -> str | None:
        """First non-voice model dir under /opt/openclaw/models for Ollama default."""
        if not OPENCLAW_MODELS_PATH.exists():
            return None
        for entry in sorted(OPENCLAW_MODELS_PATH.iterdir()):
            if entry.is_dir() and entry.name not in VOICE_MODEL_DIRS:
                return entry.name
        return None

    def _default_model_from_llm_provider(self, llm_cfg: dict) -> str | None:
        """Return OpenClaw 'provider/model' from llm-provider.json default_provider + api_keys."""
        provider = (llm_cfg.get("default_provider") or llm_cfg.get("provider") or "").strip().lower()
        if not provider:
            return None
        key_map = {
            "deepseek": "deepseek/deepseek-chat",
            "openai": "openai/gpt-4o",
            "anthropic": "anthropic/claude-sonnet-4-5",
            "kimi": "moonshot/kimi-k2.5",
            "glm5": "glm5/glm-4-flash",
        }
        model = key_map.get(provider)
        if model and llm_cfg.get("api_keys", {}).get(provider):
            return model
        return None

    def _write_openclaw_config(self):
        """Write OpenClaw native config (openclaw.json) and .env for the gateway. Re-run safe: merges existing config and .env."""
        console.print("\n[bold]Writing OpenClaw configuration...[/bold]")
        user = _real_user()
        user_home = _real_user_home()
        state_dir = user_home / ".openclaw"
        state_dir.mkdir(parents=True, exist_ok=True)

        gateway_token = secrets.token_hex(32)
        llm_config_path = Path("/opt/openclaw/state/llm-provider.json")
        llm_cfg = {}
        if llm_config_path.exists():
            try:
                llm_cfg = json.loads(llm_config_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        # Base config (gateway, skills)
        config = {
            "gateway": {
                "mode": "local",
                "port": OPENCLAW_GATEWAY_PORT,
                "bind": "loopback",
                "auth": {
                    "mode": "token",
                    "token": gateway_token,
                },
                "http": {
                    "endpoints": {
                        "chatCompletions": {"enabled": True},
                        "responses": {"enabled": True},
                    }
                },
            },
            "skills": {
                "load": {
                    "extraDirs": [
                        "/opt/openclaw/skills/local",
                        "/opt/openclaw/skills/clawhub",
                    ]
                }
            },
            "agents": {
                "defaults": {
                    "workspace": str(user_home / "OpenClawWorkspace"),
                }
            },
        }

        # Re-run safe: preserve or set agents.defaults.model
        config_path = state_dir / "openclaw.json"
        existing_model = None
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
                existing_model = (existing.get("agents") or {}).get("defaults", {}).get("model")
                if isinstance(existing.get("models"), dict) and existing["models"]:
                    config["models"] = existing["models"]
            except (json.JSONDecodeError, OSError):
                pass
        computed_model = self._default_model_from_llm_provider(llm_cfg)
        if computed_model:
            config["agents"]["defaults"]["model"] = computed_model
        elif existing_model:
            config["agents"]["defaults"]["model"] = existing_model
        else:
            # Local MLX fallback: no API key and no default — use first local model via Ollama
            default_provider = (llm_cfg.get("default_provider") or "").strip().lower()
            if default_provider in ("mlx", "local_only", "hybrid") or not llm_cfg.get("api_keys"):
                first_local = self._first_local_model_id()
                if first_local:
                    config["agents"]["defaults"]["model"] = f"ollama/{first_local}"
                    console.print(f"  Default model set to local: ollama/{first_local}")

        config_path.write_text(json.dumps(config, indent=2))
        subprocess.run(["chown", f"{user}:", str(config_path)], check=True)
        console.print(f"  Wrote: {config_path}")

        # Build .env: merge existing .env then overwrite gateway token and API keys from llm-provider
        key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "kimi": "MOONSHOT_API_KEY",
            "glm5": "GLM_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        our_env_keys = {"OPENCLAW_GATEWAY_TOKEN"} | set(key_map.values())
        env_lines = [f"OPENCLAW_GATEWAY_TOKEN={gateway_token}"]
        env_path = state_dir / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text().splitlines():
                    line_stripped = line.strip()
                    if not line_stripped or line_stripped.startswith("#"):
                        env_lines.append(line)
                        continue
                    if "=" in line_stripped:
                        key = line_stripped.split("=", 1)[0].strip()
                        if key not in our_env_keys:
                            env_lines.append(line)
            except (OSError, Exception):
                pass
        api_keys = llm_cfg.get("api_keys", {})
        for provider, env_name in key_map.items():
            val = api_keys.get(provider)
            if val:
                env_lines.append(f"{env_name}={val}")
        env_path.write_text("\n".join(env_lines) + "\n")
        subprocess.run(["chown", f"{user}:", str(env_path)], check=True)
        os.chmod(str(env_path), 0o600)
        console.print(f"  Wrote: {env_path}")

        # Persist gateway token for Mona Hub to read
        token_path = Path("/opt/openclaw/state/gateway-token.txt")
        token_path.write_text(gateway_token)
        os.chmod(str(token_path), 0o600)
        subprocess.run(["chown", f"{user}:", str(token_path)], check=True)
        console.print(f"  Gateway token stored: {token_path}")

        # Legacy Mona-internal config (still read by some Hub endpoints)
        legacy_config = {
            "skills_dir": "/opt/openclaw/skills",
            "clawhub_skills_dir": "/opt/openclaw/skills/clawhub",
            "models_dir": "/opt/openclaw/models",
            "state_dir": "/opt/openclaw/state",
            "workspace": str(user_home / "OpenClawWorkspace"),
            "messaging_config_dir": "/opt/openclaw/config/messaging",
        }
        legacy_path = state_dir / "config.json"
        legacy_path.write_text(json.dumps(legacy_config, indent=2))
        subprocess.run(["chown", f"{user}:", str(legacy_path)], check=True)
        console.print(f"  Wrote legacy config: {legacy_path}")

        subprocess.run(["chown", f"{user}:", str(state_dir)], check=True)

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
        suite_list = ", ".join(s["name"] for s in ALL_TOOL_SUITES)
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
1. Safety Check -> 2. Capability Match -> 3. Tool Routing -> 4. Execution -> 5. Verification

## Available Tool Suites
All {len(ALL_TOOL_SUITES)} tool suites are installed: {suite_list}.
Mona auto-routes user requests to the appropriate tool suite via embedding similarity.
Users may also manually select a tool via slash commands or the tool dropdown.
"""

    def _get_agents_md(self) -> str:
        suite_sections = []
        for suite in ALL_TOOL_SUITES:
            tool_lines = "\n".join(f"  - {t}" for t in suite["tools"])
            suite_sections.append(f"- **{suite['name']}** (`/{suite['id']}`)\n{tool_lines}")
        all_suites_text = "\n".join(suite_sections)

        return f"""# Agent Capabilities & Tool Use

## Tool Auto-Routing
Mona uses embedding-based similarity matching to automatically route user requests
to the most relevant tool suite. Users can override with slash commands (e.g. `/real-estate`)
or the tool dropdown in the chat UI.

## Installed Tool Suites ({len(ALL_TOOL_SUITES)} total)
{all_suites_text}

## Available Tool Categories
### Communication Tools
- send_whatsapp: Business API (Twilio/WhatsApp Business)
- send_telegram: Telegram Bot API (direct messaging)
- send_discord: Discord Bot API (channel and DM messaging)
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
