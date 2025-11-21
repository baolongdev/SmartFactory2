import numpy as np


class ColorObject:
    """
    Model đại diện cho một màu cần detect.

    Bao gồm:
        - name (str)
        - lower (np.array)
        - upper (np.array)
        - bgr (tuple)
        - action_id (int) → cho conveyor
        - duration_ms (int) → thời gian chạy conveyor

        Thuộc tính runtime (cập nhật khi detect):
        - x, y, w, h: bounding box
    """

    def __init__(self, name, lower, upper, bgr, action_id=0, duration_ms=3000):
        self.name = name

        # Convert HSV to numpy arrays
        self.lower = np.array(lower, dtype=np.uint8)
        self.upper = np.array(upper, dtype=np.uint8)

        # Drawing color (BGR)
        self.bgr = tuple(int(c) for c in bgr)

        # Conveyor metadata
        self.action_id = int(action_id)
        self.duration_ms = int(duration_ms)

        # Detection runtime attributes
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0

    # ----------------------------------------------------------------------

    def to_dict(self):
        """
        Chuẩn hoá dữ liệu trả về cho FE hoặc logging.
        Dùng đồng nhất trong CameraPipeline.
        """
        return {
            "color_name": self.name,
            "bgr": list(self.bgr),
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "action_id": self.action_id,
            "duration_ms": self.duration_ms
        }

    # ----------------------------------------------------------------------

    def __repr__(self):
        return (
            f"<ColorObject name={self.name}, "
            f"HSV={self.lower.tolist()}-{self.upper.tolist()}, "
            f"BGR={self.bgr}, action_id={self.action_id}, duration={self.duration_ms}ms>"
        )
