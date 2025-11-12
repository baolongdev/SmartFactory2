import cv2
import threading
import time
from app.logging_config import init_logger

logger = init_logger("CameraReader")

class CameraReader:
    def __init__(self, src=0, width=640, height=480, fps=60, reconnect_delay=2):
        self.src = src
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_delay = reconnect_delay

        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.thread = None

        self._open_camera()
        self._start_thread()

    def _open_camera(self):
        self.cap = cv2.VideoCapture(self.src)
        if not self.cap.isOpened():
            logger.error(f"Failed to open camera: {self.src}")
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        logger.info(f"Opened camera {self.src}")
        return True

    def _start_thread(self):
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _update_loop(self):
        min_interval = 1.0 / max(self.fps, 1e-3)
        while self.running:
            start = time.time()
            if self.cap is None or not self.cap.isOpened():
                logger.warning("Camera offline → reconnecting...")
                time.sleep(self.reconnect_delay)
                self._open_camera()
                continue
            grabbed, frame = self.cap.read()
            if grabbed:
                with self.lock:
                    self.frame = frame
            elapsed = time.time() - start
            time.sleep(max(0, min_interval - elapsed))

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()
        logger.info("Stopped camera reader.")
