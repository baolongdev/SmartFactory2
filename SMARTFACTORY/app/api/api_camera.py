# app/api/api_camera.py
from flask import Blueprint, jsonify, Response, current_app, request
from functools import wraps

from app.services.camera_service import camera_service

api_camera = Blueprint("camera", __name__, url_prefix="/api/camera")


def require_camera_running(f):
    """Decorator: chỉ cho phép gọi API khi camera đang chạy."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not camera_service.running:
            current_app.logger.warning(f"{f.__name__} called but camera not running")
            return jsonify({"status": "error", "message": "Camera not started"}), 400
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------

@api_camera.post("/start")
def start_camera():
    """
    Khởi động camera pipeline.

    FE có thể gửi thêm:
    - src: override camera source
    """
    payload = request.get_json(silent=True) or {}
    src = payload.get("src")

    ok = camera_service.start(src_override=src)

    return jsonify({
        "status": "success" if ok else "error",
        "started": ok,
        "src": src,
        "message": "Camera started" if ok else "Failed to start camera"
    })


# ---------------------------------------------------------------------------

@api_camera.post("/stop")
def stop_camera():
    ok = camera_service.stop()
    current_app.logger.info(f"/camera/stop called, result={ok}")
    return jsonify({
        "status": "success",
        "message": "Camera stopped",
        "stopped": ok
    })


# ---------------------------------------------------------------------------

@api_camera.get("/status")
def camera_status():
    status = camera_service.get_status()
    current_app.logger.info(f"/camera/status called, status={status}")
    return jsonify({"status": "success", "data": status})


# ---------------------------------------------------------------------------

@api_camera.get("/stream")
@require_camera_running
def video_stream() -> Response:
    """MJPEG Streaming"""
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


# ---------------------------------------------------------------------------

@api_camera.get("/detections")
@require_camera_running
def camera_detections():
    """
    Danh sách vật thể detect (đã chuẩn hoá).
    """
    detections = camera_service.get_detections()
    if detections is None:
        return jsonify({
            "status": "error",
            "message": "Camera pipeline not ready"
        }), 400

    return jsonify({"status": "success", "detections": detections})

@api_camera.get("/list")
def list_cameras():
    """
    Trả về danh sách camera khả dụng.
    - Windows: dò index 0→10 bằng OpenCV
    - Raspberry/Linux: đọc từ /dev/video* (ổn định hơn)
    """

    import cv2
    import glob
    import platform

    os_name = platform.system().lower()
    available = []

    # ======================================================
    # 👉 RASPBERRY PI / UBUNTU / LINUX
    # ======================================================
    if "linux" in os_name:
        # Tìm camera device /dev/video*
        video_devices = sorted(glob.glob("/dev/video*"))

        for dev in video_devices:
            # Lấy index số từ tên /dev/videoX
            cam_index = int(dev.replace("/dev/video", ""))

            cap = cv2.VideoCapture(cam_index)
            if cap.isOpened():
                available.append({
                    "index": cam_index,
                    "name": f"Linux Camera {cam_index} ({dev})"
                })
            cap.release()

    # ======================================================
    # 👉 WINDOWS
    # ======================================================
    elif "windows" in os_name:
        # Windows có thể có device index rác → chỉ scan 0 → 5
        for i in range(0, 6):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)   # CAP_DSHOW: bắt cam nhanh, tránh freeze
            if cap.isOpened():
                available.append({
                    "index": i,
                    "name": f"Windows Camera {i}"
                })
            cap.release()

    # ======================================================
    # 👉 OTHER OS (macOS...)
    # ======================================================
    else:
        for i in range(0, 5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append({
                    "index": i,
                    "name": f"Camera {i}"
                })
            cap.release()

    return jsonify({
        "status": "success",
        "cameras": available
    })
