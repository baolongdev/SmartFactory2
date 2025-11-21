from .loader import ConfigLoader
from .validator import ConfigValidator


class MQTTConfig:
    DEFAULT = {
        "mqtt_server": "mqtt.ohstem.vn",
        "mqtt_port": 1883,
        "mqtt_users": ["0_SmartConvey2025", "1_SmartConvey2025"],
        "mqtt_password": "",
        "cmd_topic": "V1",
        "status_topic": "V2"
    }

    def __init__(self, path="config/config_mqtt.json"):
        cfg = ConfigLoader.load(path, default=self.DEFAULT)

        # --- SERVER ---
        self.server = ConfigValidator.require(cfg, "mqtt_server", self.DEFAULT["mqtt_server"])
        self.port = ConfigValidator.require(cfg, "mqtt_port", self.DEFAULT["mqtt_port"])

        # --- USERS & AUTH ---
        self.users = ConfigValidator.require(cfg, "mqtt_users", self.DEFAULT["mqtt_users"])
        self.password = ConfigValidator.require(cfg, "mqtt_password", self.DEFAULT["mqtt_password"])

        # --- TOPICS ---
        self.cmd_topic = ConfigValidator.require(cfg, "cmd_topic", self.DEFAULT["cmd_topic"])
        self.status_topic = ConfigValidator.require(cfg, "status_topic", self.DEFAULT["status_topic"])
