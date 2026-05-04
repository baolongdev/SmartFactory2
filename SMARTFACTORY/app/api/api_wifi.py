"""
WiFi API Blueprint - REST endpoints for WiFi management.

This module provides HTTP endpoints for WiFi operations.
Useful for Raspberry Pi deployments where the system needs to
scan and connect to WiFi networks.

Endpoints:
----------
- GET  /api/wifi/scan     : Scan for available WiFi networks
- GET  /api/wifi/status    : Get current WiFi connection status
- POST /api/wifi/connect  : Connect to a WiFi network (requires API key)

Authentication:
---------------
Connect endpoint requires API key if API_KEY is configured:
    Header: X-API-Key: <your_api_key>

Platform Support:
----------------
- Linux (Raspberry Pi): Uses `nmcli` for scanning and connecting
- Windows: Uses `netsh` for scanning, XML profile for secure connections
- Other: Returns 400 Unsupported OS

Usage:
------
    from app.api.api_wifi import api_wifi
    app.register_blueprint(api_wifi)
"""

from flask import Blueprint, jsonify, request
import subprocess
import platform
import os

import structlog

from app.services.wifi_service import scan_wifi, wifi_status

# Module-level logger
logger = structlog.get_logger(__name__)

# Blueprint definition
api_wifi = Blueprint("wifi", __name__, url_prefix="/api/wifi")

# API key from environment (if set, enables authentication)
API_KEY = os.environ.get("API_KEY")


# ---------------------------------------------------------------------------
# Helper: Check API Key
# ---------------------------------------------------------------------------
def check_api_key():
    """
    Check if API key is valid (if API_KEY is configured).

    Returns:
        None if valid (or API_KEY not configured)
        Response if invalid (401 Unauthorized)
    """
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        logger.warning("wifi_api_unauthorized", endpoint=request.path)
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# GET /api/wifi/scan
# ---------------------------------------------------------------------------
@api_wifi.get("/scan")
def api_scan():
    """
    Scan for available WiFi networks.

    Returns:
        {
            "status": "success",
            "wifi_list": [
                {
                    "ssid": string,
                    "bssid": string,
                    "signal": int (0-100),
                    "channel": int,
                    "freq": int,
                    "band": "2.4 GHz"|"5 GHz"|"6 GHz"|"Unknown",
                    "security": string
                },
                ...
            ]
        }
        Error: {"status": "error", "message": string} (500)

    Notes:
        - Uses OS-specific tools (nmcli on Linux, netsh on Windows)
        - Results are merged with cache for stability
        - Scan may take a few seconds on some systems
    """
    try:
        wifi_list = scan_wifi()
        logger.info("wifi_scan_completed", count=len(wifi_list))
        return jsonify({"status": "success", "wifi_list": wifi_list})
    except Exception as e:
        logger.exception("wifi_scan_failed", error_type=type(e).__name__)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/wifi/status
# ---------------------------------------------------------------------------
@api_wifi.get("/status")
def api_status():
    """
    Get current WiFi connection status.

    Returns:
        {
            "status": "success",
            "data": {
                "ssid": string,
                "signal": string,
                "bssid": string,
                "channel": string,
                "freq": int|null,
                "band": string,
                "security": string,
                "device": string
            }
        }
        Error: {"status": "error", "message": string} (500)

    Notes:
        - Returns empty dict if not connected
        - Logs at DEBUG level (noisy if INFO)
    """
    try:
        status = wifi_status()
        logger.debug("wifi_status_requested", connected=bool(status))
        return jsonify({"status": "success", "data": status})
    except Exception as e:
        logger.exception("wifi_status_failed", error_type=type(e).__name__)
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# POST /api/wifi/connect
# ---------------------------------------------------------------------------
@api_wifi.post("/connect")
def api_connect():
    """
    Connect to a WiFi network.

    Headers (if API_KEY is configured):
        X-API-Key: <api_key>

    Request Body:
        {
            "ssid": string,        # Network SSID (required)
            "password": string,    # Network password (required for secure networks)
            "secure": bool         # Is network secure? (default: true)
        }

    Returns:
        Success: {"success": true}
        Error:   {"success": false, "message": string} (400, 401, 500)

    Platform-Specific Behavior:
    ---------------------------
    Linux:
        - Uses `nmcli dev wifi connect` command
        - Password passed as command argument for secure networks

    Windows:
        - For secure networks: Creates WLAN profile XML, then connects
        - For open networks: Direct connect via `netsh wlan connect`
        - Profile XML uses WPA2PSK/AES by default

    Validation:
        - SSID must be a non-empty string
        - Password required for secure networks (handled by OS)

    Security:
        - Password is not logged (redacted by structlog)
        - API key required if configured
        - Profile XML is deleted after use (Windows)
    """
    # Check authentication
    auth_check = check_api_key()
    if auth_check:
        return auth_check

    # Parse request data
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid", "")
    password = data.get("password", "")
    secure = data.get("secure", True)

    # Validate SSID
    if not isinstance(ssid, str) or not ssid.strip():
        logger.warning("wifi_connect_missing_ssid")
        return jsonify({"success": False, "message": "Valid SSID required"}), 400

    # Detect operating system
    os_name = platform.system().lower()

    # ---------------------------------------------------------------------------
    # Linux (Raspberry Pi)
    # ---------------------------------------------------------------------------
    if "linux" in os_name:
        try:
            if secure:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
            else:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]

            subprocess.run(cmd, check=True)
            logger.info("wifi_connected_linux", ssid=ssid, secure=secure)
            return jsonify({"success": True})

        except Exception as e:
            logger.exception("wifi_connect_failed_linux", ssid=ssid, error_type=type(e).__name__)
            return jsonify({"success": False, "message": str(e)}), 500

    # ---------------------------------------------------------------------------
    # Windows
    # ---------------------------------------------------------------------------
    if "windows" in os_name:
        # Secure network: Create WLAN profile XML
        if secure and password:
            import tempfile

            # WLAN profile XML template
            profile_xml = f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID><name>{ssid}</name></SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""

            # Write profile to temporary file
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False)
            tmp.write(profile_xml)
            profile_path = tmp.name
            tmp.close()

            try:
                # Add profile and connect
                subprocess.run(f'netsh wlan add profile filename="{profile_path}"', shell=True, check=True)
                subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True, check=True)
                logger.info("wifi_connected_windows", ssid=ssid, secure=True)
                return jsonify({"success": True})
            except Exception as e:
                logger.error("wifi_connect_failed_windows", ssid=ssid, error=str(e))
                return jsonify({"success": False, "message": str(e)}), 500
            finally:
                # Clean up temporary profile file
                import os as os_mod
                os_mod.unlink(profile_path)

        # Open network: Direct connect
        else:
            try:
                subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True, check=True)
                logger.info("wifi_connected_windows", ssid=ssid, secure=False)
                return jsonify({"success": True})
            except Exception as e:
                logger.error("wifi_connect_failed_windows", ssid=ssid, error=str(e))
                return jsonify({"success": False, "message": str(e)}), 500

    # ---------------------------------------------------------------------------
    # Unsupported OS
    # ---------------------------------------------------------------------------
    logger.warning("wifi_connect_unsupported_os", os=os_name)
    return jsonify({"success": False, "message": "Unsupported OS"}), 400
