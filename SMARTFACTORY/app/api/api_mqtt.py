# app/api/api_mqtt.py
from flask import Blueprint, jsonify, request
from app.services.mqtt_service import mqtt_service

api_mqtt = Blueprint("mqtt", __name__, url_prefix="/api/mqtt")


@api_mqtt.post("/publish")
def publish():
    """
    Publish 1 message lên MQTT.

    NOTE mở rộng:
    - Sau này có thể cho phép gửi JSON phức tạp:
        + FE gửi "payload": { ... }
        + Ở đây dùng json.dumps(payload) trước khi publish.
    - Có thể thêm field "user" để chọn user cụ thể trong cfg.users.
    """
    data = request.get_json(silent=True) or {}
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
    """Trả về trạng thái kết nối MQTT."""
    status = mqtt_service.status()
    return jsonify({"status": "success", "data": status})


@api_mqtt.get("/messages")
def get_last_message():
    """
    Lấy message cuối cùng của 1 topic.

    NOTE mở rộng:
    - Có thể cho phép query nhiều topic cùng lúc:
        + FE gửi ?topic=A&topic=B
        + Trả lại dict {topic: last_message}
    """
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"status": "error", "message": "Missing 'topic' parameter"}), 400

    msg = mqtt_service.get_last_message(topic)
    return jsonify({"status": "success", "topic": topic, "message": msg})
