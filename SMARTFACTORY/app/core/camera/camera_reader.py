import cv2
import time
import threading
from app.logging_config import init_logger

logger = init_logger("CameraReader")


class CameraReader:
    """
    Threaded camera reader supporting USB, RTSP, and MJPEG-over-HTTP streams.

    Optimisations vs. original:
    ─────────────────────────────────────────────────────────────────
    • RTSP URLs (rtsp://) detected and opened with OpenCV VideoCapture
      (same as USB path) but with CAP_PROP_BUFFERSIZE=1 to keep the
      internal buffer minimal — prevents stale frames building up when
      the detection loop is slower than the camera FPS.
    • _update_loop() uses grab()+retrieve() instead of read() so the
      capture thread always drains the OS buffer and keeps only the
      latest frame.  Eliminates lag on high-FPS RTSP streams.
    • Reconnect logic unchanged.
    """

    def __init__(self, src=0, width=640, height=480, fps=30, reconnect_delay=2):
        self.src = src
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect_delay = reconnect_delay

        self.cap = None
        self.frame = None
        self.running = False
        self.is_mjpeg = False

        self.lock = threading.Lock()
        self.thread = None

        # Route: HTTP MJPEG → MJPEGReader, everything else → VideoCapture
        if isinstance(src, str) and src.lower().startswith("http"):
            self._init_mjpeg(src)
        else:
            self._init_capture()

    # ------------------------------------------------------------------
    # Init VideoCapture (USB int index OR rtsp:// string)
    # ------------------------------------------------------------------
    def _init_capture(self):
        self.is_mjpeg = False
        if self._open_capture():
            self._start_thread()
        else:
            logger.error("CameraReader: cannot open source", src=self.src)

    def _open_capture(self) -> bool:
        """Open VideoCapture for USB index or RTSP/HTTP URL."""
        self.cap = cv2.VideoCapture(self.src)

        if not self.cap.isOpened():
            logger.error("Failed to open capture", src=self.src)
            return False

        # USB cameras: set resolution + FPS
        if isinstance(self.src, int):
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS,          self.fps)

        # Keep internal OpenCV buffer as small as possible.
        # Prevents old frames from accumulating when the pipeline
        # runs slower than the camera frame rate.
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        logger.info("Capture opened", src=self.src)
        return True

    # ------------------------------------------------------------------
    # Init MJPEG-over-HTTP
    # ------------------------------------------------------------------
    def _init_mjpeg(self, url: str):
        from app.core.camera.mjpeg_reader import MJPEGReader
        self.is_mjpeg = True
        self.reader = MJPEGReader(url)
        self.reader.start()
        self.running = True
        logger.info("MJPEG stream started", url=url)

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------
    def _start_thread(self):
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _update_loop(self):
        """
        Continuously drain the capture buffer and keep only the latest frame.

        Uses grab() + retrieve() instead of read() so we can call grab()
        multiple times to discard buffered frames before retrieving.
        This keeps the stored frame as fresh as possible.
        """
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                logger.warning("Capture offline → reconnecting...")
                time.sleep(self.reconnect_delay)
                self._open_capture()
                continue

            # Drain any buffered frames; only keep the latest
            grabbed = self.cap.grab()
            if not grabbed:
                time.sleep(0.01)
                continue

            ok, frame = self.cap.retrieve()
            if ok and frame is not None:
                with self.lock:
                    self.frame = frame

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def read(self):
        """Return a copy of the latest frame (thread-safe)."""
        if self.is_mjpeg:
            return self.reader.read()

        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def is_opened(self) -> bool:
        if self.is_mjpeg:
            return self.reader.frame is not None
        return self.cap is not None and self.cap.isOpened()

    def stop(self):
        self.running = False
        if self.is_mjpeg:
            self.reader.stop()
            return
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()
        logger.info("CameraReader stopped")
