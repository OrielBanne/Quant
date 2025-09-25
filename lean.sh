#!/bin/bash

# LEAN CLI wrapper for QuantConnect Local Development
# This Bash script provides easy access to the LEAN CLI from the project directory

# LEAN CLI path for Windows
LEAN_PATH="/c/Users/RutiB/AppData/Local/Packages/PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0/LocalCache/local-packages/Python311/Scripts/lean.exe"

# Check if LEAN CLI exists
if [ ! -f "$LEAN_PATH" ]; then
    echo "Error: LEAN CLI not found at expected location"
    echo "Expected: $LEAN_PATH"
    echo ""
    echo "Please ensure LEAN CLI is installed correctly"
    exit 1
fi

# Activate virtual environment if it exists
if [ -f "QC_VENV/Scripts/activate" ]; then
    source QC_VENV/Scripts/activate
fi

# Run LEAN CLI with all passed arguments
"$LEAN_PATH" "$@"

# Note: Bash automatically handles environment cleanup when the script exits 