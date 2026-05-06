import numpy as np


class ColorObject:
    """
    Đại diện cho một màu cần detect.
    - name, lower/upper (HSV), bgr: định nghĩa màu
    - duration_ms: thời gian chạy conveyor khi phát hiện
    - servo_id: 0=none, 1=servo1, 2=servo2
    - x, y, w, h: bounding box (runtime)
    """

    def __init__(self, name, lower, upper, bgr, duration_ms=1000, servo_id=0):
        self.name        = name
        self.lower       = np.array(lower, dtype=np.uint8)
        self.upper       = np.array(upper, dtype=np.uint8)
        self.bgr         = tuple(int(c) for c in bgr)
        self.duration_ms = int(duration_ms)
        self.servo_id    = int(servo_id)
        self.x = self.y = self.w = self.h = 0

    def to_dict(self):
        return {
            "color_name":  self.name,
            "bgr":         list(self.bgr),
            "x":           self.x,
            "y":           self.y,
            "w":           self.w,
            "h":           self.h,
            "duration_ms": self.duration_ms,
            "servo_id":    self.servo_id,
        }

    def __repr__(self):
        return (
            f"<ColorObject name={self.name}, "
            f"HSV={self.lower.tolist()}-{self.upper.tolist()}, "
            f"BGR={self.bgr}, duration={self.duration_ms}ms, servo={self.servo_id}>"
        )
