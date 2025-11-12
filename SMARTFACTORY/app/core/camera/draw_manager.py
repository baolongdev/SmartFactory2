import cv2
import numpy as np
from app.logging_config import init_logger

logger = init_logger("DrawManager")

class DrawManager:
    def __init__(self, tracker, show_fps=True, alpha=0.8, traj_ttl=3.0):
        self.tracker = tracker
        self.show_fps = show_fps
        self.alpha = alpha
        self.traj_ttl = traj_ttl
        self.overlay = None

    def render(self, frame, tracked, detections, fps=None):
        if frame is None:
            return None
        if self.overlay is None or self.overlay.shape != frame.shape:
            self.overlay = np.zeros_like(frame)
        self.overlay[:] = 0

        try:
            for obj_id, det in tracked:
                x, y, w, h = det[:4]
                cx, cy = x+w//2, y+h//2
                color_obj = None
                for dx, dy, dw, dh, o in detections:
                    dcx, dcy = dx+dw//2, dy+dh//2
                    if abs(cx-dcx)<5 and abs(cy-dcy)<5:
                        color_obj = o
                        break
                if color_obj is None:
                    continue
                bgr = tuple(int(c) for c in color_obj.bgr)
                label = f"{color_obj.name}|ID:{obj_id}"
                cv2.rectangle(self.overlay, (x, y), (x+w, y+h), bgr, 2)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(self.overlay, (x, y-th-8), (x+tw+6, y), (0,0,0), -1)
                cv2.putText(self.overlay, label, (x+3, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                traj = self.tracker.get_trajectory(obj_id, self.traj_ttl)
                for i in range(1, len(traj)):
                    cv2.line(self.overlay, traj[i-1], traj[i], bgr, 2)
                if len(traj)>=2:
                    cv2.arrowedLine(self.overlay, traj[-2], traj[-1], bgr, 2, tipLength=0.3)
            cv2.addWeighted(self.overlay, self.alpha, frame, 1-self.alpha, 0, dst=frame)
        except Exception as e:
            logger.exception(f"Render error: {e}")
        return frame
