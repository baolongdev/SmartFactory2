import os
import json

class ColorConfig:
    DEFAULT = [
        { "name": "red",    "bgr": [0, 0, 255],     "lower": [0, 100, 80],    "upper": [10, 255, 255],  "duration_ms": 1000, "servo_id": 1 },
        { "name": "orange", "bgr": [0, 165, 255],   "lower": [10, 100, 100],  "upper": [20, 255, 255],  "duration_ms": 2000, "servo_id": 0 },
        { "name": "yellow", "bgr": [0, 255, 255],   "lower": [22, 100, 100],  "upper": [33, 255, 255],  "duration_ms": 3000, "servo_id": 0 },
        { "name": "green",  "bgr": [0, 255, 0],     "lower": [35, 80, 80],    "upper": [85, 255, 255],  "duration_ms": 2000, "servo_id": 0 },
        { "name": "blue",   "bgr": [255, 0, 0],     "lower": [90, 70, 70],    "upper": [130, 255, 255], "duration_ms": 2000, "servo_id": 2 },
        { "name": "purple", "bgr": [255, 0, 255],   "lower": [135, 60, 60],   "upper": [155, 255, 255], "duration_ms": 2000, "servo_id": 0 },
        { "name": "pink",   "bgr": [203, 192, 255], "lower": [155, 70, 100],  "upper": [175, 255, 255], "duration_ms": 2000, "servo_id": 0 },
    ]

    def __init__(self, path="config/colors.json"):
        self.path = path
        self.colors = self._load_colors()
        self.colors = self._fill_missing_fields(self.colors)

    def _load_colors(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.DEFAULT, f, indent=4)
            return self.DEFAULT
        with open(self.path, "r") as f:
            return json.load(f)

    def reload(self):
        self.colors = self._fill_missing_fields(self._load_colors())

    def _fill_missing_fields(self, list_in):
        output = []
        for item in list_in:
            base = next((d for d in self.DEFAULT if d["name"] == item["name"]), None)
            if not base:
                continue
            merged = {
                "name":        item["name"],
                "bgr":         item.get("bgr",         base["bgr"]),
                "lower":       item.get("lower",       base["lower"]),
                "upper":       item.get("upper",       base["upper"]),
                "duration_ms": item.get("duration_ms", base["duration_ms"]),
                "servo_id":    item.get("servo_id",    base["servo_id"]),
            }
            output.append(merged)
        return output

    def save(self, colors):
        with open(self.path, "w") as f:
            json.dump(colors, f, indent=4)
        self.colors = self._fill_missing_fields(colors)
