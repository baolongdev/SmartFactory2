from .camera_config import CameraConfig
from .mqtt_config import MQTTConfig
from .color_config import ColorConfig
from .loader import ConfigLoader
from .validator import ConfigValidator


class AppConfig:
    DEFAULT = {
        "debug": True,
        "camera_config": "config/config_camera.json",
        "mqtt_config": "config/config_mqtt.json",
        "color_config": "config/colors.json"
    }

    def __init__(self, path="config/config_app.json"):
        """
        Load main app config (app-level).
        Đồng thời load các config con:
        - CameraConfig
        - MQTTConfig
        - ColorConfig
        """
        cfg = ConfigLoader.load(path, default=self.DEFAULT)

        # --- APP LEVEL ---
        self.debug = ConfigValidator.require(cfg, "debug", True)

        # --- CHILD CONFIG PATHS ---
        camera_path = cfg.get("camera_config", self.DEFAULT["camera_config"])
        mqtt_path = cfg.get("mqtt_config", self.DEFAULT["mqtt_config"])
        color_path = cfg.get("color_config", self.DEFAULT["color_config"])

        # --- CHILD CONFIG OBJECTS ---
        self.camera_config = CameraConfig(camera_path)
        self.mqtt_config = MQTTConfig(mqtt_path)
        self.color_config = ColorConfig(color_path)
