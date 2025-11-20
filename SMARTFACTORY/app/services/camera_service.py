import threading
import time
import cv2
from app.core.camera.pipeline import CameraPipeline
from app.core.config import config_service


class CameraService:
    """
    Camera service singleton to manage pipeline & streaming.
    Fixed version:
    - No dummy thread wrapping pipeline.start()
    - Pipeline.start() already spawns detection thread
    - Proper running flag management
    - Safe shutdown
    """
    def __init__(self):
        self.pipeline: CameraPipeline | None = None
        self.running = False
        self._lock = threading.Lock()
        self.logger = None

    def init_app(self, app):
        self.logger = app.logger
        self.logger.info("CameraService ready")

    def start(self, src_override=None) -> bool:
        with self._lock:
            if self.running:
                return True

            cfg = config_service.get_camera_config()

            # Override nguồn camera nếu FE gửi lên
            if src_override is not None:
                cfg.src = src_override
                if self.logger:
                    self.logger.info(f"Override camera source → {src_override}")

            try:
                self.pipeline = CameraPipeline(cfg)
                self.pipeline.start()
                self.running = True
                return True
            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Failed to start camera: {e}")
                self.running = False
                self.pipeline = None
                return False


    def stop(self) -> bool:
        """Stop camera pipeline safely."""
        with self._lock:
            if not self.running or not self.pipeline:
                return True

            try:
                self.pipeline.stop()
                self.pipeline = None
                self.running = False

                if self.logger:
                    self.logger.info("CameraService stopped successfully")

                return True

            except Exception as e:
                if self.logger:
                    self.logger.exception(f"Error during camera stop: {e}")
                return False

    def stream(self):
        """
        Yield MJPEG frames for /api/camera/stream.
        Must be extremely safe because Flask keeps generator running.
        """
        try:
            while self.running and self.pipeline:
                frame = None

                with self.pipeline.frame_lock:
                    frame = self.pipeline.frame

                if frame is None:
                    time.sleep(0.01)
                    continue

                ret, buf = cv2.imencode(".jpg", frame)
                if not ret:
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    buf.tobytes() +
                    b"\r\n"
                )

        except GeneratorExit:
            if self.logger:
                self.logger.info("Client disconnected from stream")

        except Exception as e:
            if self.logger:
                self.logger.exception(f"Error in stream generator: {e}")

    def get_status(self) -> dict:
        """Return simple status for /api/camera/status."""
        return {
            "running": self.running,
            "pipeline_ready": self.pipeline is not None,
            "detected": len(self.pipeline.detections) if self.pipeline else 0,
            "tracked": len(self.pipeline.tracked) if self.pipeline else 0
        }


# Singleton instance
camera_service = CameraService()
