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

Protocol (one ASCII digit + CRLF):
    0  →  dừng băng tải
    1  →  chạy băng tải
    2  →  servo 1 đóng
    3  →  servo 1 mở
    4  →  servo 2 đóng
    5  →  servo 2 mở
    6  →  dừng khẩn cấp  (thiết bị tự xử lý: dừng băng tải + đóng servo 1 + đóng servo 2)

Receive : bất kỳ dòng text nào ←  echo / status từ thiết bị
"""

import glob
import os
import threading
import time

import serial
import structlog

logger = structlog.get_logger(__name__)

# ── Command table ─────────────────────────────────────────────────────────────
COMMANDS = {
    0: "CONVEYOR_STOP",
    1: "CONVEYOR_RUN",
    2: "SERVO1_CLOSE",
    3: "SERVO1_OPEN",
    4: "SERVO2_CLOSE",
    5: "SERVO2_OPEN",
    6: "EMERGENCY_STOP",
}

# Fallback scan order when configured port is not available (Linux only)
_LINUX_SCAN_PATTERNS = ["/dev/ttyACM*", "/dev/ttyUSB*"]


def _find_port(preferred: str) -> str:
    """
    Return the best available serial port.
    1. Try the preferred port from config/env.
    2. Scan /dev/ttyACM* then /dev/ttyUSB* (first found wins).
    3. Fall back to preferred (will fail on open — logged clearly).
    """
    import serial.tools.list_ports as lp

    existing = [p.device for p in lp.comports()]
    if preferred in existing:
        return preferred

    for pattern in _LINUX_SCAN_PATTERNS:
        matches = sorted(glob.glob(pattern))
        if matches:
            found = matches[0]
            logger.info("uart_port_autodetected",
                        configured=preferred, found=found)
            return found

    return preferred


class UARTService:
    """Singleton UART service for send/receive over serial port."""

    def __init__(self):
        self.ser: serial.Serial | None = None
        self.connected: bool = False
        self.port: str = "/dev/ttyACM0"
        self.baudrate: int = 115200

        self._last_received = None
        self._last_command: int | None = None

        # Device state (updated on every successful send)
        self._conveyor_running: bool = False
        self._servo1_open: bool = False
        self._servo2_open: bool = False

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

    def _write(self, command: int) -> bool:
        """Low-level write: send one digit + CRLF."""
        if not self.connected or not self.ser:
            logger.warning("uart_send_skipped_not_connected", command=command)
            return False
        try:
            with self._write_lock:
                self.ser.write(f"{command}\r\n".encode("utf-8"))
            logger.info("uart_sent",
                        command=command,
                        label=COMMANDS.get(command, "?"))
            return True
        except Exception as e:
            logger.error("uart_send_failed", error=str(e))
            self.connected = False
            return False

    def _update_state(self, command: int) -> None:
        """Update internal device state after a successful send."""
        if command == 0:
            self._conveyor_running = False
        elif command == 1:
            self._conveyor_running = True
        elif command == 2:
            self._servo1_open = False
        elif command == 3:
            self._servo1_open = True
        elif command == 4:
            self._servo2_open = False
        elif command == 5:
            self._servo2_open = True
        elif command == 6:
            self._conveyor_running = False
            self._servo1_open = False
            self._servo2_open = False

    def send_command(self, command: int) -> bool:
        """
        Send a single command (0–5) over UART.
        For emergency stop use emergency_stop() which sends command 6.

        Args:
            command: 0–5  (see COMMANDS table)
        Returns:
            True if sent successfully.
        """
        if command not in COMMANDS or command == 6:
            logger.warning("uart_invalid_command", command=command)
            return False

        ok = self._write(command)
        if ok:
            self._last_command = command
            self._update_state(command)
        return ok

    def emergency_stop(self) -> bool:
        """
        Emergency stop: send command 6 — device handles conveyor stop +
        servo1 close + servo2 close internally.

        Returns True if sent successfully.
        """
        logger.warning("uart_emergency_stop_triggered")
        ok = self._write(6)
        if ok:
            self._last_command = 6
            self._update_state(6)
            logger.warning("uart_emergency_stop_sent")
        else:
            logger.error("uart_emergency_stop_failed")
        return ok

    # ── Public API ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "connected":        self.connected,
            "port":             self.port,
            "baudrate":         self.baudrate,
            "last_command":     self._last_command,
            "last_label":       COMMANDS.get(self._last_command, None),
            "conveyor_running": self._conveyor_running,
            "servo1_open":      self._servo1_open,
            "servo2_open":      self._servo2_open,
        }

    def get_last_received(self):
        return self._last_received


# Singleton instance
uart_service = UARTService()
