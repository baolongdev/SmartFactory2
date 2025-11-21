from app.services.camera_service import camera_service
from flask import Blueprint, jsonify, request
from app.services.colors_service import colors_service

api_colors = Blueprint("colors", __name__, url_prefix="/api/colors")


@api_colors.get("/")
def get_colors():
    return jsonify({
        "status": "success",
        "colors": colors_service.get_colors()
    })


@api_colors.post("/")
def update_colors():
    data = request.get_json(silent=True)

    if not isinstance(data, list):
        return jsonify({
            "status": "error",
            "message": "Invalid format: expected list"
        }), 400

    colors_service.update_colors(data)
    camera_service.update_colors()

    return jsonify({"status": "success", "updated": True})
