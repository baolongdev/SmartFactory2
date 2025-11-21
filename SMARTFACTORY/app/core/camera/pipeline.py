# app/core/camera/pipeline.py

import threading
import time

from app.core.camera import (
    CameraReader,
    ColorObject,
    ColorDetector,
    Tracker,
    DrawManager,
)

from app.core.config import config_service


class CameraPipeline:
    """
    Camera Processing Pipeline:

    - CameraReader: đọc frame từ USB/IP/MJPEG camera
    - ColorDetector: detect vật thể theo HSV
    - Tracker: gán ID & theo dõi vị trí
    - DrawManager: vẽ bounding box / label / trajectory
    """

    def __init__(self, config):
        # -------------------------------------------------
        # CAMERA READER
        # -------------------------------------------------
        self.camera = CameraReader(
            src=config.src,
            width=config.width,
            height=config.height,
            fps=config.fps,
        )

        # -------------------------------------------------
        # LOAD COLOR CONFIG (external colors.json)
        # -------------------------------------------------
        color_cfg = config_service.get_color_config()

        color_objects = [
            ColorObject(
                c["name"],
                c["lower"],
                c["upper"],
                c["bgr"],
                c["action_id"],
                c["duration_ms"]
            )
            for c in color_cfg.colors
        ]

        # -------------------------------------------------
        # DETECTOR
        # -------------------------------------------------
        self.detector = ColorDetector(
            color_objects=color_objects,
            min_area=config.min_area,
        )

        # -------------------------------------------------
        # TRACKER
        # -------------------------------------------------
        self.tracker = Tracker(
            max_lost=config.max_lost,
            max_history=config.max_history,
            match_dist=config.match_dist,
        )

        # -------------------------------------------------
        # DRAW MANAGER
        # -------------------------------------------------
        self.drawer = DrawManager(
            tracker=self.tracker,
            show_fps=config.show_fps,
        )

        # -------------------------------------------------
        # INTERNAL STATE
        # -------------------------------------------------
        self.frame = None
        self.frame_lock = threading.Lock()

        self.running = True
        self.det_interval = 1.0 / max(config.max_det_fps, 1e-3)

        self.detections = []
        self.tracked = []

        # --- FPS state ---
        self._fps = 0.0
        self._fps_frame_count = 0
        self._fps_last_time = time.time()

    # ---------------------------------------------------------

    def start(self):
        """Start background detection loop."""
        threading.Thread(target=self._detection_loop, daemon=True).start()

    # ---------------------------------------------------------

    def _detection_loop(self):
        last_time = 0

        while self.running:
            now = time.time()

            if now - last_time < self.det_interval:
                time.sleep(0.001)
                continue

            last_time = now

            frame = self.camera.read()
            if frame is None:
                continue

            # --------- CẬP NHẬT FPS ----------
            self._fps_frame_count += 1
            elapsed = now - self._fps_last_time
            if elapsed >= 1.0:  # cập nhật mỗi ~1 giây
                self._fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._fps_last_time = now
            # ---------------------------------

            # Detect objects
            detections = self.detector.detect(frame)
            self.detections = detections

            boxes = [(x, y, w, h) for x, y, w, h, _ in detections]
            tracked = self.tracker.update(boxes)
            self.tracked = tracked

            # Draw overlay + TRUYỀN FPS VÀO ĐÂY
            frame_drawn = self.drawer.render(frame, tracked, detections, fps=self._fps)

            # Save to buffer
            with self.frame_lock:
                self.frame = frame_drawn

    # ---------------------------------------------------------

    def stop(self):
        self.running = False
        self.camera.stop()

    # ---------------------------------------------------------

    def get_frame(self):
        """Return current frame as JPEG."""
        with self.frame_lock:
            if self.frame is None:
                return None

            import cv2
            ret, jpeg = cv2.imencode(".jpg", self.frame)
            return jpeg.tobytes() if ret else None

    # ---------------------------------------------------------

    def get_detections(self):
        """Return last detection objects."""
        with self.frame_lock:
            if not self.detector.last_detections:
                return []

            return [
                color_obj.to_dict()
                for x, y, w, h, color_obj in self.detector.last_detections
            ]
