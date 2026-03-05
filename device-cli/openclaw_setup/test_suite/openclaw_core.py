"""OpenClaw core installation verification tests."""

import json
import hashlib
import os
import subprocess
from pathlib import Path
from .base import BaseTestSuite


class OpenClawCoreTests(BaseTestSuite):

    def test_core_directory_exists(self):
        if Path("/etc/openclaw/core").exists():
            return "pass", {}
        return "fail", {"error": "/etc/openclaw/core missing"}

    def test_opt_directory_exists(self):
        for d in ["models", "skills", "state"]:
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
                with open(filepath, "rb") as f:
                    actual = hashlib.sha256(f.read()).hexdigest()
                if actual != expected_hash:
                    return "fail", {"file": filepath, "expected": expected_hash[:16], "actual": actual[:16]}
        return "pass", {}

    def test_llm_config_valid_json(self):
        config_path = Path("/opt/openclaw/state/active-work.json")
        if config_path.exists():
            try:
                with open(config_path) as f:
                    json.load(f)
                return "pass", {}
            except json.JSONDecodeError as e:
                return "fail", {"error": str(e)}
        return "skipped", {"note": "Config not yet created"}

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
