import cv2
import logging
from app.core.camera import ColorObject

logger = logging.getLogger("ColorDetector")

class ColorDetector:
    """
    Detect objects by color in BGR frame using HSV thresholds.
    Returns list of (x,y,w,h,ColorObject)
    """
    def __init__(self, color_objects, min_area=1500):
        self.color_objects = color_objects
        self.min_area = min_area
        self.last_detections = []

    def detect(self, frame):
        if frame is None:
            logger.warning("[ColorDetector] Empty frame")
            return []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        detections = []

        for obj in self.color_objects:
            mask = cv2.inRange(hsv, obj.hsv_lower, obj.hsv_upper)
            mask = cv2.medianBlur(mask, 5)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in cnts:
                area = cv2.contourArea(cnt)
                if area < self.min_area:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                detected_obj = ColorObject(obj.name, obj.hsv_lower, obj.hsv_upper, obj.bgr)
                detected_obj.x, detected_obj.y, detected_obj.w, detected_obj.h = x, y, w, h
                detections.append((x, y, w, h, detected_obj))

        self.last_detections = detections
        return detections
