# QuantConnect Local Development Environment

This repository contains a complete setup for QuantConnect local development with all necessary dependencies and tools.

## Quick Start

### Windows
```bash
# Run the setup script
setup_venv.bat
```

### Linux/Mac
```bash
# Make the script executable
chmod +x setup_venv.sh

# Run the setup script
./setup_venv.sh
```

## Manual Setup

If you prefer to set up the environment manually:

1. **Create Virtual Environment**
   ```bash
   python -m venv QC_VENV
   ```

2. **Activate Virtual Environment**
   - Windows: `QC_VENV\Scripts\activate.bat`
   - Linux/Mac: `source QC_VENV/bin/activate`

3. **Install Dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Environment Management

### Activating the Environment
- **Windows**: `QC_VENV\Scripts\activate.bat`
- **Linux/Mac**: `source QC_VENV/bin/activate`

### Deactivating the Environment
```bash
deactivate
```

### Updating Dependencies
```bash
pip install -r requirements.txt --upgrade
```

## Using the LEAN CLI

The QuantConnect LEAN CLI is available through convenient wrapper scripts:

### Initial Setup (First Time Only)
```bash
# Configure default language (Python recommended)
.\lean.bat config set default-language python

# Verify configuration
.\lean.bat config get default-language
```

### Windows (Batch)
```bash
# Check LEAN version
.\lean.bat --version

# Get help
.\lean.bat --help

# Create a new project
.\lean.bat project-create MyAlgorithm

# Initialize LEAN configuration
.\lean.bat init

# Run backtest
.\lean.bat backtest MyAlgorithm
```

### Windows (PowerShell)
```bash
# Check LEAN version
.\lean.ps1 --version

# Get help
.\lean.ps1 --help

# Create a new project
.\lean.ps1 project-create MyAlgorithm

# Initialize LEAN configuration
.\lean.ps1 init

# Run backtest
.\lean.ps1 backtest MyAlgorithm
```

### Git Bash / Unix-like Terminals
```bash
# Make executable (first time only)
chmod +x lean

# Configure default language (first time only)
./lean config set default-language python

# Check LEAN version
./lean --version

# Get help
./lean --help

# Create a new project
./lean project-create MyAlgorithm

# Initialize LEAN configuration
./lean init

# Run backtest
./lean backtest MyAlgorithm
```

### Common LEAN Commands
- `project-create <name>` - Create a new algorithm project
- `init` - Initialize LEAN configuration and data directory
- `backtest <project>` - Run a backtest locally
- `research` - Start Jupyter Lab environment
- `live <project>` - Run algorithm live
- `data download` - Download market data
- `login` - Log in to QuantConnect account

## Included Packages

### Core QuantConnect
- `quantconnect-lean`: QuantConnect LEAN engine
- `quantconnect-research`: QuantConnect research environment

### Data Analysis
- `pandas`: Data manipulation and analysis
- `numpy`: Numerical computing
- `matplotlib`: Plotting and visualization
- `seaborn`: Statistical data visualization
- `plotly`: Interactive plotting

### Financial Data
- `yfinance`: Yahoo Finance data
- `alpha-vantage`: Alpha Vantage API
- `ta-lib`: Technical analysis library

### Machine Learning (Optional)
- `scikit-learn`: Machine learning algorithms
- `tensorflow`: Deep learning framework
- `torch`: PyTorch deep learning

### Development Tools
- `jupyter`: Jupyter notebooks
- `ipykernel`: IPython kernel
- `black`: Code formatting
- `flake8`: Code linting
- `pytest`: Testing framework

### Additional utilities
- `requests`: HTTP library
- `python-dotenv`: Environment variable management
- `tqdm`: Progress bars

## Project Structure

```
QuantConnectLocal/
├── QC_VENV/                 # Virtual environment (created after setup)
├── requirements.txt         # Python dependencies
├── setup_venv.bat          # Windows setup script
├── setup_venv.sh           # Unix/Linux setup script
├── lean.bat                # LEAN CLI wrapper (Windows batch)
├── lean.ps1                # LEAN CLI wrapper (PowerShell)
├── lean.sh                 # LEAN CLI wrapper (Bash)
├── lean                    # LEAN CLI wrapper (executable, no extension)
├── test_environment.py     # Environment verification script
├── quick_start_example.ipynb # Jupyter notebook with examples
├── .gitignore              # Git ignore file
└── README.md               # This file
```

## Getting Started with QuantConnect

1. **Activate your environment**
2. **Start Jupyter Notebook**
   ```bash
   jupyter notebook
   ```

3. **Create your first algorithm**
   ```python
   from quantconnect import *
   
   class MyFirstAlgorithm(QCAlgorithm):
       def Initialize(self):
           self.SetStartDate(2020, 1, 1)
           self.SetCash(100000)
           self.AddEquity("SPY")
       
       def OnData(self, data):
           if not self.Portfolio.Invested:
               self.SetHoldings("SPY", 1)
   ```

## Troubleshooting

### Common Issues

1. **Python not found**: Ensure Python 3.8+ is installed and in your PATH
2. **Permission errors**: Run setup scripts as administrator (Windows) or with sudo (Linux)
3. **Package installation failures**: Try updating pip first: `pip install --upgrade pip`

### TA-Lib Installation Issues

If you encounter issues installing TA-Lib:

**Windows:**
```bash
pip install TA-Lib --index-url https://pypi.org/simple/
```

**Linux:**
```bash
# Install system dependencies first
sudo apt-get install ta-lib
pip install TA-Lib
```

**Mac:**
```bash
brew install ta-lib
pip install TA-Lib
```

### LEAN CLI Issues

If the LEAN CLI wrapper scripts don't work:

1. **Check the path**: Ensure the LEAN CLI is installed at the expected location
2. **Reinstall LEAN**: `pip install --upgrade lean`
3. **Use full path**: Use the full path to the LEAN executable if needed
4. **Git Bash users**: Make sure to use `./lean` instead of `.\lean.bat`

## Support

For QuantConnect-specific issues, visit:
- [QuantConnect Documentation](https://www.quantconnect.com/docs)
- [QuantConnect Forum](https://www.quantconnect.com/forum)

## License

This project is for educational and development purposes. Please refer to QuantConnect's terms of service for commercial usage. 