"""macOS system configuration integration."""

import subprocess
from typing import List

from backend.models.onboarding_state import SystemInfo, InstalledTool, InstalledModel


def get_system_info() -> SystemInfo:
    """Get basic system information."""
    try:
        # Get computer name
        result = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True, check=True)
        computer_name = result.stdout.strip()
        
        # Get appearance (dark/light)
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"], 
            capture_output=True, text=True
        )
        appearance = "dark" if "Dark" in result.stdout else "light"
        
        return SystemInfo(
            computer_name=computer_name,
            appearance=appearance,
            version="15.0",  # macOS Sequoia
            hardware="Apple Silicon"
        )
    except Exception:
        return SystemInfo(
            computer_name="Mona Mac",
            appearance="light",
            version="Unknown",
            hardware="Unknown"
        )


def set_computer_name(name: str) -> bool:
    """Set the macOS computer name."""
    try:
        # Note: This usually requires sudo, so it might fail if run as normal user
        # We'll just try it and return false if it fails
        subprocess.run(["scutil", "--set", "ComputerName", name], capture_output=True, check=True)
        subprocess.run(["scutil", "--set", "LocalHostName", name.replace(" ", "-")], capture_output=True, check=True)
        return True
    except Exception:
        return False


def set_appearance(mode: str) -> bool:
    """Set macOS appearance to dark or light."""
    try:
        script = f'tell application "System Events" to tell appearance preferences to set dark mode to {"true" if mode == "dark" else "false"}'
        subprocess.run(["osascript", "-e", script], capture_output=True, check=True)
        return True
    except Exception:
        return False


def open_system_settings(panel: str) -> bool:
    """Open a specific macOS System Settings panel."""
    try:
        # Map simple names to preference pane IDs
        panels = {
            "privacy": "x-apple.systempreferences:com.apple.preference.security?Privacy",
            "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            "general": "x-apple.systempreferences:com.apple.SystemPreferences",
        }
        url = panels.get(panel, "x-apple.systempreferences:com.apple.SystemPreferences")
        subprocess.run(["open", url], capture_output=True, check=True)
        return True
    except Exception:
        return False


def get_installed_tools() -> List[InstalledTool]:
    """Return a list of installed ClawHub/local tools."""
    # Stub implementation
    return [
        InstalledTool(id="run_shell", name="Shell Access", description="Execute terminal commands", type="local", enabled=True),
        InstalledTool(id="file_operations", name="File Operations", description="Read and write files", type="local", enabled=True),
    ]


def get_installed_models() -> List[InstalledModel]:
    """Return a list of downloaded LLM models."""
    # Stub implementation
    return [
        InstalledModel(id="qwen2.5-7b-instruct", name="Qwen 2.5 7B", size="4.5GB", status="ready", is_active=True),
    ]
