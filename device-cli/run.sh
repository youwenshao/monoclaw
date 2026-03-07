#!/usr/bin/env bash
# Invoke the one-click setup script. Run from device-cli/ or from volume root as ./device-cli/run.sh
cd "$(dirname "$0")"
exec bash "./scripts/run-setup.sh"
