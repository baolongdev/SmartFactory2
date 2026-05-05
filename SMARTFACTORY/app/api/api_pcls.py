"""
PCLS Notification API Blueprint.

Proxies color-detection events to the PCLS external reporting service.

Endpoint:
---------
- POST /api/pcls/notify   : Send color_code notification to PCLS

Color Code Mapping:
-------------------
    red    (đỏ)         → 1
    blue   (xanh dương) → 2
    yellow (vàng)       → 3

Environment Variables:
----------------------
    PCLS_API_URL   : Full URL of the PCLS endpoint
                     default: https://api-pcls.splus-software.com.vn
    PCLS_DEVICE_ID : Device identifier sent with each notification
                     default: raspi-01
    PCLS_TIMEOUT   : Request timeout in seconds (default: 5)
"""

from flask import Blueprint, jsonify, request
import requests
import os

import structlog

logger = structlog.get_logger(__name__)

api_pcls = Blueprint("pcls", __name__, url_prefix="/api/pcls")

# ── Configuration from environment ───────────────────────────────────────────
PCLS_API_URL   = os.environ.get("PCLS_API_URL",   "https://api-pcls.splus-software.com.vn")
PCLS_DEVICE_ID = os.environ.get("PCLS_DEVICE_ID", "raspi-01")
PCLS_TIMEOUT   = int(os.environ.get("PCLS_TIMEOUT", "5"))

# ── Color name → code mapping ────────────────────────────────────────────────
COLOR_CODE_MAP: dict[str, int] = {
    "red":    1,   # đỏ
    "blue":   2,   # xanh dương
    "yellow": 3,   # vàng
}


# ---------------------------------------------------------------------------
# POST /api/pcls/notify
# ---------------------------------------------------------------------------
@api_pcls.post("/notify")
def api_notify():
    """
    Forward a color-detection event to the PCLS reporting service.

    Request Body:
        {
            "color_code": int,     # 1=red, 2=blue, 3=yellow  (required)
            "color_name": string   # human-readable name       (optional, for logging)
        }

    Returns:
        Success: {"success": true,  "color_code": int, "device_id": str}
        Error:   {"success": false, "message": str}  (400 / 502)

    Notes:
        - Calls PCLS_API_URL with JSON body {"device_id": ..., "color_code": ...}
        - Returns 502 if the upstream PCLS service is unreachable or returns an error
        - color_code values outside [1, 2, 3] are rejected with 400
    """
    data = request.get_json(silent=True) or {}

    color_code = data.get("color_code")
    color_name = data.get("color_name", "")

    # Validate
    if color_code not in (1, 2, 3):
        logger.warning("pcls_invalid_color_code", color_code=color_code)
        return jsonify({"success": False, "message": f"Invalid color_code: {color_code!r}. Must be 1, 2 or 3."}), 400

    payload = {
        "device_id":  PCLS_DEVICE_ID,
        "color_code": color_code,
    }

    try:
        resp = requests.post(
            PCLS_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=PCLS_TIMEOUT,
        )
        resp.raise_for_status()

        logger.info("pcls_notified",
                    color_code=color_code,
                    color_name=color_name,
                    device_id=PCLS_DEVICE_ID,
                    status=resp.status_code)

        return jsonify({
            "success":    True,
            "color_code": color_code,
            "device_id":  PCLS_DEVICE_ID,
        })

    except requests.exceptions.Timeout:
        logger.warning("pcls_timeout", url=PCLS_API_URL, color_code=color_code)
        return jsonify({"success": False, "message": "PCLS service timeout"}), 502

    except requests.exceptions.ConnectionError:
        logger.warning("pcls_connection_error", url=PCLS_API_URL)
        return jsonify({"success": False, "message": "PCLS service unreachable"}), 502

    except requests.exceptions.HTTPError as e:
        logger.warning("pcls_http_error", status=resp.status_code, color_code=color_code)
        return jsonify({"success": False, "message": f"PCLS returned {resp.status_code}"}), 502

    except Exception as e:
        logger.exception("pcls_unexpected_error", color_code=color_code)
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# GET /api/pcls/config
# ---------------------------------------------------------------------------
@api_pcls.get("/config")
def api_config():
    """
    Return current PCLS configuration (non-sensitive fields only).

    Returns:
        {
            "api_url":    string,
            "device_id":  string,
            "color_map":  { "red": 1, "blue": 2, "yellow": 3 }
        }
    """
    return jsonify({
        "api_url":   PCLS_API_URL,
        "device_id": PCLS_DEVICE_ID,
        "color_map": COLOR_CODE_MAP,
    })
