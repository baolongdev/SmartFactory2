import paho.mqtt.client as mqtt
from app.core.config import config_service
import threading
import time
from collections import defaultdict
import json

class MQTTService:
    """Singleton MQTT service cho publish và lưu message cuối theo topic."""
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            with cls._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.client: mqtt.Client | None = None
        self.connected = False
        self.logger = None
        self.last_messages = defaultdict(lambda: None)  # lưu message cuối theo topic
        self._initialized = True

    def init_app(self, app):
        """Khởi tạo MQTT service với Flask app."""
        self.logger = app.logger
        self._setup()
        if self.logger:
            self.logger.info("[MQTTService] Initialized")

    def _setup(self):
        cfg = config_service.get_mqtt_config()
        self.client = mqtt.Client()
        if cfg.users:
            self.client.username_pw_set(cfg.users[0], cfg.password or "")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Kết nối với retry 3 lần
        for i in range(3):
            try:
                self.client.connect(cfg.server, cfg.port, 60)
                self.client.loop_start()
                if self.logger:
                    self.logger.info(f"[MQTT] Connecting to {cfg.server}:{cfg.port}")
                break
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[MQTT] Connect attempt {i+1} failed: {e}")
                time.sleep(1)
        else:
            if self.logger:
                self.logger.error("[MQTT] Could not connect after retries")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.connected = True
        cfg = config_service.get_mqtt_config()
        # Subscribe đúng topic của user, không subscribe nhầm php/feeds/...
        for user in cfg.users:
            topic = f"{user}/feeds/#"
            client.subscribe(topic)
            if self.logger:
                self.logger.info(f"[MQTT] Subscribed to {topic}")
        if self.logger:
            self.logger.info(f"[MQTT] Connected, rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if self.logger:
            self.logger.warning(f"[MQTT] Disconnected, rc={rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_raw = msg.payload.decode()
        try:
            # Nếu payload là JSON, parse ra dict
            payload = json.loads(payload_raw)
        except:
            payload = payload_raw
        self.last_messages[topic] = payload
        if self.logger:
            self.logger.info(f"[MQTT] Received on '{topic}': {payload}")

    def publish(self, topic: str, msg: str):
        """Publish message nếu connected."""
        if not self.client or not self.connected:
            if self.logger:
                self.logger.warning(f"[MQTT] Not connected, cannot publish to '{topic}'")
            return False
        try:
            self.client.publish(topic, msg)
            if self.logger:
                self.logger.info(f"[MQTT] Published to '{topic}': {msg}")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"[MQTT] Publish failed: {e}")
            return False

    def status(self) -> dict:
        return {"connected": self.connected}

    def get_last_message(self, topic: str):
        """Trả message cuối cùng của topic, nếu chưa có thì None"""
        return self.last_messages.get(topic)

# Singleton instance
mqtt_service = MQTTService()
