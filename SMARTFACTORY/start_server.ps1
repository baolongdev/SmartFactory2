# start_server.ps1 - Windows PowerShell Startup Script
# Smart Factory Control System v1.0.0
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File start_server.ps1

# Change to script directory
Set-Location -Path $PSScriptRoot

# ────────────────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────────────────
function Write-Step  { param([string]$s) Write-Host " $s" -ForegroundColor DarkGray }
function Write-OK    { param([string]$s) Write-Host "  [OK] $s" -ForegroundColor Green }
function Write-Warn  { param([string]$s) Write-Host "  [!]  $s" -ForegroundColor Yellow }
function Write-Fail  { param([string]$s) Write-Host "  [X]  $s" -ForegroundColor Red }

function Read-EnvValue {
    param(
        [string]$Key,
        [string]$Default = ""
    )
    if (-not (Test-Path ".env")) { return $Default }

    $match = Get-Content ".env" -ErrorAction SilentlyContinue |
             Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=\s*(.+)$" } |
             Select-Object -First 1

    if ($match -and $match -match "=\s*(.+)$") {
        return $Matches[1].Trim()
    }
    return $Default
}

function Pause-Exit {
    param([int]$Code = 1)
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit $Code
}

# ────────────────────────────────────────────────────────────
# Banner
# ────────────────────────────────────────────────────────────
Clear-Host
Write-Host ""
Write-Host " ╔══════════════════════════════════════════════════════╗" -ForegroundColor DarkGray
Write-Host " ║   SMARTFACTORY  ·  Smart Factory Control  v1.0.0    ║" -ForegroundColor White
Write-Host " ╚══════════════════════════════════════════════════════╝" -ForegroundColor DarkGray
Write-Host ""

# ────────────────────────────────────────────────────────────
# [1/7] Python
# ────────────────────────────────────────────────────────────
Write-Step "[1/7] Checking Python..."

$pythonCheck = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Python not found."
    Write-Host "      Download: https://www.python.org/downloads/"
    Pause-Exit
}
Write-OK "$pythonCheck"
Write-Host ""

# ────────────────────────────────────────────────────────────
# [2/7] Virtual Environment
# ────────────────────────────────────────────────────────────
Write-Step "[2/7] Setting up virtual environment..."

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "  Creating venv..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create virtual environment"
        Pause-Exit
    }
    Write-OK "venv created"
} else {
    Write-OK "venv exists"
}
Write-Host ""

# ────────────────────────────────────────────────────────────
# [3/7] Activate (set PATH directly — avoids ExecutionPolicy issues)
# ────────────────────────────────────────────────────────────
Write-Step "[3/7] Activating virtual environment..."

$env:VIRTUAL_ENV = "$PWD\venv"
$env:PATH        = "$env:VIRTUAL_ENV\Scripts;$env:PATH"
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue

Write-OK "venv activated"
Write-Host ""

# ────────────────────────────────────────────────────────────
# [4/7] Upgrade pip
# ────────────────────────────────────────────────────────────
Write-Step "[4/7] Upgrading pip..."

python -m pip install --upgrade pip setuptools wheel *>$null
Write-OK "pip ready"
Write-Host ""

# ────────────────────────────────────────────────────────────
# [5/7] Install Dependencies
# ────────────────────────────────────────────────────────────
Write-Step "[5/7] Installing dependencies..."
Write-Host "  (First run may take several minutes)"
Write-Host ""

pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Failed to install dependencies"
    Pause-Exit
}
Write-OK "Dependencies installed"
Write-Host ""

# ────────────────────────────────────────────────────────────
# [6/7] .env Configuration
# ────────────────────────────────────────────────────────────
Write-Step "[6/7] Checking .env configuration..."

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-OK ".env created from .env.example"
    } else {
        @"
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
LOG_LEVEL=INFO
LOG_FORMAT=console
ENVIRONMENT=development
SERVICE_NAME=SmartFactory2
MQTT_SERVER=mqtt.ohstem.vn
MQTT_PORT=1883
"@ | Set-Content ".env" -Encoding UTF8
        Write-OK ".env created with defaults"
    }
    Write-Warn "Please review .env with your MQTT/WiFi settings"
} else {
    Write-OK ".env exists"
}
Write-Host ""

# ────────────────────────────────────────────────────────────
# [7/7] Data Directories
# ────────────────────────────────────────────────────────────
Write-Step "[7/7] Creating data directories..."

@("data\logs", "data\calibration", "data\captured_images") | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -Path $_ -ItemType Directory -Force | Out-Null
    }
}
Write-OK "Directories ready"
Write-Host ""

# ────────────────────────────────────────────────────────────
# Read .env values for display
# ────────────────────────────────────────────────────────────
$flaskEnv  = Read-EnvValue "FLASK_ENV"  "development"
$flaskHost = Read-EnvValue "FLASK_HOST" "0.0.0.0"
$flaskPort = Read-EnvValue "FLASK_PORT" "5000"

# ────────────────────────────────────────────────────────────
# Startup Info
# ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host " ╔══════════════════════════════════════════════════════╗" -ForegroundColor DarkGray
Write-Host " ║   Starting SmartFactory Server..." -ForegroundColor White
Write-Host " ╠══════════════════════════════════════════════════════╣" -ForegroundColor DarkGray
Write-Host " ║   URL    :  " -NoNewline -ForegroundColor DarkGray
Write-Host "http://localhost:$flaskPort" -ForegroundColor Cyan
Write-Host " ║   WiFi   :  " -NoNewline -ForegroundColor DarkGray
Write-Host "http://localhost:$flaskPort/wifi" -ForegroundColor Cyan
Write-Host " ║   Env    :  $flaskEnv" -ForegroundColor DarkGray
Write-Host " ║   Host   :  $flaskHost" -ForegroundColor DarkGray
Write-Host " ║   Logs   :  Structured (structlog)" -ForegroundColor DarkGray
Write-Host " ╚══════════════════════════════════════════════════════╝" -ForegroundColor DarkGray
Write-Host ""

# ────────────────────────────────────────────────────────────
# Launch
# ────────────────────────────────────────────────────────────
$env:PYTHONIOENCODING = "utf-8"
python run.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Fail "Server stopped with errors. Check logs above."
    Pause-Exit
}
