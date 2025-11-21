from collections import deque
import time
import math
import uuid
import threading


class Tracker:
    """
    Đơn vị theo dõi vật thể theo bounding box.

    Lưu trữ:
        id → [x, y, w, h, last_seen_timestamp, trajectory_deque]

    Các chức năng:
        - update(): gán ID cho box mới
        - giữ history vị trí (trajectory)
        - loại bỏ object mất dấu
        - trả về quỹ đạo (trajectory) theo TTL
    """

    def __init__(self, max_lost=15, max_history=20, match_dist=80.0):
        # Object map: id → [x, y, w, h, last_time, trajectory]
        self.objects = {}

        # Settings
        self.max_lost = max_lost        # thời gian tối đa bị mất dấu
        self.max_history = max_history  # số điểm lưu trong lịch sử
        self.match_dist = match_dist    # khoảng cách tối đa để match object

        # Thread-safety
        self.lock = threading.Lock()

    # ----------------------------------------------------------------------

    def update(self, boxes):
        """
        Nhận danh sách bounding box mới → trả về danh sách (id, box).

        boxes format: [(x, y, w, h), ...]
        """
        now = time.time()
        updated_ids = []

        with self.lock:
            for x, y, w, h in boxes:
                cx, cy = x + w // 2, y + h // 2   # tâm box

                best_id = None
                best_dist = float("inf")

                # Tìm object có vị trí gần nhất
                for obj_id, info in self.objects.items():
                    ox, oy, ow, oh, last_time, traj = info
                    ocx, ocy = ox + ow // 2, oy + oh // 2

                    dist = math.hypot(cx - ocx, cy - ocy)
                    if dist < best_dist and dist < self.match_dist:
                        best_dist = dist
                        best_id = obj_id

                # Tạo object mới nếu không khớp object cũ
                if best_id is None:
                    obj_id = str(uuid.uuid4())[:8]

                    self.objects[obj_id] = [
                        x, y, w, h,
                        now,
                        deque(maxlen=self.max_history)
                    ]
                    self.objects[obj_id][5].append((cx, cy, now))

                    updated_ids.append((obj_id, (x, y, w, h)))

                # Update object cũ
                else:
                    obj = self.objects[best_id]
                    obj[0], obj[1], obj[2], obj[3] = x, y, w, h
                    obj[4] = now
                    obj[5].append((cx, cy, now))

                    updated_ids.append((best_id, (x, y, w, h)))

            # Xoá object bị mất dấu quá lâu
            lost = [
                obj_id for obj_id, info in self.objects.items()
                if now - info[4] > self.max_lost
            ]
            for obj_id in lost:
                del self.objects[obj_id]

        return updated_ids

    # ----------------------------------------------------------------------

    def get_trajectory(self, obj_id, ttl=3.0):
        """
        Trả về quỹ đạo của object trong vòng ttl giây gần nhất.
        """
        now = time.time()

        with self.lock:
            if obj_id not in self.objects:
                return []

            traj = [
                (cx, cy)
                for cx, cy, t in self.objects[obj_id][5]
                if now - t <= ttl
            ]

        return traj
