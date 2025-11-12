@echo off
REM Quick start script for Windows

echo ===================================
echo Flask ESP32 MQTT Industrial Control
echo ===================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo [OK] Python found

REM Create venv if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create .env if not exists
if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env
    echo [WARNING] Please edit .env file with your configuration
)

REM Create data directories
if not exist "data\logs" mkdir data\logs
if not exist "data\calibration" mkdir data\calibration
if not exist "data\captured_images" mkdir data\captured_images

REM Start server
echo.
echo Starting Flask server...
python run.py

pause
