import threading
import time
import cv2
from app.core.camera.pipeline import CameraPipeline
from app.core.config import config_service

class CameraService:
    """Camera service singleton to manage pipeline & streaming."""
    def __init__(self):
        self.pipeline: CameraPipeline | None = None
        self.running = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.logger = None

    def init_app(self, app):
        self.logger = app.logger
        self.logger.info("CameraService ready")

    def start(self) -> bool:
        with self._lock:
            if self.running:
                return True
            cfg = config_service.get_camera_config()
            self.pipeline = CameraPipeline(cfg)
            self._thread = threading.Thread(target=self.pipeline.start, daemon=True)
            self._thread.start()
            self.running = True
            if self.logger:
                self.logger.info("CameraService started")
        return True

    def stop(self) -> bool:
        with self._lock:
            if not self.running or not self.pipeline:
                return True
            self.pipeline.stop()
            if self._thread:
                self._thread.join(timeout=2)
                if self._thread.is_alive() and self.logger:
                    self.logger.warning("Camera thread did not stop in 2s")
                self._thread = None
            self.running = False
            if self.logger:
                self.logger.info("CameraService stopped")
        return True

    def stream(self):
        """Yield MJPEG frames for Flask streaming."""
        try:
            while self.running and self.pipeline:
                with self.pipeline.frame_lock:
                    frame = self.pipeline.frame
                if frame is None:
                    time.sleep(0.01)
                    continue
                ret, buf = cv2.imencode(".jpg", frame)
                if not ret:
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        except GeneratorExit:
            if self.logger:
                self.logger.info("Client disconnected from camera stream")
        except Exception:
            if self.logger:
                self.logger.exception("Error in camera stream generator")

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "detected": len(self.pipeline.detections) if self.pipeline else 0,
            "tracked": len(self.pipeline.tracked) if self.pipeline else 0
        }

# Singleton instance
camera_service = CameraService()
