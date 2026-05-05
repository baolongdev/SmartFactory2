import time
import cv2
import requests
import threading
import numpy as np
from app.logging_config import init_logger

logger = init_logger("MJPEGReader")


class MJPEGReader:
    """
    MJPEG stream reader dành cho IP camera.
    Đọc luồng ảnh JPEG liên tục qua HTTP stream.

    Features:
        - Thread-safe frame storage
        - Tự tách frame theo marker 0xFFD8 - 0xFFD9
        - Tự reconnect khi mất kết nối
    """

    def __init__(self, url, reconnect_delay=2.0):
        self.url = url
        self.reconnect_delay = reconnect_delay

        self.running = False
        self.frame = None

        self.lock = threading.Lock()
        self.thread = None

    # ----------------------------------------------------------------------

    def start(self):
        """Bắt đầu đọc luồng MJPEG ở thread nền."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

        logger.info(f"MJPEGReader started → {self.url}")

    # ----------------------------------------------------------------------

    def _loop(self):
        """Luồng chính: nhận stream JPEG liên tục."""
        while self.running:
            try:
                logger.info(f"Connecting to MJPEG stream: {self.url}")
                response = requests.get(self.url, stream=True, timeout=5)

                if response.status_code != 200:
                    logger.error(f"Failed to connect ({response.status_code}) → retry...")
                    time.sleep(self.reconnect_delay)
                    continue

                bytes_buffer = b""

                # 65536 bytes per chunk — large enough to hold a full JPEG
                # frame in 1-2 reads (typical frame = 20-80 KB at 640×480).
                # Using 1024 caused many partial reads per frame, adding
                # unnecessary CPU overhead and latency.
                for chunk in response.iter_content(chunk_size=65536):
                    if not self.running:
                        break
                    if not chunk:
                        continue

                    bytes_buffer += chunk

                    # Extract all complete JPEG frames from the buffer.
                    # A single large chunk may contain more than one frame,
                    # so keep looping until no more complete frames remain.
                    while True:
                        start = bytes_buffer.find(b'\xff\xd8')
                        if start == -1:
                            bytes_buffer = b""
                            break

                        end = bytes_buffer.find(b'\xff\xd9', start + 2)
                        if end == -1:
                            # Incomplete frame — keep the partial data
                            if start > 0:
                                bytes_buffer = bytes_buffer[start:]
                            break

                        jpg = bytes_buffer[start:end + 2]
                        bytes_buffer = bytes_buffer[end + 2:]

                        frame = cv2.imdecode(
                            np.frombuffer(jpg, dtype=np.uint8),
                            cv2.IMREAD_COLOR,
                        )
                        if frame is not None:
                            with self.lock:
                                self.frame = frame
                        # Continue inner loop to drain remaining frames

            except Exception as e:
                logger.error(f"MJPEG reader error: {e}")
                time.sleep(self.reconnect_delay)

    # ----------------------------------------------------------------------

    def read(self):
        """Trả về frame mới nhất (copy)."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    # ----------------------------------------------------------------------

    def stop(self):
        """Dừng đọc stream."""
        self.running = False
        logger.info("MJPEGReader stopped")
