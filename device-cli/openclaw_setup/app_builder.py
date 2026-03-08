"""Builds the Mona.app macOS bundle, registers a LaunchAgent, and launches the Hub."""

import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from rich.console import Console

console = Console()

MONA_HUB_PATH = Path("/opt/openclaw/mona_hub")
APP_BUNDLE_PATH = Path("/Applications/Mona.app")
LAUNCH_AGENT_LABEL = "com.monoclaw.monahub"
BUNDLE_IDENTIFIER = "com.monoclaw.mona"
SERVER_PORT = 8000
SERVER_HOST = "127.0.0.1"
BROWSER_URL = f"http://127.0.0.1:{SERVER_PORT}"


def _real_user() -> str:
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"


def _real_user_home() -> Path:
    return Path(f"/Users/{_real_user()}")


def _real_user_uid() -> int:
    import pwd
    return pwd.getpwnam(_real_user()).pw_uid


class MonaAppBuilder:
    """Builds Mona.app, registers a LaunchAgent, and launches the Hub server."""

    def __init__(self):
        self.user = _real_user()
        self.user_home = _real_user_home()
        self.python_bin = sys.executable
        self.openclaw_dir = self.user_home / ".openclaw"
        self.openclaw_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["chown", f"{self.user}:", str(self.openclaw_dir)], check=True)

    def build_and_launch(self):
        """Full pipeline: build app, register agent, start server, open browser."""
        console.print("\n[bold]Building Mona.app and launching Hub...[/bold]")

        self._build_app_bundle()
        self._write_launch_agent()
        self._write_wrapper_scripts()
        self._launch_server()
        self._wait_and_open_browser()

        console.print("[green]Mona Hub is running and ready for onboarding.[/green]")

    # -- App bundle -----------------------------------------------------------

    def _build_app_bundle(self):
        console.print("  Building /Applications/Mona.app...")

        contents = APP_BUNDLE_PATH / "Contents"
        macos_dir = contents / "MacOS"
        resources = contents / "Resources"

        for d in (macos_dir, resources):
            d.mkdir(parents=True, exist_ok=True)

        self._write_info_plist(contents / "Info.plist")
        self._write_executable(macos_dir / "Mona")
        self._write_placeholder_icon(resources)

        subprocess.run(["chown", "-R", f"{self.user}:", str(APP_BUNDLE_PATH)], check=True)
        console.print("  [green]Mona.app created[/green]")

    def _write_info_plist(self, path: Path):
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Mona</string>
    <key>CFBundleDisplayName</key>
    <string>Mona</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_IDENTIFIER}</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>Mona</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>15.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>"""
        path.write_text(plist)

    def _write_executable(self, path: Path):
        """Shell script that opens the Hub in the browser (starting the server if needed)."""
        script = f"""#!/bin/bash
# Mona — opens Mona Hub in the default browser, starting the server if needed.
PORT={SERVER_PORT}
HOST="127.0.0.1"

if ! /usr/bin/curl -sf "http://$HOST:$PORT/api/onboarding/state" >/dev/null 2>&1; then
    /bin/launchctl start {LAUNCH_AGENT_LABEL}
    for i in $(seq 1 30); do
        sleep 1
        if /usr/bin/curl -sf "http://$HOST:$PORT/api/onboarding/state" >/dev/null 2>&1; then
            break
        fi
    done
fi

