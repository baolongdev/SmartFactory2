from .app_config import AppConfig

class ConfigService:
    def __init__(self):
        self.app_cfg = AppConfig()

    def get_camera_config(self):
        return self.app_cfg.camera_config

    def get_mqtt_config(self):
        return self.app_cfg.mqtt_config

    def get_color_config(self):
        return self.app_cfg.color_config


config_service = ConfigService()
