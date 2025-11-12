from .camera_config import CameraConfig
from .mqtt_config import MQTTConfig
from .loader import ConfigLoader
from .validator import ConfigValidator

class AppConfig:
    DEFAULT = {
        "debug": True,
        "camera_config": "config/config_camera.json",
        "mqtt_config": "config/config_mqtt.json"
    }

    def __init__(self, path="config/config_app.json"):
        """
        Load application config. Nếu file không tồn tại, dùng DEFAULT.
        Đồng thời khởi tạo các config con: CameraConfig và MQTTConfig.
        """
        cfg = ConfigLoader.load(path, default=self.DEFAULT)

        # App-level
        self.debug = ConfigValidator.require(cfg, "debug", True)

        # Child configs
        camera_path = cfg.get("camera_config", self.DEFAULT["camera_config"])
        mqtt_path = cfg.get("mqtt_config", self.DEFAULT["mqtt_config"])

        self.camera_config = CameraConfig(camera_path)
        self.mqtt_config = MQTTConfig(mqtt_path)
