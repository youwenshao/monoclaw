import os
import subprocess

def test_schg():
    test_file = "/tmp/test_schg.txt"
    with open(test_file, "w") as f:
        f.write("test")
    
    # Needs sudo to set schg, but we can test uchg (user immutable) without sudo
    print("Setting uchg...")
    subprocess.run(["chflags", "uchg", test_file], check=True)
    
    print("Trying to modify...")
    try:
        with open(test_file, "w") as f:
            f.write("test2")
    except PermissionError:
        print("Permission denied as expected")
        
    print("Trying to chmod...")
    try:
        subprocess.run(["chmod", "777", test_file], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"chmod failed as expected: {e.stderr.decode()}")
        
    print("Removing uchg...")
    subprocess.run(["chflags", "nouchg", test_file], check=True)
    
    print("Trying to chmod again...")
    subprocess.run(["chmod", "777", test_file], check=True)
    print("Success")

if __name__ == "__main__":
    test_schg()
