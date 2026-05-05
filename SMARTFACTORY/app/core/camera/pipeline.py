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
    3-thread camera processing pipeline for Raspberry Pi 4:

    Thread 1 — CameraReader   : capture frames from USB/RTSP/MJPEG (already threaded)
    Thread 2 — _detection_loop: HSV detect + tracker update  (CPU ~20-40 ms/frame)
    Thread 3 — _encode_loop   : draw overlay + JPEG encode   (CPU ~30-50 ms/frame)

    Threads 2 and 3 run in parallel on separate Pi 4 cores because OpenCV
    releases the GIL during C-level image processing.  End-to-end throughput
    is limited by the SLOWER of the two (~17-25 FPS on Pi 4 vs ~10-15 FPS
    with the old single-thread design).

    Public API (unchanged):
        start()           — launch background threads
        stop()            — stop all threads
        get_frame()       — latest JPEG bytes for streaming
        get_detections()  — latest detection list (tracker-merged)
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
        # INTERNAL STATE — detection thread
        # -------------------------------------------------
        self.running = True
        self.det_interval = 1.0 / max(config.max_det_fps, 1e-3)
        self.max_objects  = config.max_objects   # 0 = unlimited

        # FPS — Exponential Moving Average, α=0.1 (≈10-frame smoothing window)
        # Updated once per frame using dt between consecutive frames.
        # More accurate than a 1-second window counter because:
        #   • no 1-second display lag
        #   • measured AFTER processing (not before), so no pre-processing bias
        #   • first frame initialises rather than distorting the average
        self._det_fps   = 0.0    # detection thread rate
        self._enc_fps   = 0.0    # encode/stream thread rate (shown in HUD)
        self._last_det_t: float = 0.0   # wall time of previous detection frame
        self._last_enc_t: float = 0.0   # wall time of previous encode frame

        # -------------------------------------------------
        # HANDOFF: detection → encoder
        # -------------------------------------------------
        # _pending holds the latest (frame, detections, tracked) tuple.
        # Encoder always consumes the LATEST — older frames are dropped
        # if encoding is slower than detection (correct for live streaming).
        self._pending      = None          # latest (frame, dets, tracked)
        self._pending_lock = threading.Lock()

        # -------------------------------------------------
        # OUTPUT — written by encoder, read by get_frame / get_detections
        # -------------------------------------------------
        self.frame             = None
        self._jpeg: bytes | None = None    # cached JPEG for streaming
        self.frame_lock        = threading.Lock()

        self._last_detections: list = []
        self._last_tracked:    list = []

    # ──────────────────────────────────────────────────────────────────────────

    def start(self):
        """Launch detection and encode threads."""
        logger.info("pipeline_starting")
        threading.Thread(
            target=self._detection_loop, daemon=True, name="sf-detect"
        ).start()
        threading.Thread(
            target=self._encode_loop, daemon=True, name="sf-encode"
        ).start()

    # ──────────────────────────────────────────────────────────────────────────
    # Thread 2 — Detection
    # ──────────────────────────────────────────────────────────────────────────

    def _detection_loop(self):
        """
        Read latest camera frame → HSV detect → tracker update.
        Publishes (frame, detections, tracked) for the encode thread.

        Uses precise sleep (remaining time) instead of 1 ms spin to avoid
        wasting CPU between detection cycles.
        """
        last_det_time = 0.0

        while self.running:
            now = time.time()

            # Precise rate-limit: sleep exactly the remaining interval
            remaining = self.det_interval - (now - last_det_time)
            if remaining > 0.0:
                time.sleep(remaining)
                continue

            last_det_time = time.time()

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.01)
                continue

            # ── Detect + Track ────────────────────────────────────────────
            detections = self.detector.detect(frame)

            # Keep only the N largest objects (by bounding-box area).
            # max_objects=0 means unlimited.
            if self.max_objects and len(detections) > self.max_objects:
                detections = sorted(
                    detections, key=lambda d: d[2] * d[3], reverse=True
                )[:self.max_objects]

            boxes   = [(x, y, w, h) for x, y, w, h, _ in detections]
            tracked = self.tracker.update(boxes)

            # Enforce max_objects limit on tracker state.
            # Without this, old tracked objects coast for up to max_lost
            # seconds and DrawManager still renders them as ghost objects.
            if self.max_objects:
                self.tracker.trim(self.max_objects)
                tracked = [t for t in tracked if not t[2]]  # drop coasting

            # ── Publish latest result for encoder ─────────────────────────
            with self._pending_lock:
                self._pending = (frame, detections, tracked)

            # ── Detection FPS — EMA (α=0.1) ───────────────────────────────
            # Measured AFTER all processing so dt reflects true frame cost.
            t_now = time.time()
            if self._last_det_t > 0.0:
                dt = t_now - self._last_det_t
                if dt > 0.0:
                    self._det_fps = 0.9 * self._det_fps + 0.1 * (1.0 / dt)
            self._last_det_t = t_now

    # ──────────────────────────────────────────────────────────────────────────
    # Thread 3 — Draw + Encode
    # ──────────────────────────────────────────────────────────────────────────

    def _encode_loop(self):
        """
        Consume the latest detection result → draw overlay → encode JPEG.

        Runs independently of the detection thread.  If encoding is slower
        than detection, intermediate frames are skipped (always shows the most
        recent result — correct behaviour for live video).

        JPEG quality 72 saves ~30 % encoding time vs 85 on ARM with barely
        perceptible quality difference at 640×480 streaming resolution.
        """
        while self.running:
            # Poll for new pending frame (5 ms poll ≪ encode latency)
            with self._pending_lock:
                item           = self._pending
                self._pending  = None

            if item is None:
                time.sleep(0.005)
                continue

            frame, detections, tracked = item

            # ── Draw overlay ──────────────────────────────────────────────
            # Pass encode FPS so HUD shows the rate the browser actually sees.
            frame_drawn = self.drawer.render(
                frame, tracked, detections, fps=self._enc_fps
            )

            # ── JPEG encode ───────────────────────────────────────────────
            # Quality 72: ~30 % faster than 85 on Pi 4 ARM;
            # difference imperceptible at 640×480 streaming resolution.
            ret, jpeg = cv2.imencode(
                ".jpg", frame_drawn,
                [cv2.IMWRITE_JPEG_QUALITY, 72]
            )

            # ── Store atomically for get_frame() / get_detections() ───────
            with self.frame_lock:
                self.frame            = frame_drawn
                self._jpeg            = jpeg.tobytes() if ret else None
                self._last_detections = detections
                self._last_tracked    = tracked

            # ── Encode FPS — EMA (α=0.1) ─────────────────────────────────
            # Measured after imencode completes → true stream throughput.
            t_now = time.time()
            if self._last_enc_t > 0.0:
                dt = t_now - self._last_enc_t
                if dt > 0.0:
                    self._enc_fps = 0.9 * self._enc_fps + 0.1 * (1.0 / dt)
            self._last_enc_t = t_now

    # ──────────────────────────────────────────────────────────────────────────

    def stop(self):
        logger.info("pipeline_stopping")
        self.running = False
        self.camera.stop()

    # ──────────────────────────────────────────────────────────────────────────

    def get_frame(self):
        """Return cached JPEG bytes (encoded by encode thread)."""
        with self.frame_lock:
            return self._jpeg

    # ──────────────────────────────────────────────────────────────────────────

    def get_detections(self):
        """
        Return detected objects merged with tracker IDs.

        Returns one entry per *active* tracked object (coasting objects
        excluded).  Each entry is the ColorObject dict enriched with:
            tracker_id : str   — unique object ID from Tracker
            bbox       : list  — [x, y, w, h] bounding box on frame
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
        used_det = set()

        for item in tracked:
            obj_id, (tx, ty, tw, th), coasting = item
            if coasting:
                continue

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
