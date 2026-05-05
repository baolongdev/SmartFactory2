#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SmartFactory WiFi Fallback Daemon
#
# Monitors internet connectivity every $SF_CHECK_INTERVAL seconds.
# - Offline  → start nmcli WiFi hotspot so a technician can connect and
#              use http://<AP-IP>:5000/wifi to configure the target WiFi.
# - Online   → stop the hotspot, wait for wlan0 DHCP, write the new IP
#              to /tmp/sf-wifi-ip and log it.
#
# Run directly:  bash wifi_fallback.sh
# Run as daemon: managed by sf-wifi-fallback.service (see setup script)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration (overridable via environment / EnvironmentFile) ─────────────
AP_SSID="${SF_AP_SSID:-SmartFactory-AP}"
AP_PASSWORD="${SF_AP_PASSWORD:-smartfactory2025}"
AP_IFACE="${SF_AP_IFACE:-wlan0}"
AP_CON_NAME="sf-fallback-ap"
CHECK_HOST="${SF_CHECK_HOST:-8.8.8.8}"
CHECK_INTERVAL="${SF_CHECK_INTERVAL:-15}"
IP_FILE="/tmp/sf-wifi-ip"
LOG_TAG="sf-wifi-fallback"

# ── Logging ───────────────────────────────────────────────────────────────────
log() { logger -t "$LOG_TAG" "$*" 2>/dev/null || true; echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── State ─────────────────────────────────────────────────────────────────────
ap_active=false

# ── Helpers ───────────────────────────────────────────────────────────────────
is_online() {
    ping -c 1 -W 3 "$CHECK_HOST" > /dev/null 2>&1
}

get_device_ip() {
    local ip
    ip=$(ip -4 addr show "$AP_IFACE" 2>/dev/null \
         | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' | head -1 || true)
    # AP gateway is typically 10.42.0.1; skip it
    if [[ "$ip" == 10.42.* ]]; then ip=""; fi
    if [ -z "$ip" ]; then
        ip=$(ip -4 addr show eth0 2>/dev/null \
             | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' | head -1 || true)
    fi
    echo "$ip"
}

# ── Start hotspot ─────────────────────────────────────────────────────────────
start_ap() {
    if $ap_active; then return 0; fi
    log "No internet detected — starting fallback AP (SSID: $AP_SSID)..."

    # Remove any stale connection with the same name
    nmcli connection delete "$AP_CON_NAME" > /dev/null 2>&1 || true

    if nmcli device wifi hotspot \
           ifname    "$AP_IFACE" \
           ssid      "$AP_SSID" \
           password  "$AP_PASSWORD" \
           con-name  "$AP_CON_NAME" > /dev/null 2>&1; then

        ap_active=true
        local ap_ip
        ap_ip=$(ip -4 addr show "$AP_IFACE" 2>/dev/null \
                | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' | head -1 || echo "10.42.0.1")
        log "AP ready — SSID: '$AP_SSID'  Password: '$AP_PASSWORD'"
        log "Access SmartFactory at: http://$ap_ip:5000/wifi"
    else
        log "ERROR: Failed to start AP — check nmcli / NetworkManager"
    fi
}

# ── Stop hotspot ──────────────────────────────────────────────────────────────
stop_ap() {
    if ! $ap_active; then return 0; fi
    log "Internet restored — stopping AP..."

    nmcli connection down   "$AP_CON_NAME" > /dev/null 2>&1 || true
    nmcli connection delete "$AP_CON_NAME" > /dev/null 2>&1 || true
    ap_active=false

    # Give DHCP time to assign an address on the real WiFi
    sleep 5

    local new_ip
    new_ip=$(get_device_ip)

    if [ -n "$new_ip" ]; then
        echo "$new_ip" > "$IP_FILE"
        log "Connected! Device IP: $new_ip"
        log "SmartFactory now accessible at: http://$new_ip:5000"
    else
        log "WARNING: Could not determine new IP after AP shutdown"
        rm -f "$IP_FILE"
    fi
}

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
    log "Daemon stopping — tearing down AP if active..."
    nmcli connection down   "$AP_CON_NAME" > /dev/null 2>&1 || true
    nmcli connection delete "$AP_CON_NAME" > /dev/null 2>&1 || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# ── Main loop ─────────────────────────────────────────────────────────────────
log "SmartFactory WiFi Fallback daemon started (interval: ${CHECK_INTERVAL}s, iface: $AP_IFACE)"

while true; do
    if is_online; then
        stop_ap
    else
        start_ap
    fi
    sleep "$CHECK_INTERVAL"
done
