#!/bin/bash
# ===================================================
#  SMARTFACTORY - Linux / Raspberry Pi Startup Script
#  Smart Factory Control System v1.0.0
# ===================================================

# Change to script directory
cd "$(dirname "${BASH_SOURCE[0]}")"

# ────────────────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────────────────
ok()   { echo "  [OK] $*"; }
fail() { echo "  [X]  $*" >&2; exit 1; }
warn() { echo "  [!]  $*"; }

# Read a key=value from .env file
read_env() {
    local key="$1"
    local default="${2:-}"
    if [ -f ".env" ]; then
        local val
        val=$(grep -m1 "^${key}=" .env 2>/dev/null | cut -d= -f2-)
        echo "${val:-$default}"
    else
        echo "$default"
    fi
}

# ────────────────────────────────────────────────────────────
# Banner
# ────────────────────────────────────────────────────────────
echo ""
echo " ╔══════════════════════════════════════════════════════╗"
echo " ║   SMARTFACTORY  ·  Smart Factory Control  v1.0.0    ║"
echo " ╚══════════════════════════════════════════════════════╝"
echo ""

# ────────────────────────────────────────────────────────────
# [1/7] Python
# ────────────────────────────────────────────────────────────
echo " [1/7] Checking Python..."

if ! command -v python3 &>/dev/null; then
    fail "Python 3 not found. Install: sudo apt install python3 python3-pip python3-venv"
fi

PYTHON_VER=$(python3 --version 2>&1)
ok "$PYTHON_VER"
echo ""

# ────────────────────────────────────────────────────────────
# [2/7] Virtual Environment
# ────────────────────────────────────────────────────────────
echo " [2/7] Setting up virtual environment..."

VENV_DIR="venv"

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "  Creating venv..."
    python3 -m venv "$VENV_DIR" || fail "Failed to create virtual environment"
    ok "venv created"
else
    ok "venv exists"
fi
echo ""

# ────────────────────────────────────────────────────────────
# [3/7] Activate
# ────────────────────────────────────────────────────────────
echo " [3/7] Activating virtual environment..."

source "$VENV_DIR/bin/activate" || fail "Failed to activate virtual environment"
ok "venv activated ($(python --version 2>&1))"
echo ""

# ────────────────────────────────────────────────────────────
# [4/7] Upgrade pip
# ────────────────────────────────────────────────────────────
echo " [4/7] Upgrading pip..."

pip install --upgrade pip setuptools wheel -q 2>&1 || warn "pip upgrade failed (continuing)"
ok "pip ready"
echo ""

# ────────────────────────────────────────────────────────────
# [5/7] Install Dependencies
# ────────────────────────────────────────────────────────────
echo " [5/7] Installing dependencies..."
echo "  (First run may take several minutes)"
echo ""

# Detect ARM / Raspberry Pi
ARM_DETECTED=false
if [ -f /proc/cpuinfo ]; then
    if grep -qi "bcm\|raspberry\|rpi" /proc/cpuinfo 2>/dev/null; then
        ARM_DETECTED=true
    fi
fi

if [ "$ARM_DETECTED" = true ]; then
    warn "ARM/Raspberry Pi detected — using piwheels for prebuilt OpenCV"
    pip install -r requirements.txt \
        --extra-index-url https://www.piwheels.org/simple \
        || fail "Failed to install dependencies"
else
    pip install -r requirements.txt || fail "Failed to install dependencies"
fi

ok "Dependencies installed"
echo ""

# ────────────────────────────────────────────────────────────
# [6/7] .env Configuration
# ────────────────────────────────────────────────────────────
echo " [6/7] Checking .env configuration..."

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        ok ".env created from .env.example"
    else
        cat > .env << 'EOF'
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
LOG_LEVEL=INFO
LOG_FORMAT=console
ENVIRONMENT=development
SERVICE_NAME=SmartFactory2
MQTT_SERVER=mqtt.ohstem.vn
MQTT_PORT=1883
EOF
        ok ".env created with defaults"
    fi
    warn "Please review .env with your MQTT/WiFi settings"
else
    ok ".env exists"
fi
echo ""

# ────────────────────────────────────────────────────────────
# [7/7] Data Directories
# ────────────────────────────────────────────────────────────
echo " [7/7] Creating data directories..."

mkdir -p data/logs data/calibration data/captured_images
ok "Directories ready"
echo ""

# ────────────────────────────────────────────────────────────
# Read .env values for display
# ────────────────────────────────────────────────────────────
FLASK_ENV=$(read_env "FLASK_ENV"  "development")
FLASK_HOST=$(read_env "FLASK_HOST" "0.0.0.0")
FLASK_PORT=$(read_env "FLASK_PORT" "5000")

# ────────────────────────────────────────────────────────────
# Startup Info
# ────────────────────────────────────────────────────────────
echo " ╔══════════════════════════════════════════════════════╗"
echo " ║   Starting SmartFactory Server..."
echo " ╠══════════════════════════════════════════════════════╣"
echo " ║   URL    :  http://localhost:${FLASK_PORT}"
echo " ║   WiFi   :  http://localhost:${FLASK_PORT}/wifi"
echo " ║   Env    :  ${FLASK_ENV}"
echo " ║   Host   :  ${FLASK_HOST}"
echo " ║   Logs   :  Structured (structlog)"
echo " ╚══════════════════════════════════════════════════════╝"
echo ""

# ────────────────────────────────────────────────────────────
# Launch
# ────────────────────────────────────────────────────────────
export PYTHONIOENCODING=utf-8

python run.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    fail "Server stopped with errors (exit code $EXIT_CODE). Check logs above."
fi
