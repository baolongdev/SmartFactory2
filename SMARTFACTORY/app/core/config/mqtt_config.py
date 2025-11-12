from .loader import ConfigLoader
from .validator import ConfigValidator


class MQTTConfig:
    DEFAULT = {
        "mqtt_server":"mqtt.ohstem.vn",
        "mqtt_port":1883,
        "mqtt_users":["0_SmartConvey2025","1_SmartConvey2025"],
        "mqtt_password":"",
        "cmd_topic":"V1",
        "status_topic":"V2"
    }

    def __init__(self, path="config/config_mqtt.json"):
        cfg = ConfigLoader.load(path, default=self.DEFAULT)
        self.server = ConfigValidator.require(cfg, "mqtt_server", "mqtt.ohstem.vn")
        self.port = ConfigValidator.require(cfg, "mqtt_port", 1883)
        self.users = ConfigValidator.require(cfg, "mqtt_users", ["0_SmartConvey2025"])
        self.password = ConfigValidator.require(cfg, "mqtt_password", "")
        self.cmd_topic = ConfigValidator.require(cfg, "cmd_topic", "V1")
        self.status_topic = ConfigValidator.require(cfg, "status_topic", "V2")