/usr/bin/open "http://$HOST:$PORT"
"""
        path.write_text(script)
        path.chmod(0o755)

    def _write_placeholder_icon(self, resources_dir: Path):
        """Generate a minimal placeholder .icns via sips + iconutil."""
        iconset_dir = None
        try:
            iconset_dir = Path(tempfile.mkdtemp(suffix=".iconset"))
            png_data = _generate_placeholder_png(1024, 1024)

            base_png = iconset_dir / "icon_512x512@2x.png"
            base_png.write_bytes(png_data)

            sizes = [16, 32, 64, 128, 256, 512]
            for s in sizes:
                name = f"icon_{s}x{s}.png"
                dest = iconset_dir / name
                subprocess.run(
                    ["sips", "-z", str(s), str(s), str(base_png), "--out", str(dest)],
                    capture_output=True, check=True,
                )
                if s >= 32:
                    retina_name = f"icon_{s // 2}x{s // 2}@2x.png"
                    retina_dest = iconset_dir / retina_name
                    if not retina_dest.exists():
                        subprocess.run(
                            ["sips", "-z", str(s), str(s), str(base_png), "--out", str(retina_dest)],
                            capture_output=True, check=True,
                        )

            icns_path = resources_dir / "AppIcon.icns"
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
                capture_output=True, check=True,
            )
            console.print("  [green]Placeholder icon created[/green]")
        except Exception as e:
            console.print(f"  [yellow]Icon generation skipped ({e}); macOS will use default icon[/yellow]")
        finally:
            if iconset_dir and iconset_dir.exists():
                import shutil
                shutil.rmtree(iconset_dir, ignore_errors=True)

    # -- LaunchAgent ----------------------------------------------------------

    def _write_launch_agent(self):
        console.print("  Registering LaunchAgent...")

        agents_dir = self.user_home / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        plist_path = agents_dir / f"{LAUNCH_AGENT_LABEL}.plist"
        wrapper = self.openclaw_dir / "start_mona_hub.sh"

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{wrapper}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>{MONA_HUB_PATH}</string>
    <key>StandardOutPath</key>
    <string>{self.user_home}/.openclaw/monahub.log</string>
    <key>StandardErrorPath</key>
    <string>{self.user_home}/.openclaw/monahub.err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>"""

        plist_path.write_text(plist)
        subprocess.run(["chown", f"{self.user}:", str(plist_path)], check=True)
        console.print(f"  [green]LaunchAgent written: {plist_path}[/green]")

    def _write_wrapper_scripts(self):
        console.print("  Writing wrapper scripts...")

        onboarding_state = "/opt/openclaw/state/onboarding.json"

        start_script = self.openclaw_dir / "start_mona_hub.sh"
        start_script.write_text(f"""#!/bin/bash
# Mona Hub launcher — starts the server and opens the browser if onboarding is pending.
# Called by launchd (via LaunchAgent) on login, or directly during initial setup.
ONBOARDING_STATE="{onboarding_state}"
PORT={SERVER_PORT}
HOST={SERVER_HOST}
BROWSER_HOST="127.0.0.1"

# If the server is already running (e.g. from the initial finalize launch),
# wait for it to exit before taking over.  This prevents a port conflict
# between the manually-started process and the launchd-managed one.
while /usr/bin/lsof -i :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
    sleep 10
done

open_browser_if_needed() {{
    sleep 5
    COMPLETED="false"
    if [ -f "$ONBOARDING_STATE" ]; then
        COMPLETED=$({self.python_bin} -c "import json; print(json.load(open('$ONBOARDING_STATE')).get('onboarding_completed', False))" 2>/dev/null || echo "false")
    fi
    if [ "$COMPLETED" != "True" ]; then
        /usr/bin/open "http://$BROWSER_HOST:$PORT"
    fi
}}

open_browser_if_needed &

cd {MONA_HUB_PATH} && exec {self.python_bin} -m uvicorn backend.main:app --host $HOST --port $PORT
""")
        start_script.chmod(0o755)
        subprocess.run(["chown", f"{self.user}:", str(start_script)], check=True)

        console.print("  [green]Wrapper scripts written[/green]")

    # -- Launch ---------------------------------------------------------------

    def _launch_server(self):
        """Start the Mona Hub server directly as a detached process.

        We cannot use launchctl bootstrap/load here because the finalize step
        runs under sudo, which places us in the root bootstrap domain — not the
        user's gui/<uid> domain.  The LaunchAgent plist is already written to
        ~/Library/LaunchAgents/ and will be picked up automatically on the
        user's next login (RunAtLoad + KeepAlive).
        """
        console.print("  Starting Mona Hub server...")

        log_path = self.user_home / ".openclaw" / "monahub.log"
        err_path = self.user_home / ".openclaw" / "monahub.err.log"

        subprocess.Popen(
            [
                "sudo", "-u", self.user, "bash", "-c",
                f"cd {MONA_HUB_PATH} && "
                f"nohup {self.python_bin} -m uvicorn backend.main:app "
                f"--host {SERVER_HOST} --port {SERVER_PORT} "
                f">> '{log_path}' 2>> '{err_path}' &"
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        console.print("  [green]Server process started[/green]")

    def _wait_and_open_browser(self):
        """Poll the server until it responds, then open the browser."""
        console.print("  Waiting for server to become ready...")

        url = f"http://127.0.0.1:{SERVER_PORT}/api/onboarding/state"
        for attempt in range(1, 31):
            try:
                req = urllib.request.urlopen(url, timeout=2)
                if req.status == 200:
                    console.print(f"  [green]Server ready (attempt {attempt})[/green]")
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            console.print("  [yellow]Server did not respond in 30s; opening browser anyway[/yellow]")
            err_log = self.user_home / ".openclaw" / "monahub.err.log"
            if err_log.exists():
                tail = err_log.read_text()[-500:]
                console.print(f"  [red]Server error log tail:[/red]\n{tail}")

        subprocess.run(
            ["sudo", "-u", self.user, "open", f"http://127.0.0.1:{SERVER_PORT}"],
            capture_output=True,
        )
        console.print("  [green]Browser opened to onboarding page[/green]")


# -- Placeholder PNG generation (no external deps) ---------------------------

def _generate_placeholder_png(width: int, height: int) -> bytes:
    """Create a minimal valid PNG with a solid teal (#0D9488) fill."""

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        import zlib
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    import zlib

    r, g, b = 0x0D, 0x94, 0x88
    raw_rows = []
    row_bytes = bytes([r, g, b] * width)
    for _ in range(height):
        raw_rows.append(b"\x00" + row_bytes)  # filter byte 0 (None) per row

    compressed = zlib.compress(b"".join(raw_rows))

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")

    return signature + ihdr + idat + iend
