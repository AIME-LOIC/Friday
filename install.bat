@echo off
REM Quick installation script for Personal Voice Assistant (Windows)

echo ======================================
echo Personal Voice Assistant - Setup
echo ======================================
echo.

REM Check Python version
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.7+
    pause
    exit /b 1
)
echo OK

REM Get current directory
cd /d "%~dp0"
echo Working directory: %cd%

REM Create virtual environment (optional)
set /p CREATE_VENV="Create virtual environment? (y/n): "
if /i "%CREATE_VENV%"=="y" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo OK
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ======================================
echo OK - Setup complete!
echo ======================================
echo.
echo To start the Voice Assistant, run:
echo   python main.py
echo.
echo For advanced version with more features:
echo   python advanced.py
echo.
echo To run tests and diagnostics:
echo   python setup.py
echo.
pause
