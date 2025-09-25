# LEAN CLI wrapper for QuantConnect Local Development
# This PowerShell script provides easy access to the LEAN CLI from the project directory

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$LeanPath = "C:\Users\RutiB\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\lean.exe"

# Check if LEAN CLI exists
if (-not (Test-Path $LeanPath)) {
    Write-Error "LEAN CLI not found at expected location: $LeanPath"
    Write-Host "Please ensure LEAN CLI is installed correctly"
    exit 1
}

# Activate virtual environment if it exists
if (Test-Path "QC_VENV\Scripts\Activate.ps1") {
    & "QC_VENV\Scripts\Activate.ps1"
}

# Run LEAN CLI with all passed arguments
& $LeanPath @Arguments

# Note: PowerShell automatically handles environment cleanup when the script exits 