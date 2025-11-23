from flask import Blueprint, jsonify, request
import subprocess
import platform
import traceback

from app.services.wifi_service import scan_wifi, wifi_status

api_wifi = Blueprint("wifi", __name__, url_prefix="/api/wifi")


# ======================================================
# API: /scan
# ======================================================
@api_wifi.get("/scan")
def api_scan():
    return jsonify({"wifi_list": scan_wifi()})


# ======================================================
# API: /status
# ======================================================
@api_wifi.get("/status")
def api_status():
    return jsonify(wifi_status())


# ======================================================
# API: /connect
# ======================================================
@api_wifi.post("/connect")
def api_connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid", "")
    password = data.get("password", "")
    secure = data.get("secure", True)

    if not ssid:
        return jsonify({"success": False, "message": "SSID missing"}), 400

    os = platform.system().lower()

    if "linux" in os:
        try:
            if secure:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
            else:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]

            subprocess.run(cmd, check=True)
            return jsonify({"success": True})

        except Exception as e:
            traceback.print_exc()
            return jsonify({"success": False, "message": str(e)}), 500

    # Windows
    if "windows" in os:
        subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True)
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Unsupported OS"}), 400
