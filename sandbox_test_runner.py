import subprocess
import os

script = """#!/bin/bash
export PATH="/opt/homebrew/bin:$PATH"
python3 -c "import os; import subprocess; print(subprocess.run(['which', 'brew'], capture_output=True, text=True).stdout)"
"""
with open("test_script.sh", "w") as f:
    f.write(script)
os.chmod("test_script.sh", 0o755)

res = subprocess.run(["bash", "./test_script.sh"], capture_output=True, text=True)
print("Output:", res.stdout)
