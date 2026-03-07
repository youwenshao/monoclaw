import os
import subprocess
from pathlib import Path

def test_finalize_fix():
    # 1. Setup mock environment
    opt_dir = Path("/tmp/opt_openclaw_mock")
    cred_file = opt_dir / ".setup-credentials"
    
    # Create dir as root (simulated)
    subprocess.run(["sudo", "mkdir", "-p", str(opt_dir)], check=True)
    
    # Create file and chown to current user (as provisioner does)
    user = os.environ.get("USER")
    subprocess.run(["sudo", "touch", str(cred_file)], check=True)
    subprocess.run(["sudo", "chown", user, str(cred_file)], check=True)
    
    print(f"Mock setup: {cred_file} exists, owned by {user}")
    print(f"Parent dir {opt_dir} owned by root")

    # 2. Try to delete WITHOUT sudo (this is what fails currently)
    print("\nAttempting deletion WITHOUT sudo...")
    try:
        cred_file.unlink()
        print("Success (unexpected)")
    except PermissionError as e:
        print(f"Caught expected error: {e}")

    # 3. Try to delete WITH sudo (the fix)
    print("\nAttempting deletion WITH sudo...")
    try:
        subprocess.run(["sudo", "rm", "-f", str(cred_file)], check=True)
        if not cred_file.exists():
            print("Success! File removed via sudo.")
        else:
            print("Failure: File still exists.")
    except Exception as e:
        print(f"Error during sudo rm: {e}")

    # Cleanup mock dir
    subprocess.run(["sudo", "rm", "-rf", str(opt_dir)], check=True)

if __name__ == "__main__":
    test_finalize_fix()
