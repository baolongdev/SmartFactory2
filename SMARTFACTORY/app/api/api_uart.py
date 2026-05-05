"""
UART API Blueprint - REST endpoints for serial communication.

Endpoints:
----------
- POST /api/uart/send   : Send JSON command to device via UART
- GET  /api/uart/status : UART connection status
- GET  /api/uart/read   : Latest data received from device
"""

from flask import Blueprint, jsonify, request
import structlog

from app.services.uart_service import uart_service

logger = structlog.get_logger(__name__)

api_uart = Blueprint("uart", __name__, url_prefix="/api/uart")


# ---------------------------------------------------------------------------
# POST /api/uart/send
# ---------------------------------------------------------------------------
@api_uart.post("/send")
def uart_send():
    """
    Send a JSON command to the device over UART.

    Request Body:
        {"action": int, "duration_ms": int}   — conveyor command
        {"action": "PING"}                     — ping

    Returns:
        {"status": "success", "data": {...}}
        {"status": "error",   "message": "..."} (400 / 503)
    """
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    ok = uart_service.send(data)
    if ok:
        return jsonify({"status": "success", "data": data})
    return jsonify({"status": "error", "message": "UART not connected"}), 503


# ---------------------------------------------------------------------------
# GET /api/uart/status
# ---------------------------------------------------------------------------
@api_uart.get("/status")
def uart_status():
    """Return UART connection status."""
    return jsonify({"status": "success", "data": uart_service.status()})


# ---------------------------------------------------------------------------
# GET /api/uart/read
# ---------------------------------------------------------------------------
@api_uart.get("/read")
def uart_read():
    """Return the latest data received from the device (or null)."""
    return jsonify({"status": "success", "data": uart_service.get_last_received()})
