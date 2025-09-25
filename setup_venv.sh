#!/bin/bash

echo "Creating QuantConnect Virtual Environment..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv QC_VENV

# Activate virtual environment
echo "Activating virtual environment..."
source QC_VENV/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing QuantConnect dependencies..."
pip install -r requirements.txt

echo ""
echo "QuantConnect Virtual Environment setup complete!"
echo ""
echo "To activate the environment, run:"
echo "    source QC_VENV/bin/activate"
echo ""
echo "To deactivate, run:"
echo "    deactivate"
echo "" 