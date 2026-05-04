"""
Camera API Blueprint - REST endpoints for camera operations.

This module provides HTTP endpoints for controlling and monitoring
the camera pipeline. All endpoints require proper request context.

Endpoints:
----------
- POST /api/camera/start   : Start camera pipeline (optional: src parameter)
- POST /api/camera/stop    : Stop camera pipeline
- GET  /api/camera/status   : Get pipeline status (running, detected, tracked)
- GET  /api/camera/stream   : MJPEG video stream
- GET  /api/camera/detections: Get current detection results
- GET  /api/camera/list     : List available cameras

Decorators:
------------
- require_camera_running: Ensures camera is running before processing request

Request Context:
--------------
All endpoints automatically include request context from middleware:
- request_id: Unique request identifier
- method: HTTP method
- path: Request path
- client_ip: Client IP address

Usage:
------
    from app.api.api_camera import api_camera
    app.register_blueprint(api_camera)
"""

from flask import Blueprint, jsonify, Response, request
from functools import wraps

import structlog

from app.services.camera_service import camera_service

# Module-level logger
logger = structlog.get_logger(__name__)

# Blueprint definition
api_camera = Blueprint("camera", __name__, url_prefix="/api/camera")


# ---------------------------------------------------------------------------
# Decorator: Require Camera Running
# ---------------------------------------------------------------------------
def require_camera_running(f):
    """
    Decorator: Only allow API calls when camera is running.

    Returns 400 error if camera is not started.
    Logs warning with function name for debugging.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not camera_service.running:
            logger.warning("camera_api_called_but_not_running", func=f.__name__)
            return jsonify({"status": "error", "message": "Camera not started"}), 400
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# POST /api/camera/start
# ---------------------------------------------------------------------------
@api_camera.post("/start")
def start_camera():
    """
    Start camera pipeline.

    Request Body (optional):
        {
            "src": 0  # Camera source index or URL (optional)
        }

    Returns:
        {
            "status": "success"|"error",
            "started": bool,
            "src": int|null,
            "message": string
        }

    Notes:
        - If camera is already running, returns True (idempotent)
        - Source override allows switching cameras without restart
    """
    payload = request.get_json(silent=True) or {}
    src = payload.get("src")

    # Validate src if provided
    # src can be an integer (USB index) or a string URL (RTSP/HTTP)
    if src is not None:
        if isinstance(src, str):
            src = src.strip()
            if not src:
                return jsonify({
                    "status": "error",
                    "message": "src URL cannot be empty"
                }), 400
        else:
            try:
                src = int(src)
            except (ValueError, TypeError):
                return jsonify({
                    "status": "error",
                    "message": "src must be an integer index or a URL string"
                }), 400

    ok = camera_service.start(src_override=src)

    return jsonify({
        "status": "success" if ok else "error",
        "started": ok,
        "src": src,
        "message": "Camera started" if ok else "Failed to start camera"
    })


# ---------------------------------------------------------------------------
# POST /api/camera/stop
# ---------------------------------------------------------------------------
@api_camera.post("/stop")
def stop_camera():
    """
    Stop camera pipeline.

    Returns:
        {
            "status": "success",
            "message": "Camera stopped",
            "stopped": bool
        }

    Notes:
        - Safe to call even if camera is already stopped
        - Logs result for monitoring
    """
    ok = camera_service.stop()
    logger.info("camera_stop_api_called", result=ok)
    return jsonify({
        "status": "success",
        "message": "Camera stopped",
        "stopped": ok
    })


# ---------------------------------------------------------------------------
# GET /api/camera/status
# ---------------------------------------------------------------------------
@api_camera.get("/status")
def camera_status():
    """
    Get camera pipeline status.

    Returns:
        {
            "status": "success",
            "data": {
                "running": bool,
                "pipeline_ready": bool,
                "detected": int,
                "tracked": int
            }
        }

    Status Fields:
        - running: Is camera service running?
        - pipeline_ready: Is pipeline initialized?
        - detected: Number of objects detected in last frame
        - tracked: Number of objects being tracked
    """
    status = camera_service.get_status()
    logger.info("camera_status_api_called", **status)
    return jsonify({"status": "success", "data": status})


# ---------------------------------------------------------------------------
# GET /api/camera/stream
# ---------------------------------------------------------------------------
@api_camera.get("/stream")
@require_camera_running
def video_stream() -> Response:
    """
    MJPEG video stream endpoint.

    Returns:
        Response: MJPEG stream with appropriate headers

    Headers Set:
        - Content-Type: multipart/x-mixed-replace; boundary=frame
        - Cache-Control: no-cache
        - Connection: close

    Notes:
        - Requires camera to be running (require_camera_running)
        - Stream continues until client disconnects
        - FPS can be limited by modifying sleep in stream generator
    """
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
# GET /api/camera/detections
# ---------------------------------------------------------------------------
@api_camera.get("/detections")
@require_camera_running
def camera_detections():
    """
    Get current detection results (normalized for frontend).

    Returns:
        {
            "status": "success",
            "detections": [
                {
                    "x": int, "y": int, "w": int, "h": int,
                    "name": string,
                    "bgr": [int, int, int],
                    "action_id": int,
                    "duration_ms": int
                },
                ...
            ]
        }

    Notes:
        - Requires camera to be running
        - Returns empty list if no objects detected
        - Results are normalized to consistent format
    """
    detections = camera_service.get_detections()
    if detections is None:
        return jsonify({
            "status": "error",
            "message": "Camera pipeline not ready"
        }), 400

    return jsonify({"status": "success", "detections": detections})


# ---------------------------------------------------------------------------
# GET /api/camera/list
# ---------------------------------------------------------------------------
@api_camera.get("/list")
def list_cameras():
    """
    List available camera devices.

    Returns:
        {
            "status": "success",
            "cameras": [
                {"index": int, "name": string},
                ...
            ]
        }

    Detection Logic:
        - Linux: Scan /dev/video* devices
        - Windows: Test indices 0-5 using OpenCV with CAP_DSHOW
        - Other: Test indices 0-4

    Notes:
        - Windows uses CAP_DSHOW for faster camera access
        - Only returns cameras that can be opened
    """
    import cv2
    import glob
    import platform

    os_name = platform.system().lower()
    available = []

    # Linux: Scan /dev/video* devices
    if "linux" in os_name:
        video_devices = sorted(glob.glob("/dev/video*"))
        for dev in video_devices:
            cam_index = int(dev.replace("/dev/video", ""))
            cap = cv2.VideoCapture(cam_index)
            if cap.isOpened():
                available.append({
                    "index": cam_index,
                    "name": f"Linux Camera {cam_index} ({dev})"
                })
            cap.release()

    # Windows: Test indices 0-5
    elif "windows" in os_name:
        for i in range(0, 6):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                available.append({
                    "index": i,
                    "name": f"Windows Camera {i}"
                })
            cap.release()

    # Other OS: Test indices 0-4
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
