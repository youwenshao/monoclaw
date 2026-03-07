"""macOS environment verification tests."""

import subprocess
import platform
from .base import BaseTestSuite


class MacOSEnvironmentTests(BaseTestSuite):

    def test_macos_version(self):
        version = platform.mac_ver()[0]
        major = int(version.split(".")[0]) if version else 0
        if major >= 15:
            return "pass", {"version": version}
        return "fail", {"version": version, "minimum_required": "15.0"}

    def test_sip_enabled(self):
        result = subprocess.run(
            ["csrutil", "status"],
            capture_output=True, text=True,
        )
        if "enabled" in result.stdout.lower():
            return "pass", {"status": result.stdout.strip()}
        return "fail", {"status": result.stdout.strip()}

    def test_filevault_status(self):
        result = subprocess.run(
            ["fdesetup", "status"],
            capture_output=True, text=True,
        )
        output = result.stdout.strip()
        if "On" in output:
            return "pass", {"status": output}
        return "warning", {"status": output, "note": "FileVault not enabled"}

    def test_firewall_enabled(self):
        result = subprocess.run(
            ["sudo", "/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"],
            capture_output=True, text=True,
        )
        if "enabled" in result.stdout.lower():
            return "pass", {}
        return "warning", {"note": "Firewall may not be enabled"}

    def test_gatekeeper_enabled(self):
        result = subprocess.run(
            ["spctl", "--status"],
            capture_output=True, text=True,
        )
        if "enabled" in result.stdout.lower() or "assessments enabled" in result.stdout.lower():
            return "pass", {}
        return "warning", {"note": "Gatekeeper status unclear"}

    def test_xcode_cli_tools(self):
        result = subprocess.run(
            ["xcode-select", "-p"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "pass", {"path": result.stdout.strip()}
        return "fail", {"error": "Xcode CLI tools not installed"}

    def test_homebrew_installed(self):
        # Try to find brew in typical paths if not in default PATH
        brew_cmd = "brew"
        if subprocess.run(["which", "brew"], capture_output=True).returncode != 0:
            if platform.mac_ver()[0]:
                if platform.machine() == "arm64" and Path("/opt/homebrew/bin/brew").exists():
                    brew_cmd = "/opt/homebrew/bin/brew"
                elif Path("/usr/local/bin/brew").exists():
                    brew_cmd = "/usr/local/bin/brew"

        try:
            result = subprocess.run(
                [brew_cmd, "--version"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return "pass", {"version": result.stdout.strip().split("\n")[0]}
        except FileNotFoundError:
            pass
        return "fail", {"error": "Homebrew not installed"}

    def test_python_version(self):
        result = subprocess.run(
            ["python3", "--version"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            parts = version.replace("Python ", "").split(".")
            if int(parts[0]) >= 3 and int(parts[1]) >= 11:
                return "pass", {"version": version}
            return "fail", {"version": version, "minimum": "3.11"}
        return "fail", {"error": "Python 3 not found"}

    def test_node_installed(self):
        # Try to find node in typical paths if not in default PATH
        node_cmd = "node"
        if subprocess.run(["which", "node"], capture_output=True).returncode != 0:
            if platform.mac_ver()[0]:
                if platform.machine() == "arm64" and Path("/opt/homebrew/bin/node").exists():
                    node_cmd = "/opt/homebrew/bin/node"
                elif Path("/usr/local/bin/node").exists():
                    node_cmd = "/usr/local/bin/node"

        try:
            result = subprocess.run(
                [node_cmd, "--version"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return "pass", {"version": result.stdout.strip()}
        except FileNotFoundError:
            pass
        return "fail", {"error": "Node.js not installed"}

    def test_ffmpeg_installed(self):
        # Try to find ffmpeg in typical Homebrew paths if not in default PATH
        ffmpeg_cmd = "ffmpeg"
        if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
            if platform.mac_ver()[0]:
                if platform.machine() == "arm64" and Path("/opt/homebrew/bin/ffmpeg").exists():
                    ffmpeg_cmd = "/opt/homebrew/bin/ffmpeg"
                elif Path("/usr/local/bin/ffmpeg").exists():
                    ffmpeg_cmd = "/usr/local/bin/ffmpeg"

        try:
            result = subprocess.run(
                [ffmpeg_cmd, "-version"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                return "pass", {"version": result.stdout.strip().split("\n")[0]}
        except FileNotFoundError:
            pass
        return "fail", {"error": "FFmpeg not installed"}
