import cv2
import numpy as np
from app.logging_config import init_logger

logger = init_logger("DrawManager")


class DrawManager:
    """
    Quản lý việc vẽ bounding box, nhãn, trajectory lên frame.

    - overlay riêng (alpha blending) → không làm hỏng frame gốc
    - trajectory (đường chuyển động)
    - gán ID + label
    - hỗ trợ hiển thị FPS
    """

    def __init__(self, tracker, show_fps=True, alpha=0.4, trajectory_ttl=3.0):
        self.tracker = tracker
        self.show_fps = show_fps
        self.alpha = alpha
        self.traj_ttl = trajectory_ttl
        self.overlay = None

    # ----------------------------------------------------------------------

    def _ensure_overlay(self, frame):
        """Reset overlay mỗi frame nếu kích thước không khớp."""
        if self.overlay is None or self.overlay.shape != frame.shape:
            self.overlay = np.zeros_like(frame)
        else:
            self.overlay[:] = 0

    # ----------------------------------------------------------------------

    def _draw_label(self, label, x, y, color):
        """Vẽ label nền đen + chữ trắng."""
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(self.overlay, (x, y - th - 8), (x + tw + 6, y), (0, 0, 0), -1)
        cv2.putText(
            self.overlay, label, (x + 3, y - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )

    # ----------------------------------------------------------------------

    def _draw_trajectory(self, obj_id, color):
        """Vẽ đường đi + mũi tên hướng di chuyển."""
        traj = self.tracker.get_trajectory(obj_id, self.traj_ttl)

        if len(traj) < 2:
            return

        for i in range(1, len(traj)):
            cv2.line(self.overlay, traj[i - 1], traj[i], color, 2)

        # Mũi tên ở cuối đường đi
        cv2.arrowedLine(self.overlay, traj[-2], traj[-1], color, 2, tipLength=0.3)

    # ----------------------------------------------------------------------

    def render(self, frame, tracked, detections, fps=None):
        """Vẽ tất cả thông tin lên frame."""
        if frame is None:
            return None

        self._ensure_overlay(frame)

        try:
            # ===================== VẼ ĐỐI TƯỢNG ======================
            for obj_id, box in tracked:
                x, y, w, h = box
                cx, cy = x + w // 2, y + h // 2

                # Ghép với object màu (ColorObject)
                color_obj = None
                for dx, dy, dw, dh, obj in detections:
                    dcx, dcy = dx + dw // 2, dy + dh // 2
                    if abs(cx - dcx) < 5 and abs(cy - dcy) < 5:
                        color_obj = obj
                        break

                if color_obj is None:
                    continue

                color = tuple(int(c) for c in color_obj.bgr)
                label = f"{color_obj.name} | ID:{obj_id}"

                # Bounding box
                cv2.rectangle(self.overlay, (x, y), (x + w, y + h), color, 2)

                # Label
                self._draw_label(label, x, y, color)

                # Trajectory
                self._draw_trajectory(obj_id, color)


            # ===================== VẼ FPS ======================
            if self.show_fps and fps:
                text = f"FPS: {fps:.1f}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.45
                thickness = 1

                # Lấy kích thước chữ
                (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)

                padding = 5

                # Góc phải trên
                frame_h, frame_w = frame.shape[:2]
                x = frame_w - tw - padding
                y = th + padding + 10

                # Hộp nền trắng (KHÔNG VIỀN)
                cv2.rectangle(
                    frame,
                    (x - padding, y - th - padding),
                    (x + tw + padding, y + padding),
                    (255, 255, 255),   # trắng
                    -1                 # filled
                )

                # Text màu đen
                cv2.putText(
                    frame,
                    text,
                    (x, y),
                    font,
                    font_scale,
                    (0, 0, 0),         # đen
                    thickness
                )




            # ===================== OVERLAY ======================
            cv2.addWeighted(self.overlay, self.alpha, frame, 1 - self.alpha, 0, dst=frame)

        except Exception as e:
            logger.exception(f"DrawManager render error: {e}")

        return frame
