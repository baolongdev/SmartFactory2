import cv2
import numpy as np


class DrawManager:
    """
    Industrial-style annotation renderer.

    Improvements over original:
    ────────────────────────────────────────────────────────────────────
    1. Corner-bracket boxes (drawn on frame — full opacity, sharp edges)
       The four L-shaped corners replace a full rectangle, giving a
       cleaner industrial look.  Coasting objects are drawn dimmed.

    2. Pill label with colour chip
       "[color chip] name#ID" layout.  Drawn on overlay (blended) so
       labels don't obscure the scene.

    3. Fading trajectory
       Trail segments fade in both colour intensity and line thickness
       as they age (uses the age_frac returned by tracker.get_trajectory).
       Arrow at the newest point shows movement direction.

    4. Colour cache for coasting objects
       When an object is coasting (not in current detections), DrawManager
       uses the last known colour via _color_cache[obj_id].

    5. HUD panel (top-right corner)
       Shows FPS + active object count in a compact dark box.

    6. Two rendering planes
       - Brackets → frame directly  (crisp, full opacity)
       - Labels + trails → overlay  (blended at self.alpha)
       HUD is drawn after blending so it stays sharp.
    """

    _FONT       = cv2.FONT_HERSHEY_SIMPLEX
    _FONT_SCALE = 0.45
    _THICKNESS  = 1

    def __init__(self, tracker, show_fps: bool = True,
                 alpha: float = 0.4, trajectory_ttl: float = 3.0):
        self.tracker  = tracker
        self.show_fps = show_fps
        self.alpha    = alpha
        self.traj_ttl = trajectory_ttl
        self.overlay  = None

        # Cache last known ColorObject per tracked ID (for coasting objects)
        self._color_cache: dict = {}

    # ── Overlay management ────────────────────────────────────────────────────

    def _ensure_overlay(self, frame: np.ndarray) -> None:
        if self.overlay is None or self.overlay.shape != frame.shape:
            self.overlay = np.zeros_like(frame)
        else:
            self.overlay.fill(0)

    # ── Corner bracket box ────────────────────────────────────────────────────

    @staticmethod
    def _draw_corner_box(surface: np.ndarray,
                         x: int, y: int, w: int, h: int,
                         color: tuple,
                         thickness: int = 2,
                         ratio: float = 0.22) -> None:
        """Draw only the four L-shaped corners of a bounding box."""
        lx = max(8, int(w * ratio))
        ly = max(8, int(h * ratio))
        corners = [
            # top-left
            ((x,       y + ly), (x,   y),   (x + lx, y  )),
            # top-right
            ((x+w-lx,  y     ), (x+w, y),   (x+w,    y + ly)),
            # bottom-left
            ((x,       y+h-ly), (x,   y+h), (x + lx, y+h)),
            # bottom-right
            ((x+w-lx,  y+h   ), (x+w, y+h), (x+w,    y+h-ly)),
        ]
        for p0, p1, p2 in corners:
            cv2.line(surface, p0, p1, color, thickness, cv2.LINE_AA)
            cv2.line(surface, p1, p2, color, thickness, cv2.LINE_AA)

    # ── Pill label ────────────────────────────────────────────────────────────

    def _draw_label(self, x: int, y: int,
                    color: tuple, name: str, obj_id: str,
                    coasting: bool) -> None:
        label = f"{name} #{obj_id}"
        if coasting:
            label += " ·"    # subtle indicator for coasting state

        (tw, th), _ = cv2.getTextSize(
            label, self._FONT, self._FONT_SCALE, self._THICKNESS
        )
        pad    = 4
        chip_w = 8
        bx1 = x
        bx2 = x + chip_w + tw + pad * 3
        by1 = max(0, y - th - pad * 2)
        by2 = y

        # Dark background
        bg = (25, 25, 25) if not coasting else (50, 50, 50)
        cv2.rectangle(self.overlay, (bx1, by1), (bx2, by2), bg, -1)

        # Colour chip (left stripe)
        chip_color = color if not coasting else tuple(c // 2 for c in color)
        cv2.rectangle(self.overlay, (bx1, by1), (bx1 + chip_w, by2), chip_color, -1)

        # Label text
        text_color = (225, 225, 225) if not coasting else (140, 140, 140)
        cv2.putText(
            self.overlay, label,
            (bx1 + chip_w + pad, by2 - pad),
            self._FONT, self._FONT_SCALE, text_color,
            self._THICKNESS, cv2.LINE_AA,
        )

    # ── Fading trajectory ─────────────────────────────────────────────────────

    def _draw_trajectory(self, obj_id: str, color: tuple) -> None:
        """
        Draw motion trail with opacity and thickness that fade with age.
        age_frac=0.0 → newest (bright, thick)
        age_frac=1.0 → oldest (dim, thin)
        """
        pts = self.tracker.get_trajectory(obj_id, self.traj_ttl)
        # pts: [(cx, cy, age_frac), ...]  oldest-first in deque order
        if len(pts) < 2:
            return

        for i in range(1, len(pts)):
            x0, y0, a0 = pts[i - 1]
            x1, y1, a1 = pts[i]
            # brightness: average age of segment (0=newest→1.0, 1=oldest→0.0)
            bright = 1.0 - (a0 + a1) * 0.5
            seg_color = tuple(max(0, int(c * bright)) for c in color)
            thickness = max(1, round(3 * bright))
            cv2.line(self.overlay, (x0, y0), (x1, y1),
                     seg_color, thickness, cv2.LINE_AA)

        # Arrow at newest end
        x0, y0, _ = pts[-2]
        x1, y1, _ = pts[-1]
        cv2.arrowedLine(self.overlay, (x0, y0), (x1, y1),
                        color, 2, cv2.LINE_AA, tipLength=0.35)

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self, frame: np.ndarray,
                  fps: float, obj_count: int) -> None:
        fh, fw = frame.shape[:2]

        lines = []
        if self.show_fps and fps:
            lines.append(f"FPS  {fps:4.1f}")
        lines.append(f"OBJ  {obj_count:4d}")

        pad    = 5
        lh     = 15   # px per line
        box_w  = 76
        box_h  = lh * len(lines) + pad * 2
        bx     = fw - box_w - pad
        by     = pad

        # Background + border
        cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h),
                      (18, 18, 18), -1)
        cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h),
                      (70, 70, 70), 1)

        for i, line in enumerate(lines):
            ry = by + pad + lh * i + lh - 3
            cv2.putText(frame, line,
                        (bx + 6, ry),
                        self._FONT, 0.38, (190, 190, 190),
                        1, cv2.LINE_AA)

    # ── Main render ───────────────────────────────────────────────────────────

    def render(self, frame: np.ndarray,
               tracked: list, detections: list,
               fps: float = None) -> np.ndarray:
        """
        Annotate frame with bounding boxes, labels, and trajectories.

        Parameters
        ----------
        frame      : BGR image (modified in-place)
        tracked    : [(id, (x,y,w,h), coasting), ...] from Tracker.update()
        detections : [(x,y,w,h, ColorObject), ...]   from ColorDetector.detect()
        fps        : current processing FPS (optional)

        Returns
        -------
        Annotated BGR frame.
        """
        if frame is None:
            return None

        self._ensure_overlay(frame)

        try:
            # ── Build centre → ColorObject map (O(1) lookup) ─────────────
            det_map: dict = {}
            for dx, dy, dw, dh, cobj in detections:
                det_map[(dx + dw // 2, dy + dh // 2)] = cobj

            active_count = 0

            for item in tracked:
                obj_id, (x, y, w, h), coasting = item
                cx, cy = x + w // 2, y + h // 2

                # ── Resolve ColorObject ───────────────────────────────────
                if not coasting:
                    # Active: exact centre match (tracker stores detection box)
                    color_obj = det_map.get((cx, cy))
                    if color_obj is None:
                        # Rare rounding difference — fall back to closest
                        best_d = float("inf")
                        for (dcx, dcy), obj in det_map.items():
                            d = abs(cx - dcx) + abs(cy - dcy)
                            if d < best_d:
                                best_d = d
                                color_obj = obj
                    # Cache for future coasting frames
                    if color_obj is not None:
                        self._color_cache[obj_id] = color_obj
                else:
                    # Coasting: no detection — use cache
                    color_obj = self._color_cache.get(obj_id)

                if color_obj is None:
                    continue

                if not coasting:
                    active_count += 1

                color = tuple(int(c) for c in color_obj.bgr)

                # ── Corner brackets on frame (crisp / full opacity) ───────
                box_color = color if not coasting else tuple(c // 3 for c in color)
                box_thick = 2   if not coasting else 1
                self._draw_corner_box(frame, x, y, w, h,
                                      box_color, box_thick)

                # ── Label + trajectory on overlay (blended) ───────────────
                self._draw_label(x, y, color, color_obj.name,
                                 obj_id, coasting)
                if not coasting:
                    self._draw_trajectory(obj_id, color)

            # ── Blend overlay ─────────────────────────────────────────────
            cv2.addWeighted(self.overlay, self.alpha,
                            frame, 1.0 - self.alpha, 0, dst=frame)

            # ── HUD (drawn after blend — stays sharp) ────────────────────
            self._draw_hud(frame, fps, active_count)

            # ── Purge cache entries for evicted objects ───────────────────
            live_ids = {item[0] for item in tracked}
            stale    = [k for k in self._color_cache if k not in live_ids]
            for k in stale:
                del self._color_cache[k]

        except Exception:
            pass   # never crash the video loop

        return frame
