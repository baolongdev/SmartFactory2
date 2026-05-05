# app/core/camera/pipeline.py

import threading
import time

import cv2
import structlog

from app.core.camera import (
    CameraReader,
    ColorObject,
    ColorDetector,
    Tracker,
    DrawManager,
)

from app.core.config import config_service

logger = structlog.get_logger(__name__)


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
            alpha=config.overlay_alpha,
            trajectory_ttl=config.trajectory_ttl,
        )

        # -------------------------------------------------
        # INTERNAL STATE
        # -------------------------------------------------
        self.frame = None
        self._jpeg: bytes | None = None   # cached JPEG — encoded once per cycle
        self.frame_lock = threading.Lock()

        self.running = True
        self.det_interval = 1.0 / max(config.max_det_fps, 1e-3)

        # Stored atomically together under frame_lock so get_detections()
        # always reads a consistent (detections, tracked) pair.
        self._last_detections: list = []
        self._last_tracked:    list = []

        # --- FPS state ---
        self._fps = 0.0
        self._fps_frame_count = 0
        self._fps_last_time = time.time()

    # ---------------------------------------------------------

    def start(self):
        """Start background detection loop."""
        logger.info("pipeline_starting")
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
                time.sleep(0.01)
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

            boxes   = [(x, y, w, h) for x, y, w, h, _ in detections]
            # tracked: [(id, (x,y,w,h), coasting), ...]
            tracked = self.tracker.update(boxes)

            # Draw overlay
            frame_drawn = self.drawer.render(frame, tracked, detections, fps=self._fps)

            # Encode JPEG + cache everything atomically so get_detections()
            # always reads a consistent (detections, tracked) pair.
            ret, jpeg = cv2.imencode(
                ".jpg", frame_drawn,
                [cv2.IMWRITE_JPEG_QUALITY, 85]
            )
            with self.frame_lock:
                self.frame             = frame_drawn
                self._jpeg             = jpeg.tobytes() if ret else None
                self._last_detections  = detections
                self._last_tracked     = tracked

    # ---------------------------------------------------------

    def stop(self):
        logger.info("pipeline_stopping")
        self.running = False
        self.camera.stop()

    # ---------------------------------------------------------

    def get_frame(self):
        """Return cached JPEG bytes (encoded once per detection cycle)."""
        with self.frame_lock:
            return self._jpeg

    # ---------------------------------------------------------

    def get_detections(self):
        """
        Return detected objects merged with tracker IDs.

        Returns one entry per *active* tracked object (coasting objects are
        excluded).  Each entry is the ColorObject dict enriched with:
            tracker_id : str   — unique object ID assigned by the Tracker
            bbox       : list  — [x, y, w, h] bounding box on the frame

        This prevents the API from returning N raw contours for the same
        physical object (e.g. 17 red blobs all showing ID:1).
        """
        with self.frame_lock:
            detections = self._last_detections
            tracked    = self._last_tracked

        if not detections or not tracked:
            return []

        # Build detection-centre → ColorObject map (O(1) lookup)
        det_map: dict = {}
        for dx, dy, dw, dh, color_obj in detections:
            det_map[(dx + dw // 2, dy + dh // 2)] = (color_obj, dx, dy, dw, dh)

        result   = []
        used_det = set()   # prevent two tracked objects claiming the same detection

        for item in tracked:
            obj_id, (tx, ty, tw, th), coasting = item
            if coasting:
                continue   # only show live detections in the list

            cx, cy = tx + tw // 2, ty + th // 2

            # Find nearest detection centre for this tracked object
            best_key  = None
            best_dist = float("inf")
            for key in det_map:
                if key in used_det:
                    continue
                dx, dy = key
                d = abs(cx - dx) + abs(cy - dy)
                if d < best_dist:
                    best_dist = d
                    best_key  = key

            if best_key is None:
                continue

            used_det.add(best_key)
            color_obj, bx, by, bw, bh = det_map[best_key]

            entry = color_obj.to_dict()
            entry["tracker_id"] = str(obj_id)
            entry["bbox"]       = [bx, by, bw, bh]
            result.append(entry)

        return result
