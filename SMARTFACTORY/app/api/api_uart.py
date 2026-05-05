"""
UART API Blueprint - REST endpoints for serial communication.

Protocol:
    POST /api/uart/command  {"command": 0}  → dừng băng tải  ("0\n")
    POST /api/uart/command  {"command": 1}  → chạy băng tải  ("1\n")
    GET  /api/uart/status                   → trạng thái kết nối
    GET  /api/uart/read                     → dữ liệu nhận mới nhất từ thiết bị
"""

from flask import Blueprint, jsonify, request
import structlog

from app.services.uart_service import uart_service

logger = structlog.get_logger(__name__)

api_uart = Blueprint("uart", __name__, url_prefix="/api/uart")


# ---------------------------------------------------------------------------
# POST /api/uart/command
# ---------------------------------------------------------------------------
@api_uart.post("/command")
def uart_command():
    """
    Gửi lệnh điều khiển băng tải qua UART.

    Request Body:
        {"command": 1}   — chạy băng tải
        {"command": 0}   — dừng băng tải

    Returns:
        {"status": "success", "command": 0|1}
        {"status": "error",   "message": "..."} (400 / 503)
    """
    data = request.get_json(silent=True) or {}
    command = data.get("command")

    if command not in (0, 1):
        return jsonify({
            "status":  "error",
            "message": "command must be 0 (stop) or 1 (run)"
        }), 400

    ok = uart_service.send_command(command)
    if ok:
        return jsonify({"status": "success", "command": command})
    return jsonify({"status": "error", "message": "UART not connected"}), 503


# ---------------------------------------------------------------------------
# GET /api/uart/status
# ---------------------------------------------------------------------------
@api_uart.get("/status")
def uart_status():
    """Trạng thái kết nối UART."""
    return jsonify({"status": "success", "data": uart_service.status()})


# ---------------------------------------------------------------------------
# GET /api/uart/read
# ---------------------------------------------------------------------------
@api_uart.get("/read")
def uart_read():
    """Dữ liệu mới nhất nhận từ thiết bị (hoặc null)."""
    return jsonify({"status": "success", "data": uart_service.get_last_received()})
