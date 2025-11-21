# app/services/camera_service.py
import threading
import time
import cv2
from typing import Any, Dict, List, Optional

from app.core.camera.color_object import ColorObject
from app.services.colors_service import colors_service
from app.core.camera.pipeline import CameraPipeline
from app.core.config import config_service


class CameraService:
    """
    Camera service singleton quản lý pipeline & streaming.

    Vai trò:
    - Quản lý vòng đời CameraPipeline (start/stop).
    - Cung cấp API thân thiện cho layer API:
        + stream() → MJPEG generator
        + get_frame_bytes() → lấy 1 frame ảnh JPEG
        + get_detections() → list detection chuẩn hoá cho FE
        + get_status() → thông tin đơn giản
    - Ẩn toàn bộ chi tiết core (CameraReader, ColorDetector, Tracker...).
      Sau này đổi thuật toán detect chỉ cần sửa service + core,
      không phải sửa các API.
    """

    def __init__(self):
        self.pipeline: Optional[CameraPipeline] = None
        self.running: bool = False
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

            if src_override is not None:
                cfg.src = src_override
                if self.logger:
                    self.logger.info(f"Override camera source → {src_override}")

            try:
                self.pipeline = CameraPipeline(cfg)

                # 🔥 NEW: VERIFY CAMERA OPENED OK
                if not self.pipeline.camera.is_opened():
                    if self.logger:
                        self.logger.error("❌ Camera failed to open at source: %s", cfg.src)
                    self.pipeline = None
                    self.running = False
                    return False

                self.update_colors()
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
        """Dừng camera pipeline an toàn."""
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

    def get_frame_bytes(self) -> Optional[bytes]:
        """
        Lấy frame hiện tại dưới dạng JPEG bytes.
        Dùng được cho:
        - MJPEG stream
        - API /snapshot tải 1 ảnh đơn.
        """
        if not self.pipeline:
            return None
        return self.pipeline.get_frame()

    def stream(self):
        """
        Yield MJPEG frames cho /api/camera/stream.

        NOTE mở rộng:
        - Nếu muốn giới hạn FPS stream (ví dụ 15fps) có thể
          thêm time.sleep(1/15) trong vòng lặp.
        """
        try:
            while self.running:
                frame_bytes = self.get_frame_bytes()
                if not frame_bytes:
                    time.sleep(0.01)
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    frame_bytes +
                    b"\r\n"
                )

        except GeneratorExit:
            if self.logger:
                self.logger.info("Client disconnected from stream")

        except Exception as e:
            if self.logger:
                self.logger.exception(f"Error in stream generator: {e}")

    def get_detections(self) -> Optional[List[Dict[str, Any]]]:
        """
        Trả list các detection đã chuẩn hoá cho FE.

        Return:
            - None  → pipeline chưa sẵn sàng
            - []    → không thấy đối tượng nào
        """
        if not self.pipeline:
            return None

        raw_objs = self.pipeline.get_detections()
        detections: List[Dict[str, Any]] = []

        for o in raw_objs:

            # ===============================================================
            # 1) Trường hợp pipeline trả dict (từ ColorObject.to_dict())
            # ===============================================================
            if isinstance(o, dict):
                detections.append({
                    "x": o.get("x", 0),
                    "y": o.get("y", 0),
                    "w": o.get("w", 0),
                    "h": o.get("h", 0),
                    "name": o.get("color_name") or o.get("name", "unknown"),
                    "bgr": list(o.get("bgr", (255, 255, 255))),
                    "action_id": o.get("action_id", 0),
                    "duration_ms": o.get("duration_ms", 1000),
                })
            
            # ===============================================================
            # 2) Trường hợp pipeline trả instance ColorObject
            # ===============================================================
            elif hasattr(o, "name"):
                detections.append({
                    "x": getattr(o, "x", 0),
                    "y": getattr(o, "y", 0),
                    "w": getattr(o, "w", 0),
                    "h": getattr(o, "h", 0),
                    "name": getattr(o, "name", "unknown"),
                    "bgr": list(getattr(o, "bgr", (255, 255, 255))),
                    "action_id": getattr(o, "action_id", 0),
                    "duration_ms": getattr(o, "duration_ms", 1000),
                })

            # ===============================================================
            # 3) Fallback
            # ===============================================================
            else:
                detections.append({
                    "x": 0, "y": 0, "w": 0, "h": 0,
                    "name": "unknown",
                    "bgr": [200, 200, 200],
                    "action_id": 0,
                    "duration_ms": 1000,
                })

        return detections

    
    def update_colors(self) -> bool:
        """
        Hot-reload cấu hình màu cho ColorDetector
        sau khi /api/colors được cập nhật.
        """
        if not self.pipeline:
            # Chưa start camera thì thôi, lần start sau sẽ tự load config mới
            return False

        # Lấy colors mới đã được fill đủ lower/upper/bgr từ ColorsService
        colors = colors_service.get_colors()

        # Build lại danh sách ColorObject
        color_objects = [
            ColorObject(
                c["name"],
                c["lower"],
                c["upper"],
                c["bgr"],
                c["action_id"],
                c["duration_ms"],
            )
            for c in colors
        ]

        # Gán thẳng vào detector đang chạy
        self.pipeline.detector.color_objects = color_objects

        if self.logger:
            self.logger.info("[CameraService] Hot-reloaded color config")

        return True


    def get_status(self) -> dict:
        """Return status đơn giản cho /api/camera/status."""
        pipeline_ready = self.pipeline is not None
        detected = len(self.pipeline.detections) if pipeline_ready else 0
        tracked = len(self.pipeline.tracked) if pipeline_ready else 0

        return {
            "running": self.running,
            "pipeline_ready": pipeline_ready,
            "detected": detected,
            "tracked": tracked,
        }


# Singleton instance
camera_service = CameraService()
