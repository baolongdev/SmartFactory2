"""
MQTT API Blueprint - REST endpoints for MQTT operations.

This module provides HTTP endpoints for interacting with the MQTT broker.
Some endpoints require API key authentication for security.

Endpoints:
----------
- POST /api/mqtt/publish   : Publish message to topic (requires API key)
- GET  /api/mqtt/status    : Get MQTT connection status
- GET  /api/mqtt/messages  : Get last message for a topic

Authentication:
---------------
Endpoints that modify state (publish) require API key:
    Header: X-API-Key: <your_api_key>

Set API_KEY environment variable to enable authentication.
If not set, all endpoints are accessible without authentication.

Usage:
------
    from app.api.api_mqtt import api_mqtt
    app.register_blueprint(api_mqtt)
"""

from flask import Blueprint, jsonify, request
import os

import structlog

from app.services.mqtt_service import mqtt_service

# Module-level logger
logger = structlog.get_logger(__name__)

# Blueprint definition
api_mqtt = Blueprint("mqtt", __name__, url_prefix="/api/mqtt")

# API key from environment (if set, enables authentication)
API_KEY = os.environ.get("API_KEY")


# ---------------------------------------------------------------------------
# Helper: Check API Key
# ---------------------------------------------------------------------------
def check_api_key():
    """
    Check if API key is valid (if API_KEY is configured).

    Returns:
        None if valid (or API_KEY not configured)
        Response if invalid (401 Unauthorized)
    """
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        logger.warning("mqtt_api_unauthorized", endpoint=request.path)
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# POST /api/mqtt/publish
# ---------------------------------------------------------------------------
@api_mqtt.post("/publish")
def publish():
    """
    Publish a message to an MQTT topic.

    Headers:
        X-API-Key: <api_key> (required if API_KEY is configured)

    Request Body:
        {
            "topic": string,      # MQTT topic (required)
            "message": string     # Message payload (required)
        }

    Returns:
        Success: {"status": "success", "topic": string, "message": string}
        Error:   {"status": "error", "message": string} (400, 401, or 500)

    Validation:
        - topic must be a non-empty string
        - message must be a string

    Notes:
        - Requires MQTT to be connected
        - Topic and message are logged for debugging
    """
    # Check authentication
    auth_check = check_api_key()
    if auth_check:
        return auth_check

    data = request.get_json(silent=True) or {}
    topic = data.get("topic")
    message = data.get("message")

    # Validate topic
    if not isinstance(topic, str) or not topic.strip():
        logger.warning("mqtt_publish_invalid_topic", topic=topic)
        return jsonify({"status": "error", "message": "Valid topic required"}), 400

    # Validate message
    if not isinstance(message, str):
        logger.warning("mqtt_publish_invalid_message")
        return jsonify({"status": "error", "message": "Message must be a string"}), 400

    # Publish message
    ok = mqtt_service.publish(topic, message)

    if ok:
        logger.info("mqtt_publish_success", topic=topic)
        return jsonify({"status": "success", "topic": topic, "message": message})
    else:
        logger.error("mqtt_publish_failed_not_connected", topic=topic)
        return jsonify({"status": "error", "message": "MQTT not connected"}), 500


# ---------------------------------------------------------------------------
# GET /api/mqtt/status
# ---------------------------------------------------------------------------
@api_mqtt.get("/status")
def mqtt_status():
    """
    Get MQTT connection status.

    Returns:
        {
            "status": "success",
            "data": {
                "connected": bool
            }
        }

    Notes:
        - Logs at DEBUG level (noisy if INFO)
        - Used by frontend to show connection indicator
    """
    status = mqtt_service.status()
    logger.debug("mqtt_status_requested", connected=status.get("connected"))
    return jsonify({"status": "success", "data": status})


# ---------------------------------------------------------------------------
# GET /api/mqtt/messages
# ---------------------------------------------------------------------------
@api_mqtt.get("/messages")
def get_last_message():
    """
    Get the last message received on a topic.

    Query Parameters:
        topic: MQTT topic to retrieve last message for

    Returns:
        {
            "status": "success",
            "topic": string,
            "message": any  # Last message (JSON or string)
        }
        Error: {"status": "error", "message": "Missing 'topic' parameter"} (400)

    Notes:
        - Returns None if no message received on topic
        - Message may be parsed JSON or raw string
    """
    topic = request.args.get("topic")

    if not topic:
        return jsonify({"status": "error", "message": "Missing 'topic' parameter"}), 400

    msg = mqtt_service.get_last_message(topic)
    logger.debug("mqtt_get_last_message", topic=topic)
    return jsonify({"status": "success", "topic": topic, "message": msg})
