import cv2
from flask import json
import numpy as np
import math
import threading
import time
import uuid
from collections import deque

# =========================================================
# CONFIGURATION
# =========================================================
class ConfigCamera:
    def __init__(self, path="config.json"):
        with open(path, "r") as f:
            cfg = json.load(f)

        # Camera
        cam = cfg.get("camera", {})
        self.cam_src = cam.get("src", 0)
        self.cam_width = cam.get("width", 640)
        self.cam_height = cam.get("height", 480)
        self.cam_fps = cam.get("fps", 60)

        # Detection
        det = cfg.get("detection", {})
        self.min_contour_area = det.get("min_contour_area", 1500)
        self.max_detection_fps = det.get("max_detection_fps", 30)

        # Tracker
        trk = cfg.get("tracker", {})
        self.max_lost = trk.get("max_lost", 15)
        self.max_history = trk.get("max_history", 20)
        self.match_dist = trk.get("match_dist", 80)

        # Drawing
        drw = cfg.get("drawing", {})
        self.show_fps = drw.get("show_fps", True)

        # Colors
        self.colors = cfg.get("colors", [])

# =========================================================
# CAMERA THREAD
# =========================================================
class Camera:
    def __init__(self, config):
        self.cap = cv2.VideoCapture(config.cam_src)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.cam_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.cam_height)
        self.cap.set(cv2.CAP_PROP_FPS, config.cam_fps)

        self.lock = threading.Lock()
        self.frame = None
        self.is_running = True
        self._start_thread()

    def _start_thread(self):
        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.is_running:
            grabbed, frame = self.cap.read()
            if not grabbed:
                print("[Camera] Frame grab failed")
                time.sleep(0.01)
                continue
            with self.lock:
                self.frame = frame

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.is_running = False
        self.cap.release()

# =========================================================
# COLOR OBJECT & DETECTOR
# =========================================================
class ColorObject:
    def __init__(self, name, hsv_lower, hsv_upper, draw_color):
        self.name = name
        self.hsv_lower = np.array(hsv_lower)
        self.hsv_upper = np.array(hsv_upper)
        self.draw_color = draw_color

class ColorDetector:
    def __init__(self, color_objects, min_area=1500):
        self.color_objects = color_objects
        self.min_area = min_area

    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        detections = []
        for obj in self.color_objects:
            mask = cv2.inRange(hsv, obj.hsv_lower, obj.hsv_upper)
            mask = cv2.medianBlur(mask, 7)
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in cnts:
                if cv2.contourArea(cnt) < self.min_area:
                    continue
                x, y, w, h = cv2.boundingRect(cnt)
                detections.append((x, y, w, h, obj))
        return detections

# =========================================================
# TRACKER
# =========================================================
class Tracker:
    def __init__(self, max_lost=15, max_history=20, match_dist=80):
        self.objects = {}  # id -> [x, y, w, h, last_time, trajectory]
        self.max_lost = max_lost
        self.max_history = max_history
        self.match_dist = match_dist
        self.lock = threading.Lock()

    def update(self, detections):
        now = time.time()
        updated_ids = []
        with self.lock:
            for det in detections:
                x, y, w, h = det[:4]
                cx, cy = x + w//2, y + h//2
                best_id = None
                best_dist = 99999
                for obj_id, info in self.objects.items():
                    ox, oy, ow, oh, last_time, traj = info
                    ocx, ocy = ox + ow//2, oy + oh//2
                    dist = math.hypot(cx - ocx, cy - ocy)
                    if dist < best_dist and dist < self.match_dist:
                        best_id = obj_id
                        best_dist = dist
                if best_id is None:
                    obj_id = str(uuid.uuid4())[:8]
                    self.objects[obj_id] = [x, y, w, h, now, deque(maxlen=self.max_history)]
                    self.objects[obj_id][5].append((cx, cy))
                    updated_ids.append((obj_id, det))
                else:
                    self.objects[best_id][:4] = [x, y, w, h]
                    self.objects[best_id][4] = now
                    self.objects[best_id][5].append((cx, cy))
                    updated_ids.append((best_id, det))

            lost = [obj_id for obj_id, info in self.objects.items() if now - info[4] > self.max_lost]
            for obj_id in lost:
                del self.objects[obj_id]

        return updated_ids

    def get_trajectory(self, obj_id):
        with self.lock:
            return list(self.objects[obj_id][5]) if obj_id in self.objects else []

