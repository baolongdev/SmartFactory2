from collections import deque
import time, math, uuid
import threading

class Tracker:
    def __init__(self, max_lost=15, max_history=20, match_dist=80.0):
        self.objects = {}  # id -> [x,y,w,h,last_time,trajectory]
        self.max_lost = max_lost
        self.max_history = max_history
        self.match_dist = match_dist
        self.lock = threading.Lock()

    def update(self, boxes):
        now = time.time()
        updated_ids = []

        with self.lock:
            for box in boxes:
                x, y, w, h = box
                cx, cy = x+w//2, y+h//2

                best_id = None
                best_dist = float('inf')
                for obj_id, info in self.objects.items():
                    ox, oy, ow, oh, last_time, traj = info
                    ocx, ocy = ox+ow//2, oy+oh//2
                    dist = math.hypot(cx-ocx, cy-ocy)
                    if dist < best_dist and dist < self.match_dist:
                        best_dist = dist
                        best_id = obj_id

                if best_id is None:
                    obj_id = str(uuid.uuid4())[:8]
                    self.objects[obj_id] = [x, y, w, h, now, deque(maxlen=self.max_history)]
                    self.objects[obj_id][5].append((cx, cy, now))
                    updated_ids.append((obj_id, box))
                else:
                    self.objects[best_id][:4] = [x, y, w, h]
                    self.objects[best_id][4] = now
                    self.objects[best_id][5].append((cx, cy, now))
                    updated_ids.append((best_id, box))

            # Remove lost
            lost_ids = [obj_id for obj_id, info in self.objects.items() if now-info[4] > self.max_lost]
            for obj_id in lost_ids:
                del self.objects[obj_id]

        return updated_ids

    def get_trajectory(self, obj_id, ttl=3.0):
        now = time.time()
        with self.lock:
            if obj_id in self.objects:
                traj = [(cx, cy) for cx, cy, t in self.objects[obj_id][5] if now-t <= ttl]
                return traj
        return []
