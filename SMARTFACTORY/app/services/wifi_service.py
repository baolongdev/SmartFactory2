import subprocess
import platform
import re

# ======================================================
# WIFI CACHE
# ======================================================
wifi_cache = {}
SCAN_LIMIT = 10  # mất 10 lần scan liên tiếp thì xoá khỏi list


# ======================================================
# COMMON HELPERS
# ======================================================
def channel_to_freq(ch):
    if ch is None:
        return None
    ch = int(ch)

    # 2.4 GHz
    if 1 <= ch <= 13:
        return 2412 + (ch - 1) * 5

    # 5 GHz
    if 36 <= ch <= 165:
        return ch * 5 + 5000

    # 6 GHz
    if 1 <= ch <= 233:
        return 5950 + ch * 5

    return None


def freq_to_band(freq):
    if freq is None:
        return "Unknown"

    f = int(freq)
    if 2400 <= f <= 2500:
        return "2.4 GHz"
    if 5170 <= f <= 5895:
        return "5 GHz"
    if 5925 <= f <= 7125:
        return "6 GHz"
    return "Unknown"


# ======================================================
# SCAN WIFI – LINUX (Raspberry Pi)
# ======================================================
def scan_wifi_linux():
    """
    Scan WiFi trên Linux/Raspberry Pi dùng nmcli.
    Trả về list các AP:
    {
        ssid, bssid, signal, channel, freq, band, security
    }
    """
    try:
        result = subprocess.check_output(
            [
                "nmcli", "-t",
                "-f", "ACTIVE,BSSID,SSID,MODE,CHAN,RATE,SIGNAL,BARS,SECURITY",
                "dev", "wifi"
            ],
            text=True
        )

        wifi_list = []

        for raw in result.split("\n"):
            if not raw.strip():
                continue

            # nmcli dùng "\:" để escape, đổi lại về ":" thật
            raw = raw.replace("\\:", ":")

            parts = raw.split(":")
            # ACTIVE,BSSID(6 phần),SSID,MODE,CHAN,RATE,SIGNAL,BARS,SECURITY
            if len(parts) < 13:
                continue

            # BSSID = ghép 6 phần tiếp theo
            bssid = ":".join(parts[1:7])
            ssid = parts[7].strip()

            # CHANNEL
            try:
                channel = int(parts[9])
            except Exception:
                channel = None

            # SIGNAL %
            try:
                signal = int(parts[11])
            except Exception:
                signal = None

            # SECURITY
            security = parts[12] if len(parts) > 12 else "Unknown"

            # Freq + Band
            freq = channel_to_freq(channel)

            wifi_list.append({
                "ssid": ssid,
                "bssid": bssid,
                "signal": signal,
                "channel": channel,
                "freq": freq,
                "band": freq_to_band(freq),
                "security": security
            })

        return wifi_list

    except Exception as e:
        print("[SCAN LINUX ERROR]", e)
        return []


# ======================================================
# SCAN WIFI – WINDOWS (netsh)
# ======================================================
def scan_wifi_windows():
    """
    Scan WiFi trên Windows bằng netsh (có security).
    Trả về list các AP:
    {
        ssid, bssid, signal, channel, freq, band, security
    }
    """
    try:
        result = subprocess.check_output(
            "netsh wlan show networks mode=bssid",
            shell=True,
            text=True
        )

        wifi_list = []

        ssid = None
        security = "Unknown"
        current_ap = None

        for line in result.split("\n"):
            line = line.strip()

            # NEW SSID BLOCK
            if line.startswith("SSID "):
                ssid = line.split(":", 1)[1].strip()
                security = "Unknown"  # reset mỗi SSID
                continue

            # SECURITY
            if "Authentication" in line:
                security = line.split(":", 1)[1].strip()
                continue

            # BSSID
            if line.startswith("BSSID"):
                m = re.search(r"BSSID \d+\s*:\s*([0-9A-Fa-f:-]+)", line)
                if m and ssid:
                    current_ap = {
                        "ssid": ssid,
                        "bssid": m.group(1),
                        "signal": None,
                        "channel": None,
                        "freq": None,
                        "band": "Unknown",
                        "security": security
                    }
                    wifi_list.append(current_ap)
                continue

            # SIGNAL
            if "Signal" in line and current_ap:
                try:
                    current_ap["signal"] = int(
                        line.split(":", 1)[1].replace("%", "").strip()
                    )
                except Exception:
                    current_ap["signal"] = None
                continue

            # CHANNEL
            if "Channel" in line and current_ap:
                try:
                    ch = int(line.split(":", 1)[1].strip())
                    current_ap["channel"] = ch

                    freq = channel_to_freq(ch)
                    current_ap["freq"] = freq
                    current_ap["band"] = freq_to_band(freq)

                except Exception:
                    pass
                continue

        return wifi_list

    except Exception as e:
        print("[SCAN WIN ERROR]", e)
        return []


