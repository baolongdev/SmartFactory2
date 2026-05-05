from collections import deque
import time
import math
import threading


class Tracker:
    """
    Centroid-based object tracker with trajectory history.

    Improvements over original:
    ────────────────────────────────────────────────────────────────────
    1. Greedy matching with exclusion
       Each detection can match AT MOST one tracked object and vice-versa.
       Prevents two detections from "stealing" the same tracked ID.

    2. Adaptive match threshold
       Threshold scales with object size: max(match_dist, √(w·h) × 0.4).
       Small objects get a tight window; large objects tolerate more movement.

    3. Coasting (temporal smoothing)
       Objects not detected this frame are flagged as coasting=True and
       kept at their last known position.  They appear in the returned list
       until they exceed max_lost seconds — eliminating 1-2 frame flicker.

    4. Structured object record (dict, not list)
       Easier to extend and read.  Adds `frames` lifetime counter.

    5. get_trajectory returns age fractions
       Each point carries `age_frac` (0.0=newest … 1.0=oldest within TTL)
       so DrawManager can render fading trails without extra time calls.
    """

    def __init__(self, max_lost: float = 15.0, max_history: int = 30,
                 match_dist: float = 80.0):
        # id → { box, last_seen, traj, frames, coasting }
        self.objects:    dict  = {}
        self.max_lost    = max_lost
        self.max_history = max_history
        self.match_dist  = match_dist

        self._next_id: int = 0
        self.lock = threading.Lock()

    # ── ID generator ─────────────────────────────────────────────────────────

    def _new_id(self) -> str:
        oid = self._next_id
        self._next_id += 1
        return str(oid)

    # ── Adaptive distance threshold ───────────────────────────────────────────

    def _adapt(self, w: int, h: int) -> float:
        """Return match threshold scaled to object size."""
        return max(self.match_dist, math.sqrt(w * h) * 0.4)

    # ── Main update ───────────────────────────────────────────────────────────

    def update(self, boxes: list) -> list:
        """
        Match incoming detections to tracked objects.

        Parameters
        ----------
        boxes : [(x, y, w, h), ...]   — this frame's detections

        Returns
        -------
        [(id, (x, y, w, h), coasting), ...]
            coasting=False → matched to a detection this frame
            coasting=True  → no detection found; using last known position
        """
        now = time.time()

        with self.lock:

            # ── Phase 1: greedy matching with exclusion ───────────────────
            used_track_ids = set()   # tracks already claimed
            assignments    = {}      # box_idx → track_id

            for box_idx, (x, y, w, h) in enumerate(boxes):
                cx, cy = x + w // 2, y + h // 2
                thresh = self._adapt(w, h)

                best_id   = None
                best_dist = float("inf")

                for obj_id, obj in self.objects.items():
                    if obj_id in used_track_ids:
                        continue
                    ox, oy, ow, oh = obj["box"]
                    d = math.hypot(cx - (ox + ow // 2),
                                   cy - (oy + oh // 2))
                    if d < best_dist and d < thresh:
                        best_dist = d
                        best_id   = obj_id

                if best_id is not None:
                    assignments[box_idx] = best_id
                    used_track_ids.add(best_id)

            # ── Phase 2: apply matches / create new objects ───────────────
            result = []

            for box_idx, (x, y, w, h) in enumerate(boxes):
                cx, cy = x + w // 2, y + h // 2

                if box_idx in assignments:
                    obj_id = assignments[box_idx]
                    obj    = self.objects[obj_id]
                    obj["box"]       = [x, y, w, h]
                    obj["last_seen"] = now
                    obj["frames"]   += 1
                    obj["coasting"]  = False
                    obj["traj"].append((cx, cy, now))
                else:
                    obj_id = self._new_id()
                    traj   = deque(maxlen=self.max_history)
                    traj.append((cx, cy, now))
                    self.objects[obj_id] = {
                        "box":       [x, y, w, h],
                        "last_seen": now,
                        "traj":      traj,
                        "frames":    1,
                        "coasting":  False,
                    }
                    # Mark new object so Phase 3 doesn't coast it immediately
                    used_track_ids.add(obj_id)

                result.append((obj_id, (x, y, w, h), False))

            # ── Phase 3: coast unmatched objects ─────────────────────────
            for obj_id, obj in self.objects.items():
                if obj_id in used_track_ids:
                    continue          # already in result
                obj["coasting"] = True
                x, y, w, h = obj["box"]
                result.append((obj_id, (x, y, w, h), True))

            # ── Phase 4: evict objects silent too long ────────────────────
            stale = [oid for oid, obj in self.objects.items()
                     if now - obj["last_seen"] > self.max_lost]
            for oid in stale:
                del self.objects[oid]

        return result

    # ── Hard limit ───────────────────────────────────────────────────────────

    def trim(self, max_keep: int) -> None:
        """
        Enforce a hard object-count limit after update().

        1. Evict all coasting objects immediately (no more ghost trails).
        2. If still more than max_keep active objects, keep only the ones
           tracked the longest (highest frame count = most stable track).

        Call this right after update() when max_objects > 0 so DrawManager
        never receives more than max_keep entries.
        """
        with self.lock:
            # Step 1 — drop all coasting objects
            coasting_ids = [oid for oid, obj in self.objects.items()
                            if obj["coasting"]]
            for oid in coasting_ids:
                del self.objects[oid]

            # Step 2 — if still over limit, evict least-stable tracks
            if len(self.objects) > max_keep:
                sorted_ids = sorted(
                    self.objects,
                    key=lambda oid: self.objects[oid]["frames"],
                    reverse=True,
                )
                for oid in sorted_ids[max_keep:]:
                    del self.objects[oid]

    # ── Trajectory query ──────────────────────────────────────────────────────

    def get_trajectory(self, obj_id: str, ttl: float = 3.0) -> list:
        """
        Return trajectory points within the last `ttl` seconds.

        Returns
        -------
        [(cx, cy, age_frac), ...]
            age_frac = 0.0  → newest point
            age_frac = 1.0  → oldest point still within TTL
        """
        now = time.time()
        with self.lock:
            obj = self.objects.get(obj_id)
            if obj is None:
                return []
            pts = []
            for cx, cy, t in obj["traj"]:
                age = now - t
                if age <= ttl:
                    pts.append((cx, cy, age / ttl))
            return pts

    # ── Lifetime query ────────────────────────────────────────────────────────

    def get_frames(self, obj_id: str) -> int:
        """Return how many frames this object has been continuously tracked."""
        with self.lock:
            return self.objects.get(obj_id, {}).get("frames", 0)
