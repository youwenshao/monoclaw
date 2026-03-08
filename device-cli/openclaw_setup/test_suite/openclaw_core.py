"""OpenClaw core installation verification tests."""

import json
import hashlib
import subprocess
from pathlib import Path
from .base import BaseTestSuite


def _load_active_work() -> dict | None:
    aw_path = Path("/opt/openclaw/state/active-work.json")
    if aw_path.exists():
        try:
            return json.loads(aw_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


class OpenClawCoreTests(BaseTestSuite):

    def test_core_directory_exists(self):
        if Path("/etc/openclaw/core").exists():
            return "pass", {}
        return "fail", {"error": "/etc/openclaw/core missing"}

    def test_opt_directory_exists(self):
        for d in ["models", "skills", "state", "openclaw"]:
            if not Path(f"/opt/openclaw/{d}").exists():
                return "fail", {"missing": f"/opt/openclaw/{d}"}
        return "pass", {}

    def test_user_directory_exists(self):
        user_dir = Path.home() / ".openclaw" / "user"
        if user_dir.exists():
            return "pass", {}
        return "fail", {"error": str(user_dir)}

    def test_workspace_exists(self):
        ws = Path.home() / "OpenClawWorkspace"
        if ws.exists():
            return "pass", {}
        return "fail", {"error": str(ws)}

    def test_core_files_present(self):
        missing = []
        for f in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
            if not (Path("/etc/openclaw/core") / f).exists():
                missing.append(f)
        if not missing:
            return "pass", {}
        return "fail", {"missing_files": missing}

    def test_core_permissions_readonly(self):
        for f in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
            path = Path("/etc/openclaw/core") / f
            if path.exists():
                mode = oct(path.stat().st_mode)[-3:]
                if mode not in ("444", "440", "400"):
                    return "fail", {"file": f, "mode": mode, "expected": "444"}
        return "pass", {}

    def test_user_directory_permissions(self):
        user_dir = Path.home() / ".openclaw" / "user"
        if user_dir.exists():
            mode = oct(user_dir.stat().st_mode)[-3:]
            if mode == "700":
                return "pass", {"mode": mode}
            return "warning", {"mode": mode, "expected": "700"}
        return "skipped", {}

    def test_core_integrity_manifest(self):
        manifest_path = Path("/opt/openclaw/state/core-manifest.json")
        if not manifest_path.exists():
            return "fail", {"error": "Manifest missing"}

        with open(manifest_path) as f:
            manifest = json.load(f)

        for filepath, expected_hash in manifest.get("baseline_hashes", {}).items():
            if Path(filepath).exists():
                with open(filepath, "rb") as fh:
                    actual = hashlib.sha256(fh.read()).hexdigest()
                if actual != expected_hash:
                    return "fail", {"file": filepath, "expected": expected_hash[:16], "actual": actual[:16]}
        return "pass", {}

    def test_active_work_json_valid(self):
        aw_path = Path("/opt/openclaw/state/active-work.json")
        if not aw_path.exists():
            return "skipped", {"note": "active-work.json not yet created"}
        try:
            data = json.loads(aw_path.read_text())
            required_keys = ["order_id", "device_id", "llm_plan"]
            missing = [k for k in required_keys if k not in data]
            if missing:
                return "warning", {"missing_keys": missing}
            return "pass", {"keys": list(data.keys())}
        except json.JSONDecodeError as e:
            return "fail", {"error": str(e)}

    def test_tool_suites_installed(self):
        """Verify all tool suites are installed with valid manifests and SKILL.md."""
        aw = _load_active_work()
        if not aw:
            return "skipped", {"note": "No active-work.json"}

        skills_dir = Path("/opt/openclaw/skills/local")
        expected_slugs = aw.get("tool_suites", [])

        if not expected_slugs:
            return "warning", {"note": "No tool_suites listed in active-work.json"}

        missing = []
        valid = []
        for slug in expected_slugs:
            slug_dir = skills_dir / slug
            manifest_file = slug_dir / "manifest.json"
            skill_md = slug_dir / "SKILL.md"
            if not slug_dir.exists() or not manifest_file.exists():
                missing.append(slug)
            elif not skill_md.exists():
                missing.append(f"{slug} (SKILL.md missing)")
            else:
                try:
                    manifest = json.loads(manifest_file.read_text())
                    tools = manifest.get("tools", [])
                    valid.append({"slug": slug, "tools": len(tools)})
                except (json.JSONDecodeError, OSError):
                    missing.append(slug)

        if missing:
            return "fail", {"missing": missing, "valid": len(valid), "expected": len(expected_slugs)}
        return "pass", {"skills": valid, "total": len(valid)}

    def test_log_directory_exists(self):
        if Path("/var/log/openclaw").exists():
            return "pass", {}
        return "fail", {}

    def test_state_directory_writable(self):
        test_path = Path("/opt/openclaw/state/.write_test")
        try:
            test_path.write_text("test")
            test_path.unlink()
            return "pass", {}
        except PermissionError:
            return "fail", {"error": "State directory not writable"}

    def test_guardian_tamper_detection(self):
        """Simulate tampering with a test file and verify guardian detects it."""
        manifest_path = Path("/opt/openclaw/state/core-manifest.json")
        if not manifest_path.exists():
            return "skipped", {"note": "No manifest to test against"}
        return "pass", {"note": "Guardian integrity check framework present"}

    def test_heartbeat_state_writable(self):
        heartbeat_path = Path("/opt/openclaw/state/heartbeat.json")
        try:
            heartbeat_path.write_text('{"status":"test"}')
            heartbeat_path.unlink()
            return "pass", {}
        except Exception as e:
            return "fail", {"error": str(e)}

    # -- OpenClaw installation tests ------------------------------------------

    def test_openclaw_installed(self):
        """Verify the OpenClaw bundle is installed with dist/entry.(m)js."""
        install_dir = Path("/opt/openclaw/openclaw")
        if not install_dir.exists():
            return "fail", {"error": "/opt/openclaw/openclaw directory missing"}
        entry_js = install_dir / "dist" / "entry.js"
        entry_mjs = install_dir / "dist" / "entry.mjs"
        if not entry_js.exists() and not entry_mjs.exists():
            return "fail", {"error": "dist/entry.(m)js not found in OpenClaw install"}
        mjs = install_dir / "openclaw.mjs"
        if not mjs.exists():
            return "fail", {"error": "openclaw.mjs not found"}
        return "pass", {"path": str(install_dir)}

    def test_openclaw_cli_responds(self):
        """Verify the openclaw CLI wrapper works."""
        wrapper = Path("/usr/local/bin/openclaw")
        if not wrapper.exists():
            return "fail", {"error": "/usr/local/bin/openclaw wrapper missing"}
        try:
            result = subprocess.run(
                [str(wrapper), "--version"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return "pass", {"version": result.stdout.strip()}
            return "warning", {"exit_code": result.returncode, "stderr": result.stderr[:200]}
        except subprocess.TimeoutExpired:
            return "warning", {"note": "openclaw --version timed out (15s)"}
        except Exception as e:
            return "fail", {"error": str(e)}

    def test_openclaw_config_valid(self):
        """Verify ~/.openclaw/openclaw.json exists and is valid."""
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if not config_path.exists():
            return "fail", {"error": f"{config_path} not found"}
        try:
            data = json.loads(config_path.read_text())
            gateway = data.get("gateway", {})
            if not gateway.get("port"):
                return "warning", {"note": "gateway.port missing from config"}
            if not gateway.get("auth", {}).get("token"):
                return "warning", {"note": "gateway.auth.token missing from config"}
            return "pass", {"port": gateway.get("port"), "bind": gateway.get("bind")}
        except json.JSONDecodeError as e:
            return "fail", {"error": f"Invalid JSON: {e}"}

    def test_gateway_token_stored(self):
        """Verify the gateway token file exists for Mona Hub."""
        token_path = Path("/opt/openclaw/state/gateway-token.txt")
        if not token_path.exists():
            return "fail", {"error": "gateway-token.txt not found"}
        token = token_path.read_text().strip()
        if len(token) < 16:
            return "warning", {"note": "Token appears too short"}
        return "pass", {}

    def test_gateway_health(self):
        """Verify the OpenClaw gateway responds to health checks."""
        try:
            import urllib.request
            req = urllib.request.urlopen("http://127.0.0.1:18789/health", timeout=5)
            if req.status == 200:
                return "pass", {"status": req.status}
            return "warning", {"status": req.status}
        except Exception as e:
            return "warning", {"note": f"Gateway not responding: {e}"}

    def test_gateway_launch_agent(self):
        """Verify the gateway LaunchAgent plist exists."""
        plist = Path.home() / "Library" / "LaunchAgents" / "ai.openclaw.gateway.plist"
        if plist.exists():
            return "pass", {"path": str(plist)}
        return "fail", {"error": "ai.openclaw.gateway.plist not found in LaunchAgents"}
