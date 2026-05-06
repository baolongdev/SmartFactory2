# app/services/camera_service.py
"""
Camera Service - Singleton service managing camera pipeline and streaming.

This module provides a high-level interface to the camera system:
- Start/stop camera pipeline
- Stream MJPEG video to clients
- Get detection results
- Update color configuration (hot-reload)

Architecture:
------------
- CameraService: Singleton service class
- CameraPipeline: Core processing pipeline (detection, tracking, drawing)
- CameraReader: Threaded frame capture from USB/IP/MJPEG cameras
- ColorDetector: HSV-based color detection
- Tracker: Object tracking with unique IDs
- DrawManager: Renders bounding boxes, labels, trajectories

Usage:
------
    from app.services.camera_service import camera_service

    # Start camera
    camera_service.start()

    # Get frame as JPEG bytes
    frame = camera_service.get_frame_bytes()

    # Get current detections
    detections = camera_service.get_detections()

    # Stop camera
    camera_service.stop()
"""

import threading
import time
import cv2
from typing import Any, Dict, List, Optional

import structlog

from app.core.camera.color_object import ColorObject
from app.services.colors_service import colors_service
from app.core.camera.pipeline import CameraPipeline
from app.core.config import config_service

# Module-level logger for CameraService
logger = structlog.get_logger(__name__)


