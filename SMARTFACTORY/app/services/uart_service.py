"""
UART Service - Singleton service for serial (UART) communication.

Sends JSON commands to the ESP32 conveyor controller over a serial port.
Receives status responses (e.g., {"status":"READY"}) from the device.

Configuration (environment variables):
    UART_PORT     — serial port, e.g. /dev/ttyUSB0  (Linux/Pi)
                                      /dev/ttyAMA0  (Pi GPIO UART)
                                      COM3          (Windows)
    UART_BAUDRATE — baud rate, default 115200

Protocol:
    Send : one JSON line  →  {"action":1,"duration_ms":4000}\n
    Recv : one JSON line  ←  {"status":"READY"}\n
"""

import json
import os
import threading
import time

import serial
import structlog

logger = structlog.get_logger(__name__)


class UARTService:
    """Singleton UART service for send/receive over serial port."""

    def __init__(self):
        self.ser: serial.Serial | None = None
        self.connected: bool = False
        self.port: str = "/dev/ttyUSB0"
        self.baudrate: int = 115200
        self._last_received = None   # latest parsed line from device
        self._write_lock = threading.Lock()

    def init_app(self, app) -> None:
        self.port     = os.environ.get("UART_PORT",     "/dev/ttyUSB0")
        self.baudrate = int(os.environ.get("UART_BAUDRATE", "115200"))
        self._connect()
        threading.Thread(target=self._read_loop, daemon=True,
                         name="sf-uart-rx").start()
        logger.info("uart_service_initialized",
                    port=self.port, baudrate=self.baudrate,
                    connected=self.connected)

    # ── Connection ────────────────────────────────────────────────────────────

    def _connect(self) -> None:
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            logger.info("uart_connected", port=self.port)
        except Exception as e:
            self.ser = None
            self.connected = False
            logger.warning("uart_connect_failed", port=self.port, error=str(e))

    # ── RX thread ─────────────────────────────────────────────────────────────

    def _read_loop(self) -> None:
        """Background thread: read lines from the device and cache latest."""
        while True:
            if not self.ser or not self.ser.is_open:
                time.sleep(2)
                self._connect()
                continue
            try:
                raw = self.ser.readline()
                if raw:
                    text = raw.decode("utf-8", errors="ignore").strip()
                    if text:
                        try:
                            self._last_received = json.loads(text)
                        except Exception:
                            self._last_received = text
                        logger.debug("uart_received", data=self._last_received)
            except Exception as e:
                logger.warning("uart_read_error", error=str(e))
                self.connected = False
                time.sleep(2)
                self._connect()

    # ── TX ───────────────────────────────────────────────────────────────────

    def send_command(self, command: int) -> bool:
        """
        Send a conveyor command over UART.

        Protocol: one ASCII character + newline
            "0\\n"  →  dừng băng tải (stop)
            "1\\n"  →  chạy băng tải (run)

        Args:
            command: 0 (stop) or 1 (run)

        Returns:
            True if written successfully, False if not connected or error.
        """
        if not self.connected or not self.ser:
            logger.warning("uart_send_skipped_not_connected", command=command)
            return False
        try:
            line = f"{command}\n"
            with self._write_lock:
                self.ser.write(line.encode("utf-8"))
            logger.info("uart_sent", command=command)
            return True
        except Exception as e:
            logger.error("uart_send_failed", error=str(e))
            self.connected = False
            return False

    # ── Status / read ─────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "port":      self.port,
            "baudrate":  self.baudrate,
        }

    def get_last_received(self):
        """Return latest data received from device (dict or raw string)."""
        return self._last_received


# Singleton instance
uart_service = UARTService()
