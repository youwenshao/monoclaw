#!/bin/bash
export PATH="/opt/homebrew/bin:$PATH"
python3 -c "import os; import subprocess; print(subprocess.run(['which', 'brew'], capture_output=True, text=True).stdout)"
