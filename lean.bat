@echo off
REM LEAN CLI wrapper for QuantConnect Local Development
REM This batch file provides easy access to the LEAN CLI from the project directory

set LEAN_PATH=C:\Users\RutiB\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\lean.exe

REM Check if LEAN CLI exists
if not exist "%LEAN_PATH%" (
    echo Error: LEAN CLI not found at expected location
    echo Expected: %LEAN_PATH%
    echo.
    echo Please ensure LEAN CLI is installed correctly
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "QC_VENV\Scripts\activate.bat" (
    call QC_VENV\Scripts\activate.bat
)

REM Run LEAN CLI with all passed arguments
"%LEAN_PATH%" %*

REM Deactivate virtual environment
if defined VIRTUAL_ENV (
    deactivate
) 