# ======================================================
# MERGE SCAN RESULT WITH CACHE
# ======================================================
def merge_scan_with_cache(raw_list):
    """
    Gộp kết quả scan mới với cache:
    - Nếu AP xuất hiện: missing = 0, cập nhật data
    - Nếu AP không xuất hiện trong lần scan này: missing += 1
    - Nếu missing >= SCAN_LIMIT: xoá khỏi cache
    """
    global wifi_cache

    seen = set()

    for ap in raw_list:
        key = ap.get("bssid") or ap.get("ssid")
        if not key:
            continue

        seen.add(key)

        if key not in wifi_cache:
            wifi_cache[key] = {"data": ap, "missing": 0}
        else:
            wifi_cache[key]["data"] = ap
            wifi_cache[key]["missing"] = 0

    # tăng missing cho AP không thấy trong lần scan này
    for key in list(wifi_cache.keys()):
        if key not in seen:
            wifi_cache[key]["missing"] += 1
            if wifi_cache[key]["missing"] >= SCAN_LIMIT:
                del wifi_cache[key]

    # trả về list AP hiện còn trong cache
    return [wifi_cache[k]["data"] for k in wifi_cache]


# ======================================================
# ENTRY POINT SCAN
# ======================================================
def scan_wifi():
    """
    Hàm gọi chung cho API:
    - Tự detect OS
    - Scan raw
    - Merge với cache
    """
    os_name = platform.system().lower()

    if "linux" in os_name:
        raw = scan_wifi_linux()
    elif "windows" in os_name:
        raw = scan_wifi_windows()
    else:
        raw = []

    return merge_scan_with_cache(raw)


# ======================================================
# WIFI STATUS (LINUX)
# ======================================================
def wifi_status_linux():
    """
    Trả về thông tin WiFi đang kết nối trên Linux:
    {
        ssid, signal, bssid, channel, freq, band, security, device
    }
    """
    try:
        result = subprocess.check_output(
            ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,BSSID,CHAN,FREQ,SECURITY,DEVICE",
             "dev", "wifi"],
            text=True
        )

        for line in result.split("\n"):
            if line.startswith("yes:"):
                parts = line.split(":")

                ssid = parts[1]
                signal = parts[2]
                bssid = parts[3]
                channel = parts[4]

                try:
                    freq = int(parts[5])
                except Exception:
                    freq = None

                security = parts[6] if len(parts) > 6 else "Unknown"
                device = parts[7] if len(parts) > 7 else ""

                return {
                    "ssid": ssid,
                    "signal": signal,
                    "bssid": bssid,
                    "channel": channel,
                    "freq": freq,
                    "band": freq_to_band(freq),
                    "security": security,
                    "device": device
                }

        return {}

    except Exception as e:
        print("[STATUS LINUX ERROR]", e)
        return {}


# ======================================================
# WIFI STATUS (WINDOWS)
# ======================================================
def wifi_status_windows():
    """
    Trả về thông tin WiFi đang kết nối trên Windows:
    {
        ssid, signal, bssid, channel, freq, band, security, device
    }
    """
    try:
        result = subprocess.check_output(
            "netsh wlan show interfaces",
            shell=True,
            text=True
        )

        status = {
            "ssid": "",
            "signal": "",
            "bssid": "",
            "channel": "",
            "freq": None,
            "band": "",
            "security": "",
            "device": ""
        }

        for line in result.split("\n"):
            line = line.strip()

            if line.startswith("SSID"):
                status["ssid"] = line.split(":", 1)[1].strip()

            if line.startswith("BSSID"):
                status["bssid"] = line.split(":", 1)[1].strip()

            if line.startswith("Signal"):
                status["signal"] = line.split(":", 1)[1].replace("%", "").strip()

            if line.startswith("Channel"):
                try:
                    ch = int(line.split(":", 1)[1].strip())
                    status["channel"] = ch
                    freq = channel_to_freq(ch)
                    status["freq"] = freq
                    status["band"] = freq_to_band(freq)
                except Exception:
                    pass

            if line.startswith("Authentication"):
                status["security"] = line.split(":", 1)[1].strip()

            if line.startswith("Name"):
                status["device"] = line.split(":", 1)[1].strip()

        return status

    except Exception as e:
        print("[STATUS WIN ERROR]", e)
        return {}


# ======================================================
# UNIVERSAL STATUS
# ======================================================
def wifi_status():
    """
    Hàm gọi chung cho API /api/wifi/status
    """
    os_name = platform.system().lower()

    if "linux" in os_name:
        return wifi_status_linux()

    if "windows" in os_name:
        return wifi_status_windows()

    return {}
