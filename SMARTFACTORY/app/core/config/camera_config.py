from .loader import ConfigLoader
from .validator import ConfigValidator


class CameraConfig:
    DEFAULT = {
        "camera": {
            "src": 0,
            "width": 640,
            "height": 480,
            "fps": 30
        },
        "detection": {
            "min_contour_area": 1500,
            "max_detection_fps": 30
        },
        "tracker": {
            "max_lost": 15,
            "max_history": 20,
            "match_dist": 80
        },
        "drawing": {
            "show_fps": True
        }
        # Colors are loaded separately via ColorConfig
    }

    def __init__(self, path="config/config_camera.json"):
        cfg = ConfigLoader.load(path, default=self.DEFAULT)

        # --- CAMERA ---
        cam = cfg.get("camera", {})
        self.src = ConfigValidator.require(cam, "src", self.DEFAULT["camera"]["src"])
        self.width = ConfigValidator.require(cam, "width", self.DEFAULT["camera"]["width"])
        self.height = ConfigValidator.require(cam, "height", self.DEFAULT["camera"]["height"])
        self.fps = ConfigValidator.require(cam, "fps", self.DEFAULT["camera"]["fps"])

        # --- DETECTION ---
        det = cfg.get("detection", {})
        self.min_area = ConfigValidator.require(det, "min_contour_area", self.DEFAULT["detection"]["min_contour_area"])
        self.max_det_fps = ConfigValidator.require(det, "max_detection_fps", self.DEFAULT["detection"]["max_detection_fps"])

        # --- TRACKER ---
        trk = cfg.get("tracker", {})
        self.max_lost = ConfigValidator.require(trk, "max_lost", self.DEFAULT["tracker"]["max_lost"])
        self.max_history = ConfigValidator.require(trk, "max_history", self.DEFAULT["tracker"]["max_history"])
        self.match_dist = ConfigValidator.require(trk, "match_dist", self.DEFAULT["tracker"]["match_dist"])

        # --- DRAWING ---
        draw = cfg.get("drawing", {})
        self.show_fps = ConfigValidator.require(draw, "show_fps", self.DEFAULT["drawing"]["show_fps"])

        # --- COLORS (always empty here, loaded via ColorConfig) ---
        self.colors = []
