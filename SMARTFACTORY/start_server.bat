@echo off
chcp 65001 >nul
cls

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   SMARTFACTORY  ·  Smart Factory Control  v1.0.0    ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM ────────────────────────────────────────────────────────────
REM [1/7] Check Python
REM ────────────────────────────────────────────────────────────
echo  [1/7] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [X] Python not found.
    echo      Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo  [OK] %PYTHON_VER%
echo.

REM ────────────────────────────────────────────────────────────
REM [2/7] Virtual Environment
REM ────────────────────────────────────────────────────────────
echo  [2/7] Setting up virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo  Creating venv...
    python -m venv venv
    if errorlevel 1 (
        echo  [X] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo  [OK] venv created
) else (
    echo  [OK] venv exists
)
echo.

REM ────────────────────────────────────────────────────────────
REM [3/7] Activate
REM ────────────────────────────────────────────────────────────
echo  [3/7] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo  [X] Failed to activate virtual environment
    pause
    exit /b 1
)
echo  [OK] venv activated
echo.

REM ────────────────────────────────────────────────────────────
REM [4/7] Upgrade pip
REM ────────────────────────────────────────────────────────────
echo  [4/7] Upgrading pip...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo  [OK] pip ready
echo.

REM ────────────────────────────────────────────────────────────
REM [5/7] Install Dependencies
REM ────────────────────────────────────────────────────────────
echo  [5/7] Installing dependencies...
echo  (First run may take several minutes)
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [X] Failed to install dependencies
    pause
    exit /b 1
)
echo  [OK] Dependencies installed
echo.

REM ────────────────────────────────────────────────────────────
REM [6/7] .env Configuration
REM ────────────────────────────────────────────────────────────
echo  [6/7] Checking .env configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo  [OK] .env created from .env.example
    ) else (
        (
            echo FLASK_ENV=development
            echo FLASK_HOST=0.0.0.0
            echo FLASK_PORT=5000
            echo LOG_LEVEL=INFO
            echo LOG_FORMAT=console
            echo ENVIRONMENT=development
            echo SERVICE_NAME=SmartFactory2
            echo MQTT_SERVER=mqtt.ohstem.vn
            echo MQTT_PORT=1883
        ) > .env
        echo  [OK] .env created with defaults
    )
    echo  [!] Please review .env with your MQTT settings
) else (
    echo  [OK] .env exists
)
echo.

REM ────────────────────────────────────────────────────────────
REM [7/7] Data Directories
REM ────────────────────────────────────────────────────────────
echo  [7/7] Creating data directories...
if not exist "data\logs"            mkdir data\logs
if not exist "data\calibration"     mkdir data\calibration
if not exist "data\captured_images" mkdir data\captured_images
echo  [OK] Directories ready
echo.

REM ────────────────────────────────────────────────────────────
REM Read values from .env for display
REM ────────────────────────────────────────────────────────────
set FLASK_ENV=development
set FLASK_HOST=0.0.0.0
set FLASK_PORT=5000

for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if /i "%%a"=="FLASK_ENV"  set FLASK_ENV=%%b
    if /i "%%a"=="FLASK_HOST" set FLASK_HOST=%%b
    if /i "%%a"=="FLASK_PORT" set FLASK_PORT=%%b
)

REM ────────────────────────────────────────────────────────────
REM Startup Info
REM ────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   Starting SmartFactory Server...
echo  ╠══════════════════════════════════════════════════════╣
echo  ║   URL    :  http://localhost:%FLASK_PORT%
echo  ║   WiFi   :  http://localhost:%FLASK_PORT%/wifi
echo  ║   Env    :  %FLASK_ENV%
echo  ║   Logs   :  Structured ^(structlog^)
echo  ╚══════════════════════════════════════════════════════╝
echo.

REM ────────────────────────────────────────────────────────────
REM Launch
REM ────────────────────────────────────────────────────────────
set PYTHONIOENCODING=utf-8
python run.py

if errorlevel 1 (
    echo.
    echo  [X] Server stopped with errors. Check logs above.
    pause
    exit /b 1
)

pause
