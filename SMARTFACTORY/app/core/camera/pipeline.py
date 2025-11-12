import threading
import time
from app.core.camera import CameraReader, ColorObject, ColorDetector, Tracker, DrawManager

class CameraPipeline:
    def __init__(self, config):
        self.camera = CameraReader(src=config.src, width=config.width, height=config.height, fps=config.fps)
        self.detector = ColorDetector(
            color_objects=[ColorObject(c["name"], c["lower"], c["upper"], c["bgr"]) for c in config.colors],
            min_area=config.min_area
        )
        self.tracker = Tracker(max_lost=config.max_lost, max_history=config.max_history, match_dist=config.match_dist)
        self.drawer = DrawManager(self.tracker, show_fps=config.show_fps)
        self.frame = None
        self.frame_lock = threading.Lock()
        self.running = True
        self.det_interval = 1.0 / max(config.max_det_fps, 1e-3)
        self.detections = []
        self.tracked = []

    def start(self):
        threading.Thread(target=self._detection_loop, daemon=True).start()

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
            detections = self.detector.detect(frame)
            self.detections = detections
            boxes = [(x,y,w,h) for x,y,w,h,_ in detections]
            tracked = self.tracker.update(boxes)
            self.tracked = tracked
            frame_drawn = self.drawer.render(frame, tracked, detections)
            with self.frame_lock:
                self.frame = frame_drawn

    def stop(self):
        self.running = False
        self.camera.stop()

    def get_frame(self):
        with self.frame_lock:
            if self.frame is None:
                return None
            import cv2
            ret, jpeg = cv2.imencode('.jpg', self.frame)
            return jpeg.tobytes() if ret else None

    def get_detections(self):
        with self.frame_lock:
            if not hasattr(self.detector, "last_detections") or not self.detector.last_detections:
                return []
            return [color_obj.to_dict() for x,y,w,h,color_obj in self.detector.last_detections]
