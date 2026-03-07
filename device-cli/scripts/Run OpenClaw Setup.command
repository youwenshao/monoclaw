#!/bin/bash
# Double-clickable entry for MonoClaw one-click setup.
# Copy this file to the pendrive volume root (same level as device-cli/), then double-click.
cd "$(dirname "$0")"
exec bash "./device-cli/scripts/run-setup.sh"
