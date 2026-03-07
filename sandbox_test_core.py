import subprocess
import os
from pathlib import Path

def test_core_files():
    print("Checking /etc/openclaw/core")
    res = subprocess.run(["ls", "-la", "/etc/openclaw/core"], capture_output=True, text=True)
    print(res.stdout)
    print(res.stderr)
    
    print("\nChecking file modes")
    for f in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
        path = Path("/etc/openclaw/core") / f
        if path.exists():
            print(f"{f}: {oct(path.stat().st_mode)[-3:]}")
            
    print("\nChecking schg flag")
    for f in ["SOUL.md", "AGENTS.md", "TOOLS.md"]:
        path = Path("/etc/openclaw/core") / f
        if path.exists():
            res = subprocess.run(["ls", "-lO", str(path)], capture_output=True, text=True)
            print(f"{f}: {res.stdout.strip()}")

if __name__ == "__main__":
    test_core_files()
