"""
MQTT Service - Singleton service for MQTT communication.

This module provides MQTT connectivity for the SmartFactory2 system.
Used to send commands to ESP32-based conveyor systems based on
detected color objects.

Architecture:
------------
- MQTTService: Singleton class managing MQTT client lifecycle
- Automatic reconnection with retry logic
- Message caching for last message per topic
- Subscribe to user feeds for receiving status updates

Dependencies:
------------
- paho-mqtt: MQTT client library
- config_service: Provides MQTT broker configuration
- threading: For singleton thread-safe initialization

Usage:
------
    from app.services.mqtt_service import mqtt_service

    # Publish a message
    mqtt_service.publish("topic/name", "payload")

    # Check connection status
    status = mqtt_service.status()

    # Get last message for a topic
    msg = mqtt_service.get_last_message("topic/name")

Configuration (config_mqtt.json):
----------------------------
    {
        "mqtt_server": "mqtt.example.com",
        "mqtt_port": 1883,
        "mqtt_users": ["user1", "user2"],
        "mqtt_password": "",
        "cmd_topic": "V1",
        "status_topic": "V2"
    }
"""

import paho.mqtt.client as mqtt
from app.core.config import config_service
import threading
import time
from collections import defaultdict
import json

import structlog

# Module-level logger
logger = structlog.get_logger(__name__)


class MQTTService:
    """
    Singleton MQTT service for publish/subscribe operations.

    Design Patterns:
    - Singleton: Only one instance exists (mqtt_service)
    - Observer: Subscribes to topics and caches incoming messages
    - Retry: Automatic reconnection with configurable attempts

    Responsibilities:
    - Manage MQTT client connection (connect/disconnect)
    - Publish messages to topics
    - Subscribe to user feeds for status updates
    - Cache last message per topic
    - Provide connection status

    Thread Safety:
    - _instance_lock: Thread-safe singleton initialization
    - Note: MQTT client operations are not thread-safe by default
            Consider adding lock for publish operations if using multiple threads
    """

    # Thread-safe singleton implementation
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Ensure only one instance exists."""
        if not hasattr(cls, "_instance"):
            with cls._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initialize MQTT service (runs only once due to _initialized flag).

        Sets up:
        - MQTT client instance (None until connected)
        - Connection status flag
        - Message cache (defaultdict for last message per topic)
        """
        # Skip re-initialization (singleton pattern)
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.client: mqtt.Client | None = None
        self.connected = False
        self.last_messages = defaultdict(lambda: None)  # last message per topic
        self._initialized = True

    def init_app(self, app):
        """
        Initialize service with Flask app context.

        Args:
            app: Flask application instance (for logging context)
        """
        self._setup()
        logger.info("mqtt_service_initialized")

    def _setup(self):
        """
        Set up MQTT client and attempt connection.

        Configuration:
        - Reads config from config_service (config_mqtt.json)
        - Sets up username/password if configured
        - Registers callback handlers
        - Attempts connection with retry (3 attempts)

        Callbacks:
        - _on_connect: Called when connection established
        - _on_disconnect: Called when disconnected
        - _on_message: Called when message received
        """
        cfg = config_service.get_mqtt_config()

        # Create MQTT client
        self.client = mqtt.Client()

        # Set credentials if configured
        if cfg.users:
            self.client.username_pw_set(cfg.users[0], cfg.password or "")

        # Register callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Attempt connection with retry
        for i in range(3):
            try:
                logger.info("mqtt_connecting", server=cfg.server, port=cfg.port, attempt=i+1)
                self.client.connect(cfg.server, cfg.port, 60)
                self.client.loop_start()
                break
            except Exception as e:
                logger.error("mqtt_connect_attempt_failed", attempt=i+1, error=str(e))
                time.sleep(1)
        else:
            logger.error("mqtt_connect_failed_after_retries")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback: Called when MQTT client connects to broker.

        Args:
            client: MQTT client instance
            userdata: User data (unused)
            flags: Connection flags
            rc: Return code (0 = success)
            properties: MQTT v5 properties (optional)
        """
        self.connected = True
        cfg = config_service.get_mqtt_config()

        # Subscribe to user feeds for status updates
        for user in cfg.users:
            topic = f"{user}/feeds/#"
            client.subscribe(topic)
            logger.info("mqtt_subscribed", topic=topic)

        logger.info("mqtt_connected", rc=rc)

    def _on_disconnect(self, client, userdata, rc):
        """
        Callback: Called when MQTT client disconnects from broker.

        Args:
            client: MQTT client instance
            userdata: User data (unused)
            rc: Return code
        """
        self.connected = False
        logger.warning("mqtt_disconnected", rc=rc)

    def _on_message(self, client, userdata, msg):
        """
        Callback: Called when message is received on subscribed topic.

        Args:
            client: MQTT client instance
            userdata: User data (unused)
            msg: MQTT message (topic, payload, etc.)
        """
        topic = msg.topic
        payload_raw = msg.payload.decode()

        # Try to parse as JSON, fall back to raw string
        try:
            payload = json.loads(payload_raw)
        except:
            payload = payload_raw

        # Cache last message for this topic
        self.last_messages[topic] = payload
        logger.info("mqtt_message_received", topic=topic, payload=payload)

    def publish(self, topic: str, msg: str) -> bool:
        """
        Publish a message to an MQTT topic.

        Args:
            topic: MQTT topic string
            msg: Message payload (string)

        Returns:
            bool: True if published successfully, False otherwise
        """
        # Check connection
        if not self.client or not self.connected:
            logger.warning("mqtt_not_connected_cannot_publish", topic=topic)
            return False

        try:
            self.client.publish(topic, msg)
            logger.info("mqtt_published", topic=topic, message=msg)
            return True
        except Exception as e:
            logger.exception("mqtt_publish_failed", topic=topic, error_type=type(e).__name__)
            return False

    def status(self) -> dict:
        """
        Get current MQTT connection status.

        Returns:
            dict: Status information with 'connected' key
        """
        return {"connected": self.connected}

    def get_last_message(self, topic: str):
        """
        Get the last message received on a topic.

        Args:
            topic: MQTT topic string

        Returns:
            The last message (JSON dict or string), or None if no message received
        """
        return self.last_messages.get(topic)


# Singleton instance - imported by other modules
mqtt_service = MQTTService()
