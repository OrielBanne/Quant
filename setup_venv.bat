@echo off
echo Creating QuantConnect Virtual Environment...

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv QC_VENV

REM Activate virtual environment
echo Activating virtual environment...
call QC_VENV\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing QuantConnect dependencies...
pip install -r requirements.txt

echo.
echo QuantConnect Virtual Environment setup complete!
echo.
echo To activate the environment, run:
echo     QC_VENV\Scripts\activate.bat
echo.
echo To deactivate, run:
echo     deactivate
echo.
pause 