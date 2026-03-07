import subprocess
import os

def test_brew_path():
    # The test runs as the real user, but does not have the updated PATH from the provisioner
    # because the provisioner runs in a separate process.
    # The test script uses subprocess.run(["brew", "--version"]) which relies on brew being in PATH.
    
    # Let's see what PATH is in a normal subprocess
    res = subprocess.run(["echo", "$PATH"], capture_output=True, text=True, shell=True)
    print("Default PATH:", res.stdout.strip())
    
    # Try to run brew
    res = subprocess.run(["brew", "--version"], capture_output=True, text=True)
    print("Brew run result:", res.returncode, res.stdout, res.stderr)

if __name__ == "__main__":
    try:
        test_brew_path()
    except Exception as e:
        print("Error:", e)
