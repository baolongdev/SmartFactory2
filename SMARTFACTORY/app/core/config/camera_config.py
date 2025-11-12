from .loader import ConfigLoader
from .validator import ConfigValidator

class CameraConfig:
    DEFAULT = {
        "camera": {"src":0, "width":640, "height":480, "fps":30},
        "detection": {"min_contour_area":1500, "max_detection_fps":30},
        "tracker": {"max_lost":15, "max_history":20, "match_dist":80},
        "drawing": {"show_fps": True},
        "colors": [
            {"name":"Red", "lower":[0,120,70], "upper":[10,255,255], "bgr":[0,0,255]},
            {"name":"Green", "lower":[36,50,70], "upper":[89,255,255], "bgr":[0,255,0]},
            {"name":"Blue", "lower":[94,80,2], "upper":[126,255,255], "bgr":[255,0,0]}
        ]
    }

    def __init__(self, path="config/config_camera.json"):
        cfg = ConfigLoader.load(path, default=self.DEFAULT)
        cam = cfg.get("camera", {})
        det = cfg.get("detection", {})
        trk = cfg.get("tracker", {})
        draw = cfg.get("drawing", {})

        self.src = ConfigValidator.require(cam, "src", 0)
        self.width = ConfigValidator.require(cam, "width", 640)
        self.height = ConfigValidator.require(cam, "height", 480)
        self.fps = ConfigValidator.require(cam, "fps", 30)

        self.min_area = ConfigValidator.require(det, "min_contour_area", 1500)
        self.max_det_fps = ConfigValidator.require(det, "max_detection_fps", 30)

        self.max_lost = ConfigValidator.require(trk, "max_lost", 15)
        self.max_history = ConfigValidator.require(trk, "max_history", 20)
        self.match_dist = ConfigValidator.require(trk, "match_dist", 80)

        self.show_fps = ConfigValidator.require(draw, "show_fps", True)
        self.colors = cfg.get("colors", [])
