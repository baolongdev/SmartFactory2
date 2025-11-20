from flask import Blueprint, jsonify, Response, current_app
from app.services.camera_service import camera_service
from functools import wraps

api_camera = Blueprint("camera", __name__, url_prefix="/api/camera")

def require_camera_running(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not camera_service.running:
            current_app.logger.warning(f"{f.__name__} called but camera not running")
            return jsonify({"status": "error", "message": "Camera not started"}), 400
        return f(*args, **kwargs)
    return decorated

@api_camera.post("/start")
def start_camera():
    payload = {}
    try:
        payload = request.get_json() or {}
    except:
        pass

    # Lấy src nếu FE gửi lên
    src = payload.get("src")

    ok = camera_service.start(src_override=src)

    return jsonify({
        "status": "success" if ok else "error",
        "started": ok,
        "message": f"Camera started with src={src}"
    })


@api_camera.post("/stop")
def stop_camera():
    ok = camera_service.stop()
    current_app.logger.info(f"/camera/stop called, result={ok}")
    return jsonify({"status": "success", "message": "Camera stopped", "stopped": ok})

@api_camera.get("/status")
def camera_status():
    status = camera_service.get_status()
    current_app.logger.info(f"/camera/status called, status={status}")
    return jsonify({"status": "success", "data": status})

@api_camera.get("/stream")
@require_camera_running
def video_stream() -> Response:
    return Response(
        camera_service.stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "close"
        }
    )

@api_camera.get("/detections")
@require_camera_running
def camera_detections():
    if camera_service.pipeline is None:
        return jsonify({"status":"error","message":"Camera pipeline not ready"}), 400

    raw_objs = camera_service.pipeline.get_detections()
    detections = []

    for o in raw_objs:
        if isinstance(o, dict):
            # dict từ to_dict(), sửa key "color_name" → "name"
            detections.append({
                "x": o.get("x", 0),
                "y": o.get("y", 0),
                "w": o.get("w", 0),
                "h": o.get("h", 0),
                "name": o.get("color_name", "unknown"),
                "bgr": list(o.get("bgr", (255,255,255)))
            })
        elif hasattr(o, "name") and hasattr(o, "bgr"):
            # ColorObject instance
            detections.append({
                "x": getattr(o, "x", 0),
                "y": getattr(o, "y", 0),
                "w": getattr(o, "w", 0),
                "h": getattr(o, "h", 0),
                "name": getattr(o, "name", "unknown"),
                "bgr": list(getattr(o, "bgr", (255,255,255)))
            })
        else:
            # fallback
            detections.append({
                "x":0,"y":0,"w":0,"h":0,"name":"unknown","bgr":[200,200,200]
            })

    return jsonify({"status": "success", "detections": detections})