# =========================================================
# DRAW MANAGER
# =========================================================
class DrawManager:
    def __init__(self, tracker, show_fps=True):
        self.tracker = tracker
        self.show_fps = show_fps

    @staticmethod
    def draw_rectangle(frame, x, y, w, h, color, thickness=2, r=10):
        overlay = frame.copy()
        cv2.rectangle(overlay, (x+r, y), (x+w-r, y+h), color, thickness)
        cv2.rectangle(overlay, (x, y+r), (x+w, y+h-r), color, thickness)
        cv2.ellipse(overlay, (x+r, y+r), (r,r), 180, 0, 90, color, thickness)
        cv2.ellipse(overlay, (x+w-r, y+r), (r,r), 270, 0, 90, color, thickness)
        cv2.ellipse(overlay, (x+r, y+h-r), (r,r), 90, 0, 90, color, thickness)
        cv2.ellipse(overlay, (x+w-r, y+h-r), (r,r), 0, 0, 90, color, thickness)
        frame[:] = overlay

    @staticmethod
    def draw_label(frame, x, y, text, color):
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y-th-6), (x+tw+6, y), color, -1)
        frame[:] = cv2.addWeighted(overlay, 0.6, frame, 0.4, 0)
        cv2.putText(frame, text, (x+3, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

    def draw_objects(self, frame, tracked_objects, detections, fps=None):
        for obj_id, det in tracked_objects:
            x, y, w, h = det[:4]
            color_obj = next((o for dx, dy, dw, dh, o in detections if dx==x and dy==y), None)
            if not color_obj:
                continue

            label = f"{color_obj.name} | ID:{obj_id}"
            self.draw_rectangle(frame, x, y, w, h, color_obj.draw_color)
            self.draw_label(frame, x, y, label, color_obj.draw_color)

            traj = self.tracker.get_trajectory(obj_id)
            for i in range(1, len(traj)):
                alpha = i / max(len(traj)-1,1)
                color = tuple([int(c*0.3 + c*0.7*alpha) for c in color_obj.draw_color])
                cv2.line(frame, traj[i-1], traj[i], color, 2)

            if len(traj) >= 2:
                start = traj[-2]
                end = traj[-1]
                cv2.arrowedLine(frame, start, end, color_obj.draw_color, 2, tipLength=0.3)

        cv2.putText(frame, f"Objects: {len(tracked_objects)}", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        if self.show_fps and fps is not None:
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        return frame

# =========================================================
# APP CONTROLLER
# =========================================================
class TrackerApp:
    def __init__(self, config):
        self.config = config
        self.camera = Camera(config)
        self.detector = ColorDetector([ColorObject(c["name"], c["lower"], c["upper"], c["bgr"]) for c in config.colors],
                                      min_area=config.min_contour_area)
        self.tracker = Tracker(max_lost=config.max_lost, max_history=config.max_history, match_dist=config.match_dist)
        self.draw_manager = DrawManager(self.tracker, show_fps=config.show_fps)

        self.frame_shared = None
        self.detections_shared = []
        self.tracked_shared = []
        self.frame_lock = threading.Lock()
        self.running = True
        self.det_interval = 1.0 / config.max_detection_fps

    def start(self):
        threading.Thread(target=self._detection_thread, daemon=True).start()
        self._drawing_thread()

    def _detection_thread(self):
        last_det_time = 0
        while self.running:
            now = time.time()
            if now - last_det_time < self.det_interval:
                time.sleep(0.005)
                continue
            last_det_time = now

            frame = self.camera.read()
            if frame is None:
                time.sleep(0.005)
                continue
            detections = self.detector.detect(frame)
            tracked = self.tracker.update([(x,y,w,h) for (x,y,w,h,obj) in detections])
            with self.frame_lock:
                self.frame_shared = frame
                self.detections_shared = detections
                self.tracked_shared = tracked

    def _drawing_thread(self):
        prev_time = time.time()
        fps = 0
        fps_count = 0
        fps_accum = 0
        fps_update_interval = 1.0

        while self.running:
            with self.frame_lock:
                if self.frame_shared is None:
                    time.sleep(0.005)
                    continue
                frame = self.frame_shared.copy()
                detections = self.detections_shared
                tracked = self.tracked_shared

            now = time.time()
            dt = now - prev_time
            prev_time = now
            fps_accum += 1 / dt
            fps_count += 1

            if fps_count >= fps_update_interval / dt:
                fps = fps_accum / fps_count
                fps_accum = 0
                fps_count = 0

            frame = self.draw_manager.draw_objects(frame, tracked, detections, fps=fps)
            cv2.imshow("Tracking + Vector", frame)

            if cv2.waitKey(1) == 27:
                self.running = False
                break

        self.camera.stop()
        cv2.destroyAllWindows()

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    config = ConfigCamera("config/config_camera.json")  # load từ file JSON
    app = TrackerApp(config)
    app.start()
