"""
UART Service - Singleton service for serial (UART) communication.

Configuration (environment variables):
    UART_PORT     — serial port, e.g. /dev/ttyACM0 (ESP32 USB)
                                      /dev/ttyUSB0  (USB-serial adapter)
                                      /dev/ttyAMA0  (Pi GPIO UART)
                                      COM3          (Windows)
                    If the configured port is not found, the service will
                    auto-scan /dev/ttyACM* then /dev/ttyUSB* on Linux.
    UART_BAUDRATE — baud rate, default 115200

Protocol:
    Send : "1\r\n"  →  chạy băng tải
           "0\r\n"  →  dừng băng tải
    Recv : any line ←  status/echo from device
"""

import glob
import os
import threading
import time

import serial
import structlog

logger = structlog.get_logger(__name__)

# Fallback scan order when configured port is not available (Linux only)
_LINUX_SCAN_PATTERNS = ["/dev/ttyACM*", "/dev/ttyUSB*"]


def _find_port(preferred: str) -> str:
    """
    Return the best available serial port.

    1. Try the preferred port from config/env.
    2. Scan /dev/ttyACM* then /dev/ttyUSB* (first found wins).
    3. Fall back to the preferred port (will fail on open — logged clearly).
    """
    import serial.tools.list_ports as lp

    # Check if preferred port exists
    existing = [p.device for p in lp.comports()]
    if preferred in existing:
        return preferred

    # Auto-scan Linux patterns
    for pattern in _LINUX_SCAN_PATTERNS:
        matches = sorted(glob.glob(pattern))
        if matches:
            found = matches[0]
            logger.info("uart_port_autodetected",
                        configured=preferred, found=found)
            return found

    # Nothing found — return preferred and let _connect() log the error
    return preferred


class UARTService:
    """Singleton UART service for send/receive over serial port."""

    def __init__(self):
        self.ser: serial.Serial | None = None
        self.connected: bool = False
        self.port: str = "/dev/ttyACM0"
        self.baudrate: int = 115200
        self._last_received = None    # latest data received from device
        self._last_command: int | None = None   # 0 or 1
        self._write_lock = threading.Lock()

    def init_app(self, app) -> None:
        configured = os.environ.get("UART_PORT", "/dev/ttyACM0")
        self.baudrate = int(os.environ.get("UART_BAUDRATE", "115200"))
        self.port = _find_port(configured)
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
            # Re-detect port each reconnect attempt (device may be re-plugged)
            configured = os.environ.get("UART_PORT", "/dev/ttyACM0")
            self.port = _find_port(configured)
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            logger.info("uart_connected", port=self.port)
        except Exception as e:
            self.ser = None
            self.connected = False
            logger.warning("uart_connect_failed", port=self.port, error=str(e))

    # ── RX thread ─────────────────────────────────────────────────────────────

    def _read_loop(self) -> None:
        """Background thread: read lines from device and cache latest."""
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
                        self._last_received = text
                        logger.debug("uart_received", data=text)
            except Exception as e:
                logger.warning("uart_read_error", error=str(e))
                self.connected = False
                time.sleep(2)
                self._connect()

    # ── TX ───────────────────────────────────────────────────────────────────

    def send_command(self, command: int) -> bool:
        """
        Send conveyor command over UART.
            1  →  "1\\r\\n"  chạy băng tải
            0  →  "0\\r\\n"  dừng băng tải
        """
        if not self.connected or not self.ser:
            logger.warning("uart_send_skipped_not_connected", command=command)
            return False
        try:
            with self._write_lock:
                self.ser.write(f"{command}\r\n".encode("utf-8"))
            self._last_command = command
            logger.info("uart_sent", command=command)
            return True
        except Exception as e:
            logger.error("uart_send_failed", error=str(e))
            self.connected = False
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "connected":    self.connected,
            "port":         self.port,
            "baudrate":     self.baudrate,
            "last_command": self._last_command,
        }

    def get_last_received(self):
        return self._last_received


# Singleton instance
uart_service = UARTService()
