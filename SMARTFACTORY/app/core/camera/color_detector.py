import cv2
import numpy as np
import logging
from app.core.camera.color_object import ColorObject

logger = logging.getLogger("ColorDetector")

# Max width for the detection frame.
# Frame is downscaled to this width before HSV processing.
# Fewer pixels = cheaper inRange/morphology/findContours.
# 320px is sufficient for conveyor-belt objects (large blobs).
_MAX_DETECT_W = 320


class ColorDetector:
    """
    HSV-based color detector optimised for real-time pipeline use.

    Optimisations vs. original:
    ─────────────────────────────────────────────────────────────────
    1. Pre-computed morphology kernel (class-level, not per-frame).
    2. Downscale frame to ≤320 px wide before ALL processing.
    3. Single GaussianBlur + single BGR→HSV conversion per frame
       (original did medianBlur per colour inside the loop).
    4. MORPH_OPEN (noise removal) + MORPH_CLOSE (merge nearby fragments).
    5. min_area scaled to detection resolution automatically.
    6. Bounding-box coordinates upscaled back to original resolution.
    """

    # Pre-computed once at class level — never reallocated at runtime.
    _KERNEL       = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    # Larger kernel for closing gaps between fragments of the same object.
    _CLOSE_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    def __init__(self, color_objects: list, min_area: int = 1500):
        self.color_objects = color_objects
        self.min_area = min_area
        self.last_detections: list = []

    # ------------------------------------------------------------------

    def detect(self, frame) -> list:
        """Run optimised HSV colour detection. Returns [(x,y,w,h,ColorObject)]."""
        if frame is None:
            return []

        orig_h, orig_w = frame.shape[:2]

        # ── 1. Downscale frame ──────────────────────────────────────────
        scale = min(_MAX_DETECT_W / orig_w, 1.0)
        if scale < 1.0:
            det_w = int(orig_w * scale)
            det_h = int(orig_h * scale)
            small = cv2.resize(frame, (det_w, det_h),
                               interpolation=cv2.INTER_LINEAR)
        else:
            small = frame

        # ── 2. Single blur + HSV — done ONCE for all colours ───────────
        blurred = cv2.GaussianBlur(small, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # min_area adjusted for detection resolution
        scaled_min_area = self.min_area * (scale ** 2)

        inv = 1.0 / scale
        detections: list = []

        for obj in self.color_objects:
            # ── 3. Threshold ────────────────────────────────────────────
            mask = cv2.inRange(hsv,
                               np.asarray(obj.lower, dtype=np.uint8),
                               np.asarray(obj.upper, dtype=np.uint8))

            # ── 4. OPEN removes noise; CLOSE merges nearby fragments ────
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self._KERNEL)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._CLOSE_KERNEL)

            # ── 5. Find contours ────────────────────────────────────────
            contours, _ = cv2.findContours(
                mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            for cnt in contours:
                if cv2.contourArea(cnt) < scaled_min_area:
                    continue

                sx, sy, sw, sh = cv2.boundingRect(cnt)

                # ── 6. Scale coords back to original resolution ─────────
                x = int(sx * inv)
                y = int(sy * inv)
                w = int(sw * inv)
                h = int(sh * inv)

                detected = ColorObject(
                    name=obj.name,
                    lower=obj.lower,
                    upper=obj.upper,
                    bgr=obj.bgr,
                    action_id=obj.action_id,
                    duration_ms=obj.duration_ms,
                )
                detected.x, detected.y, detected.w, detected.h = x, y, w, h
                detections.append((x, y, w, h, detected))

        self.last_detections = detections
        return detections
