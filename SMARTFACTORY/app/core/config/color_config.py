import os
import json
from .validator import ConfigValidator

class ColorConfig:
    DEFAULT = [
        {
            "name": "red",
            "bgr": [0, 0, 255],
            "lower": [0, 120, 70],
            "upper": [10, 255, 255],
            "action_id": 3,
            "duration_ms": 8000
        },
        {
            "name": "green",
            "bgr": [0, 255, 0],
            "lower": [36, 50, 70],
            "upper": [89, 255, 255],
            "action_id": 2,
            "duration_ms": 6000
        },
        {
            "name": "blue",
            "bgr": [255, 0, 0],
            "lower": [94, 80, 2],
            "upper": [126, 255, 255],
            "action_id": 1,
            "duration_ms": 4000
        },

        # ⭐ NEW COLORS ADDED ⭐
        {
            "name": "yellow",
            "bgr": [0, 255, 255],
            "lower": [20, 100, 100],
            "upper": [35, 255, 255],
            "action_id": 4,
            "duration_ms": 5000
        },
        {
            "name": "orange",
            "bgr": [0, 165, 255],
            "lower": [10, 100, 100],
            "upper": [20, 255, 255],
            "action_id": 5,
            "duration_ms": 5000
        },
        {
            "name": "purple",
            "bgr": [255, 0, 255],
            "lower": [129, 50, 70],
            "upper": [158, 255, 255],
            "action_id": 6,
            "duration_ms": 6000
        },
        {
            "name": "pink",
            "bgr": [203, 192, 255],
            "lower": [145, 80, 80],
            "upper": [170, 255, 255],
            "action_id": 7,
            "duration_ms": 7000
        }
    ]


    def __init__(self, path="config/colors.json"):
        self.path = path
        self.colors = self._load_colors()
        self.colors = self._fill_missing_fields(self.colors)

    # Load FE JSON (may be missing HSV)
    def _load_colors(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.DEFAULT, f, indent=4)
            return self.DEFAULT

        with open(self.path, "r") as f:
            return json.load(f)
        
    def reload(self):
        """Reload từ file & fill lại missing fields."""
        self.colors = self._fill_missing_fields(self._load_colors())


    # 🔥 Tự động bổ sung HSV/BGR/action/duration theo name
    def _fill_missing_fields(self, list_in):
        output = []
        for item in list_in:
            base = next((d for d in self.DEFAULT if d["name"] == item["name"]), None)
            if not base:
                continue
            
            merged = {
                "name": item["name"],
                "bgr": base["bgr"],
                "lower": base["lower"],
                "upper": base["upper"],
                "action_id": item.get("action_id", base["action_id"]),
                "duration_ms": item.get("duration_ms", base["duration_ms"])
            }
            output.append(merged)
        return output

    def save(self, colors):
        with open(self.path, "w") as f:
            json.dump(colors, f, indent=4)
        self.colors = self._fill_missing_fields(colors)
