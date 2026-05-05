#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SmartFactory WiFi Fallback — One-Time Setup
#
# Must run as root:  sudo bash scripts/setup_wifi_fallback.sh
#
# What this does:
#   1. Installs NetworkManager (nmcli) if missing
#   2. Writes /etc/sf-wifi-fallback.env  (editable config)
#   3. Copies wifi_fallback.sh → /usr/local/bin/sf-wifi-fallback
#   4. Creates   /etc/systemd/system/sf-wifi-fallback.service
#   5. Enables + starts the service
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Guard: must be root ───────────────────────────────────────────────────────
if [[ "$EUID" -ne 0 ]]; then
    echo "Error: run as root — sudo bash $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_SRC="$SCRIPT_DIR/wifi_fallback.sh"
DAEMON_DEST="/usr/local/bin/sf-wifi-fallback"
SERVICE_NAME="sf-wifi-fallback"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
ENV_FILE="/etc/${SERVICE_NAME}.env"

# ── Detect wireless interface ─────────────────────────────────────────────────
detect_iface() {
    local iface
    iface=$(iw dev 2>/dev/null | awk '$1=="Interface"{print $2; exit}')
    echo "${iface:-wlan0}"
}

echo "══════════════════════════════════════════════════"
echo "  SmartFactory WiFi Fallback Setup"
echo "══════════════════════════════════════════════════"

# ── [1] Dependencies ──────────────────────────────────────────────────────────
echo "[1/5] Checking dependencies..."
PKG_MISSING=0
for pkg in nmcli iw; do
    if ! command -v "$pkg" > /dev/null 2>&1; then
        PKG_MISSING=1
        break
    fi
done

if [[ $PKG_MISSING -eq 1 ]]; then
    echo "      Installing: network-manager wireless-tools iw..."
    apt-get update -qq
    apt-get install -y -qq network-manager wireless-tools iw
    systemctl enable NetworkManager
    systemctl start  NetworkManager
    sleep 2
    echo "      NetworkManager installed and started"
else
    echo "      All dependencies present"
fi

# ── [2] Write config env file ─────────────────────────────────────────────────
DETECTED_IFACE=$(detect_iface)
echo "[2/5] Writing config to $ENV_FILE (detected iface: $DETECTED_IFACE)..."

cat > "$ENV_FILE" <<ENVEOF
# SmartFactory WiFi Fallback — Configuration
# Edit then restart: sudo systemctl restart ${SERVICE_NAME}

# WiFi interface (run 'iw dev' to list interfaces)
SF_AP_IFACE=$DETECTED_IFACE

# Hotspot credentials
SF_AP_SSID=SmartFactory-AP
SF_AP_PASSWORD=smartfactory2025

# Connectivity check target
SF_CHECK_HOST=8.8.8.8

# Check interval in seconds
SF_CHECK_INTERVAL=15
ENVEOF

chmod 600 "$ENV_FILE"
echo "      Written: $ENV_FILE"

# ── [3] Install daemon ────────────────────────────────────────────────────────
echo "[3/5] Installing daemon to $DAEMON_DEST..."
if [[ ! -f "$DAEMON_SRC" ]]; then
    echo "      ERROR: $DAEMON_SRC not found"
    exit 1
fi
cp "$DAEMON_SRC" "$DAEMON_DEST"
chmod +x "$DAEMON_DEST"
echo "      Installed: $DAEMON_DEST"

# ── [4] Create systemd service ────────────────────────────────────────────────
echo "[4/5] Creating systemd service..."
cat > "$SERVICE_FILE" <<SVCEOF
[Unit]
Description=SmartFactory WiFi Fallback AP Daemon
Documentation=https://github.com/your-repo/SmartFactory
After=network.target NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
EnvironmentFile=-$ENV_FILE
ExecStart=$DAEMON_DEST
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SVCEOF

echo "      Service file: $SERVICE_FILE"

# ── [5] Enable + start ────────────────────────────────────────────────────────
echo "[5/5] Enabling and starting service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

# Brief wait then show status
sleep 2
echo ""
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "      Service is running  ✓"
else
    echo "      WARNING: Service may not be running — check logs below"
fi

echo ""
echo "══════════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Useful commands:"
echo "    Status : sudo systemctl status  ${SERVICE_NAME}"
echo "    Logs   : sudo journalctl -u ${SERVICE_NAME} -f"
echo "    Config : sudo nano $ENV_FILE"
echo "    Restart: sudo systemctl restart ${SERVICE_NAME}"
echo ""
echo "  When offline, connect to:"
echo "    WiFi SSID : SmartFactory-AP"
echo "    Password  : smartfactory2025"
echo "    Browser   : http://10.42.0.1:5000/wifi"
echo "══════════════════════════════════════════════════"
