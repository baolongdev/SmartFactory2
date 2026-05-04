"""
Colors API Blueprint - REST endpoints for color configuration.

This module provides HTTP endpoints for managing color detection
configuration. Color definitions are used by the camera pipeline
to detect objects on the conveyor belt.

Endpoints:
----------
- GET  /api/colors/    : Get all color definitions
- POST /api/colors/    : Update color definitions (requires API key)

Authentication:
---------------
Update endpoint requires API key if API_KEY is configured:
    Header: X-API-Key: <your_api_key>

Set API_KEY environment variable to enable authentication.

Color Configuration Format:
---------------------------
    [
        {
            "name": string,           # Color name (e.g., "red", "blue")
            "action_id": int,         # Action ID for MQTT command
            "duration_ms": int,       # Action duration in milliseconds
            "lower": [int, int, int],  # HSV lower bound (auto-filled if missing)
            "upper": [int, int, int],  # HSV upper bound (auto-filled if missing)
            "bgr": [int, int, int]     # BGR color for drawing (auto-filled if missing)
        },
        ...
    ]

Usage:
------
    from app.api.api_colors import api_colors
    app.register_blueprint(api_colors)
"""

from flask import Blueprint, jsonify, request
import os

import structlog

from app.services.colors_service import colors_service
from app.services.camera_service import camera_service

# Module-level logger
logger = structlog.get_logger(__name__)

# Blueprint definition
api_colors = Blueprint("colors", __name__, url_prefix="/api/colors")

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
        logger.warning("colors_api_unauthorized", endpoint=request.path)
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# GET /api/colors/
# ---------------------------------------------------------------------------
@api_colors.get("/")
def get_colors():
    """
    Get all color definitions.

    Returns:
        {
            "status": "success",
            "colors": [
                {
                    "name": string,
                    "action_id": int,
                    "duration_ms": int,
                    "lower": [int, int, int],
                    "upper": [int, int, int],
                    "bgr": [int, int, int]
                },
                ...
            ]
        }

    Notes:
        - Logs at DEBUG level (noisy if INFO)
        - Returns auto-filled values (lower, upper, bgr)
    """
    colors = colors_service.get_colors()
    logger.debug("colors_get_requested", count=len(colors))
    return jsonify({
        "status": "success",
        "colors": colors
    })


# ---------------------------------------------------------------------------
# POST /api/colors/
# ---------------------------------------------------------------------------
@api_colors.post("/")
def update_colors():
    """
    Update color definitions (requires API key if configured).

    Headers (if API_KEY is configured):
        X-API-Key: <api_key>

    Request Body:
        [
            {
                "name": string,           # Required: color name
                "action_id": int,         # Required: action ID
                "duration_ms": int,       # Required: duration in ms
                "lower": [int, int, int],  # Optional: HSV lower (auto-filled)
                "upper": [int, int, int],  # Optional: HSV upper (auto-filled)
                "bgr": [int, int, int]     # Optional: BGR color (auto-filled)
            },
            ...
        ]

    Returns:
        Success: {"status": "success", "updated": true}
        Error:   {"status": "error", "message": string} (400, 401)

    Validation:
        - Request body must be a list
        - Each item must be a dict
        - Each item must have a valid "name" field

    Side Effects:
        - Updates colors.json file
        - Hot-reloads color config in running camera pipeline
        - Logs update event with color count
    """
    # Check authentication
    auth_check = check_api_key()
    if auth_check:
        return auth_check

    # Parse request body
    data = request.get_json(silent=True)

    # Validate: must be a list
    if not isinstance(data, list):
        logger.warning("colors_update_invalid_format")
        return jsonify({
            "status": "error",
            "message": "Invalid format: expected list"
        }), 400

    # Validate each color entry
    for idx, color in enumerate(data):
        # Must be a dict
        if not isinstance(color, dict):
            logger.warning("colors_update_invalid_entry", index=idx)
            return jsonify({
                "status": "error",
                "message": f"Color at index {idx} must be a dict"
            }), 400

        # Must have valid name
        if "name" not in color or not isinstance(color["name"], str):
            logger.warning("colors_update_missing_name", index=idx)
            return jsonify({
                "status": "error",
                "message": f"Color at index {idx} missing valid 'name'"
            }), 400

    # Update color configuration
    colors_service.update_colors(data)

    # Hot-reload in running camera pipeline
    camera_service.update_colors()

    # Log success
    logger.info("colors_updated", count=len(data))

    return jsonify({"status": "success", "updated": True})
