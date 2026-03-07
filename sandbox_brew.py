import os
import subprocess
import sys

def test_brew_install():
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "admin"
    brew_dir = "/tmp/homebrew_test"
    
    print(f"Testing brew install for user {user} in {brew_dir}")
    
    subprocess.run(["mkdir", "-p", brew_dir], check=True)
    subprocess.run(["chown", "-R", f"{user}:staff", brew_dir], check=True)
    
    cmd = f"curl -L https://github.com/Homebrew/brew/tarball/master | tar xz --strip 1 -C {brew_dir}"
    subprocess.run(["sudo", "-u", user, "bash", "-c", cmd], check=True)
    
    # Check if brew works
    res = subprocess.run(["sudo", "-u", user, f"{brew_dir}/bin/brew", "--version"], capture_output=True, text=True)
    print(res.stdout)

if __name__ == "__main__":
    test_brew_install()