class CameraService:
    """
    Singleton service managing camera pipeline lifecycle and streaming.

    This service provides:
    - Camera pipeline start/stop management
    - MJPEG streaming for web clients
    - Detection results retrieval
    - Color configuration hot-reload

    Design Patterns:
    - Singleton: Only one instance exists (camera_service)
    - Facade: Hides complexity of pipeline internals from API layer
    - Thread-Safe: Uses threading.Lock for start/stop operations

    Responsibilities:
    - Manage CameraPipeline lifecycle (create, start, stop)
    - Provide thread-safe access to pipeline state
    - Stream MJPEG frames to web clients
    - Return normalized detection results for frontend
    - Hot-reload color configuration when updated

    Usage:
        from app.services.camera_service import camera_service

        # Start camera with default config
        camera_service.start()

        # Start with specific camera source
        camera_service.start(src_override=1)

        # Get stream generator
        return Response(camera_service.stream(), ...)

        # Get current detections
        detections = camera_service.get_detections()

        # Stop camera
        camera_service.stop()
    """

    def __init__(self):
        """Initialize CameraService with default state."""
        self.pipeline: Optional[CameraPipeline] = None
        self.running: bool = False
        self._lock = threading.Lock()

    def init_app(self, app):
        """
        Initialize service with Flask app reference.

        Args:
            app: Flask application instance (used for logging context)
        """
        logger.info("camera_service_ready")

    def _is_healthy(self) -> bool:
        """Return True if pipeline is running and has produced at least one frame."""
        return self.pipeline is not None and self.pipeline._jpeg is not None

    def _stop_unlocked(self) -> None:
        """Stop pipeline without acquiring _lock (caller must already hold it)."""
        if self.pipeline:
            try:
                self.pipeline.stop()
            except Exception:
                pass
        self.pipeline = None
        self.running = False

    def start(self, src_override=None) -> bool:
        """
        Start camera pipeline with optional source override.

        Args:
            src_override: Camera source index or URL (optional)
                         If provided, overrides config value

        Returns:
            bool: True if started successfully, False otherwise

        Health check:
            If self.running is True but the pipeline is stale (no frames),
            the pipeline is automatically restarted instead of returning
            a false-positive True.

        First-frame wait:
            After starting, blocks up to 5 s waiting for the first JPEG
            frame so the caller can be confident the stream is live.
            Slow / RTSP cameras that miss the deadline still succeed but
            log a warning.
        """
        with self._lock:
            if self.running:
                if self._is_healthy():
                    # Pipeline alive and producing frames — nothing to do.
                    return True
                # Flag says running but no frames — stale/broken state.
                logger.warning("camera_pipeline_stale_restarting")
                self._stop_unlocked()

            cfg = config_service.get_camera_config()

            if src_override is not None:
                cfg.src = src_override
                logger.info("camera_source_override", src=src_override)

            try:
                self.pipeline = CameraPipeline(cfg)

                # ── Immediate open check (USB / RTSP via VideoCapture) ────
                # For MJPEG-over-HTTP, is_opened() returns False until the
                # first frame arrives — skip this check and let the
                # first-frame wait below handle it instead.
                if not self.pipeline.camera.is_mjpeg:
                    if not self.pipeline.camera.is_opened():
                        logger.error("camera_failed_to_open", src=cfg.src)
                        self.pipeline = None
                        self.running = False
                        return False

                self.update_colors()
                self.pipeline.start()
                self.running = True

                # ── Wait for first frame ──────────────────────────────────
                # Unified check for all source types:
                #   USB   — frame arrives in < 1 s after cap.read()
                #   RTSP  — frame arrives in 1-3 s after network connect
                #   MJPEG — frame arrives after HTTP connection + first chunk
                # If no frame within timeout → genuine failure (device not
                # reachable / wrong URL / wrong index).
                timeout_s = 8.0 if isinstance(cfg.src, str) else 4.0
                deadline  = time.time() + timeout_s
                while time.time() < deadline:
                    if self.pipeline._jpeg is not None:
                        break
                    time.sleep(0.05)

                if self.pipeline._jpeg is None:
                    logger.error("camera_no_frame_received",
                                 src=cfg.src, timeout_s=timeout_s)
                    self._stop_unlocked()
                    return False

                logger.info("camera_started", src=cfg.src)
                return True

            except Exception as e:
                logger.exception("camera_start_failed",
                                 error_type=type(e).__name__, src=cfg.src)
                self.running = False
                self.pipeline = None
                return False


    def stop(self) -> bool:
        """
        Stop camera pipeline safely.

        Returns:
            bool: True if stopped successfully or already stopped

        Thread Safety:
            Acquires _lock to prevent concurrent operations
        """
        with self._lock:
            # Already stopped
            if not self.running or not self.pipeline:
                return True

            try:
                self.pipeline.stop()
                self.pipeline = None
                self.running = False
                logger.info("camera_stopped")
                return True

            except Exception as e:
                logger.exception("camera_stop_failed", error_type=type(e).__name__)
                return False

    def get_frame_bytes(self) -> Optional[bytes]:
        """
        Get current frame as JPEG bytes.

        Returns:
            Optional[bytes]: JPEG-encoded frame bytes, or None if pipeline not ready
        """
        if not self.pipeline:
            return None
        return self.pipeline.get_frame()

    def stream(self):
        """
        Yield MJPEG frames for /api/camera/stream endpoint.

        Yields:
            bytes: MJPEG frame chunks with appropriate headers

        Note:
            To limit FPS (e.g., 15fps), add time.sleep(1/15) in the loop.
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
            logger.info("stream_client_disconnected")

        except Exception as e:
            logger.exception("stream_generator_error", error_type=type(e).__name__)

    def get_detections(self) -> Optional[List[Dict[str, Any]]]:
        """
        Return current detection results, normalized for frontend.

        Returns:
            None: Pipeline not ready
            []: No objects detected
            List[Dict]: List of detection objects with keys:
                - x, y: Top-left coordinates
                - w, h: Width and height
                - name: Color name
                - bgr: BGR color tuple
                - action_id: Action ID for MQTT command
                - duration_ms: Action duration

        Handles three cases:
        1. Pipeline returns dict (from ColorObject.to_dict())
        2. Pipeline returns ColorObject instance
        3. Fallback for unknown types
        """
        if not self.pipeline:
            return None

        raw_objs = self.pipeline.get_detections()
        detections: List[Dict[str, Any]] = []

        for o in raw_objs:
            # Case 1: Pipeline returns dict (standard path after our pipeline update)
            if isinstance(o, dict):
                detections.append({
                    "x":          o.get("x", 0),
                    "y":          o.get("y", 0),
                    "w":          o.get("w", 0),
                    "h":          o.get("h", 0),
                    "name":       o.get("color_name") or o.get("name", "unknown"),
                    "bgr":        list(o.get("bgr", (255, 255, 255))),
                    "action_id":  o.get("action_id", 0),
                    "duration_ms": o.get("duration_ms", 1000),
                    "servo_id":   o.get("servo_id", 0),
                    "tracker_id": o.get("tracker_id"),
                })

            # Case 2: Pipeline returns ColorObject instance
            elif hasattr(o, "name"):
                detections.append({
                    "x":          getattr(o, "x", 0),
                    "y":          getattr(o, "y", 0),
                    "w":          getattr(o, "w", 0),
                    "h":          getattr(o, "h", 0),
                    "name":       getattr(o, "name", "unknown"),
                    "bgr":        list(getattr(o, "bgr", (255, 255, 255))),
                    "action_id":  getattr(o, "action_id", 0),
                    "duration_ms": getattr(o, "duration_ms", 1000),
                    "servo_id":   getattr(o, "servo_id", 0),
                    "tracker_id": getattr(o, "tracker_id", None),
                })

            # Case 3: Fallback
            else:
                detections.append({
                    "x": 0, "y": 0, "w": 0, "h": 0,
                    "name": "unknown",
                    "bgr": [200, 200, 200],
                    "action_id": 0,
                    "duration_ms": 1000,
                    "servo_id": 0,
                    "tracker_id": None,
                })

        return detections

    
    def get_status(self) -> dict:
        """
        Return pipeline status for GET /api/camera/status.

        Includes FPS metrics from both pipeline threads:
            det_fps  — detection rate (how fast frames are processed)
            enc_fps  — encode/stream rate (what the browser actually sees)
        """
        p = self.pipeline
        if not p:
            return {
                "running":        False,
                "pipeline_ready": False,
                "detected":       0,
                "tracked":        0,
                "det_fps":        0.0,
                "enc_fps":        0.0,
            }

        with p.frame_lock:
            n_detected = len(p._last_detections)
            n_tracked  = len([t for t in p._last_tracked if not t[2]])  # non-coasting

        return {
            "running":        self.running,
            "pipeline_ready": p._jpeg is not None,
            "detected":       n_detected,
            "tracked":        n_tracked,
            "det_fps":        round(p._det_fps, 1),
            "enc_fps":        round(p._enc_fps, 1),
        }

    def update_colors(self) -> bool:
        """
        Hot-reload color configuration for running pipeline.

        Called after /api/colors is updated via POST request.
        Updates the ColorDetector with new color definitions.

        Returns:
            bool: True if updated successfully, False if pipeline not ready
        """
        if not self.pipeline:
            # Pipeline not running - will load new config on next start
            return False

        # Get updated colors from ColorsService
        colors = colors_service.get_colors()

        # Build ColorObject list
        color_objects = [
            ColorObject(
                c["name"],
                c["lower"],
                c["upper"],
                c["bgr"],
                c["action_id"],
                c["duration_ms"],
                c.get("servo_id", 0),
            )
            for c in colors
        ]

        # Update detector in running pipeline
        self.pipeline.detector.color_objects = color_objects

        logger.info("camera_colors_hot_reloaded")
        return True


# Singleton instance - imported by other modules
camera_service = CameraService()
