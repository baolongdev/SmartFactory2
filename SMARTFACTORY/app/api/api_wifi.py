from flask import Blueprint, jsonify, request
import subprocess
import platform
import traceback
import re

api_wifi = Blueprint("wifi", __name__, url_prefix="/api/wifi")

# ==============================
# CACHE GIỮ 10 LẦN SCAN
# ==============================
wifi_cache = {}
SCAN_LIMIT = 10


# ======================================================
# PARSE BAND
# ======================================================
def freq_to_band(freq_mhz):
    try:
        f = int(freq_mhz)
    except:
        return "Unknown"

    if 2400 <= f <= 2500:
        return "2.4 GHz"
    if 5170 <= f <= 5895:
        return "5 GHz"
    if 5925 <= f <= 7125:
        return "6 GHz"
    return "Unknown"


# ======================================================
# SCAN WIFI LINUX (nmcli)
# ======================================================
def scan_wifi_linux_raw():
    try:
        result = subprocess.check_output(
            ["nmcli", "-t", "-f", "SSID,SECURITY,BSSID,FREQ,SIGNAL,CHAN",
             "dev", "wifi", "--rescan", "yes"],
            text=True
        )

        wifi_list = []
        for line in result.split("\n"):
            if not line.strip():
                continue

            parts = line.split(":")
            if len(parts) < 6:
                continue

            wifi_list.append({
                "ssid": parts[0].strip(),
                "secure": bool(parts[1].strip()),
                "bssid": parts[2].strip(),
                "freq": parts[3].strip(),
                "band": freq_to_band(parts[3].strip()),
                "signal": int(parts[4].strip()),
                "channel": parts[5].strip()
            })

        return wifi_list

    except Exception as e:
        print("[SCAN LINUX ERROR]", e)
        return []


# ======================================================
# SCAN WIFI WINDOWS
# ======================================================
def scan_wifi_windows_raw():
    try:
        subprocess.run("netsh wlan refresh networks", shell=True)
        result = subprocess.check_output(
            "netsh wlan show networks mode=bssid",
            shell=True,
            text=True
        )

        wifi_list = []
        ssid = ""
        secure = True
        bssid = ""
        signal = "0"
        channel = ""
        freq = "2400"

        for line in result.split("\n"):
            line = line.strip()

            if line.startswith("SSID "):
                ssid = line.split(":", 1)[1].strip()

            if "Authentication" in line:
                secure = line.split(":", 1)[1].strip().lower() != "open"

            if "BSSID" in line:
                m = re.search(r"BSSID \d+\s*:\s*([0-9A-Fa-f:-]+)", line)
                if m:
                    bssid = m.group(1)

            if "Signal" in line:
                signal = line.split(":", 1)[1].strip().replace("%", "")

            if "Channel" in line:
                channel = line.split(":", 1)[1].strip()

            if "Radio type" in line:
                if any(x in line for x in ["802.11a", "802.11n", "802.11ac"]):
                    freq = "5200"
                else:
                    freq = "2400"

            # End block
            if line == "" and ssid:
                wifi_list.append({
                    "ssid": ssid,
                    "secure": secure,
                    "bssid": bssid,
                    "freq": freq,
                    "band": freq_to_band(freq),
                    "signal": int(signal),
                    "channel": channel
                })
                ssid = ""

        return wifi_list

    except Exception as e:
        print("[SCAN WIN ERROR]", e)
        return []


# ======================================================
# MERGE CACHE
# ======================================================
def merge_with_cache(raw_list):
    global wifi_cache

    seen = set()

    for ap in raw_list:
        ssid = ap["ssid"]
        if not ssid:
            continue

        seen.add(ssid)

        if ssid not in wifi_cache:
            wifi_cache[ssid] = {"data": ap, "missing": 0}
        else:
            wifi_cache[ssid]["data"] = ap
            wifi_cache[ssid]["missing"] = 0

    # tăng missing
    for ssid in list(wifi_cache.keys()):
        if ssid not in seen:
            wifi_cache[ssid]["missing"] += 1

            if wifi_cache[ssid]["missing"] >= SCAN_LIMIT:
                del wifi_cache[ssid]

    return [wifi_cache[k]["data"] for k in wifi_cache]


# ======================================================
# STATUS LINUX
# ======================================================
def wifi_status_linux():
    try:
        result = subprocess.check_output(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,BSSID,CHAN,DEVICE", "dev", "wifi"],
            text=True
        )

        for line in result.split("\n"):
            if line.startswith("yes"):
                parts = line.split(":")
                return {
                    "ssid": parts[1],
                    "signal": parts[2],
                    "bssid": parts[3],
                    "channel": parts[4],
                    "device": parts[5]
                }

        return {}

    except Exception as e:
        print("[STATUS LINUX ERROR]", e)
        return {}


# ======================================================
# STATUS WINDOWS
# ======================================================
def wifi_status_windows():
    try:
        result = subprocess.check_output(
            "netsh wlan show interfaces",
            shell=True,
            text=True
        )

        data = {"ssid": "", "signal": "", "bssid": "", "channel": "", "device": ""}

        for line in result.split("\n"):
            line = line.strip()

            if line.startswith("SSID"):
                data["ssid"] = line.split(":", 1)[1].strip()

            if line.startswith("Signal"):
                data["signal"] = line.split(":", 1)[1].strip()

            if line.startswith("BSSID"):
                data["bssid"] = line.split(":", 1)[1].strip()

            if line.startswith("Channel"):
                data["channel"] = line.split(":", 1)[1].strip()

            if line.startswith("Name"):
                data["device"] = line.split(":", 1)[1].strip()

        return data

    except Exception as e:
        print("[STATUS WIN ERROR]", e)
        return {}


# ======================================================
# API: /scan
# ======================================================
@api_wifi.get("/scan")
def scan_wifi():
    os = platform.system().lower()

    if "linux" in os:
        raw = scan_wifi_linux_raw()
    else:
        raw = scan_wifi_windows_raw()

    return jsonify({"wifi_list": merge_with_cache(raw)})


# ======================================================
# API: /status
# ======================================================
@api_wifi.get("/status")
def wifi_status():
    os = platform.system().lower()

    if "linux" in os:
        return jsonify(wifi_status_linux())
    else:
        return jsonify(wifi_status_windows())


# ======================================================
# API: /connect
# ======================================================
@api_wifi.post("/connect")
def connect_wifi():
    data = request.get_json(silent=True) or {}

    ssid = data.get("ssid", "").strip()
    password = data.get("password", "").strip()
    secure = data.get("secure", True)

    if not ssid:
        return jsonify({"success": False, "message": "SSID missing"}), 400

    os = platform.system().lower()

    # Linux
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
    if not secure:
        subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True)
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Unsupported"}), 400
