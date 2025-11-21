import cv2
import time
import threading
from app.logging_config import init_logger

logger = init_logger("CameraReader")


class CameraReader:
    """
    Low-level camera reader (USB or MJPEG IP stream).
    Handles:
        - automatic reconnect
        - threaded frame grabbing
        - thread-safe latest frame storage
    """

    def __init__(self, src=0, width=640, height=480, fps=60, reconnect_delay=2):
        self.src = src
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_delay = reconnect_delay

        # State
        self.cap = None
        self.frame = None
        self.running = False
        self.is_mjpeg = False

        self.lock = threading.Lock()
        self.thread = None

        # Detect MJPEG stream URL
        if isinstance(src, str) and src.startswith("http"):
            self._init_mjpeg(src)
        else:
            self._init_usb()

    # ----------------------------------------------------------------------
    # Init USB Camera
    # ----------------------------------------------------------------------
    def _init_usb(self):
        self.is_mjpeg = False
        self.cap = None

        if self._open_camera():
            self._start_thread()
        else:
            logger.error(f"CameraReader: cannot initialize USB camera src={self.src}")

    def _open_camera(self):
        """Try to open USB camera."""
        self.cap = cv2.VideoCapture(self.src)

        if not self.cap.isOpened():
            logger.error(f"Failed to open camera: {self.src}")
            return False

        # Apply settings
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        logger.info(f"Opened USB camera: src={self.src}")
        return True

    # ----------------------------------------------------------------------
    # Init MJPEG/IP Camera
    # ----------------------------------------------------------------------
    def _init_mjpeg(self, url):
        from app.core.camera.mjpeg_reader import MJPEGReader
        self.is_mjpeg = True

        self.reader = MJPEGReader(url)
        self.reader.start()

        self.running = True
        logger.info(f"Started MJPEG stream: url={url}")

    # ----------------------------------------------------------------------
    # Worker Thread
    # ----------------------------------------------------------------------
    def _start_thread(self):
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _update_loop(self):
        """Background loop to read frames continuously."""
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

    # ----------------------------------------------------------------------
    # Read Frame
    # ----------------------------------------------------------------------
    def read(self):
        """Return latest frame (thread-safe)."""
        if self.is_mjpeg:
            return self.reader.read()

        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def is_opened(self):
        """Check whether camera (USB or MJPEG) is opened successfully."""
        if self.is_mjpeg:
            # MJPEG stream = ok only when at least 1 frame received
            return self.reader.frame is not None

        return self.cap is not None and self.cap.isOpened()

    def stop(self):
        """Stop the camera safely."""
        self.running = False

        # MJPEG stop
        if self.is_mjpeg:
            self.reader.stop()
            return

        # USB stop
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()

        logger.info("CameraReader stopped")
