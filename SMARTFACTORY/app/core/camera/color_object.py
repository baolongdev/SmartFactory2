import numpy as np

class ColorObject:
    """
    Model for a color to detect.
    Attributes:
        name: str
        hsv_lower: np.array [H,S,V]
        hsv_upper: np.array [H,S,V]
        bgr: tuple (B,G,R) for drawing
        x,y,w,h: bounding box (updated during detection)
    """
    def __init__(self, name, hsv_lower, hsv_upper, bgr):
        self.name = name
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
        self.bgr = tuple(int(c) for c in bgr)
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0

    def to_dict(self):
        return {
            "color_name": self.name,
            "bgr": list(self.bgr),
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h
        }

    def __repr__(self):
        return f"<ColorObject {self.name}, HSV:{self.hsv_lower}-{self.hsv_upper}, BGR:{self.bgr}>"
