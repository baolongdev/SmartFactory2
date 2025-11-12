from flask import Blueprint, jsonify, request
from app.services.mqtt_service import mqtt_service

api_mqtt = Blueprint("mqtt", __name__, url_prefix="/api/mqtt")

@api_mqtt.post("/publish")
def publish():
    data = request.json or {}
    topic = data.get("topic")
    message = data.get("message")
    if not topic or not message:
        return jsonify({"status": "error", "message": "Missing 'topic' or 'message'"}), 400

    ok = mqtt_service.publish(topic, message)
    if ok:
        return jsonify({"status": "success", "topic": topic, "message": message})
    else:
        return jsonify({"status": "error", "message": "MQTT not connected"}), 500

@api_mqtt.get("/status")
def mqtt_status():
    status = mqtt_service.status()
    return jsonify({"status": "success", "data": status})

@api_mqtt.get("/messages")
def get_last_message():
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"status": "error", "message": "Missing 'topic' parameter"}), 400

    msg = mqtt_service.get_last_message(topic)
    return jsonify({"status": "success", "topic": topic, "message": msg})
