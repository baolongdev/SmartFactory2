"""
UART API Blueprint - REST endpoints for serial communication.

Protocol (one ASCII digit + CRLF sent to device):
    0  →  dừng băng tải
    1  →  chạy băng tải
    2  →  servo 1 đóng
    3  →  servo 1 mở
    4  →  servo 2 đóng
    5  →  servo 2 mở
    6  →  dừng khẩn cấp (gửi 0 + 2 + 4 liên tiếp)

Endpoints:
    POST /api/uart/command   {"command": 0–5}  — gửi lệnh đơn
    POST /api/uart/estop                       — dừng khẩn cấp
    GET  /api/uart/status                      — trạng thái kết nối + device state
    GET  /api/uart/read                        — dữ liệu nhận mới nhất
"""

from flask import Blueprint, jsonify, request
import structlog

from app.services.uart_service import uart_service, COMMANDS

logger = structlog.get_logger(__name__)

api_uart = Blueprint("uart", __name__, url_prefix="/api/uart")

# Valid single commands (exclude 6 = emergency stop, handled separately)
_VALID_COMMANDS = tuple(c for c in COMMANDS if c != 6)


# ---------------------------------------------------------------------------
# POST /api/uart/command
# ---------------------------------------------------------------------------
@api_uart.post("/command")
def uart_command():
    """
    Gửi lệnh điều khiển qua UART.

    Request Body:
        {"command": 0}   — dừng băng tải
        {"command": 1}   — chạy băng tải
        {"command": 2}   — servo 1 đóng
        {"command": 3}   — servo 1 mở
        {"command": 4}   — servo 2 đóng
        {"command": 5}   — servo 2 mở

    Returns:
        {"status": "success", "command": N, "label": "..."}
        {"status": "error",   "message": "..."} (400 / 503)
    """
    data    = request.get_json(silent=True) or {}
    command = data.get("command")

    if command not in _VALID_COMMANDS:
        return jsonify({
            "status":  "error",
            "message": f"command must be one of {list(_VALID_COMMANDS)}"
        }), 400

    ok = uart_service.send_command(command)
    if ok:
        return jsonify({
            "status":  "success",
            "command": command,
            "label":   COMMANDS[command],
        })
    return jsonify({"status": "error", "message": "UART not connected"}), 503


# ---------------------------------------------------------------------------
# POST /api/uart/estop
# ---------------------------------------------------------------------------
@api_uart.post("/estop")
def uart_estop():
    """
    Dừng khẩn cấp: gửi 0 (conveyor stop) + 2 (servo1 close) + 4 (servo2 close).

    Returns:
        {"status": "success", "sequence": [0, 2, 4]}
        {"status": "error",   "message": "UART not connected"} (503)
    """
    ok = uart_service.emergency_stop()
    if ok:
        return jsonify({"status": "success", "sequence": [0, 2, 4]})
    return jsonify({"status": "error", "message": "UART not connected or partial failure"}), 503


# ---------------------------------------------------------------------------
# GET /api/uart/status
# ---------------------------------------------------------------------------
@api_uart.get("/status")
def uart_status():
    """
    Trạng thái kết nối UART + trạng thái thiết bị.

    Returns:
        {
          "status": "success",
          "data": {
            "connected": bool,
            "port": str,
            "baudrate": int,
            "last_command": int|null,
            "last_label": str|null,
            "conveyor_running": bool,
            "servo1_open": bool,
            "servo2_open": bool
          }
        }
    """
    return jsonify({"status": "success", "data": uart_service.status()})


# ---------------------------------------------------------------------------
# GET /api/uart/read
# ---------------------------------------------------------------------------
@api_uart.get("/read")
def uart_read():
    """Dữ liệu mới nhất nhận từ thiết bị (hoặc null)."""
    return jsonify({"status": "success", "data": uart_service.get_last_received()})
