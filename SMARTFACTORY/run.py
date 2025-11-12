#!/usr/bin/env python3
"""
Flask Application Entry Point
Smart Factory Control System (Development)
"""

import os
from dotenv import load_dotenv
from app import create_app
from app.logging_config import init_logger

# Load environment variables from .env
load_dotenv()

# Initialize logger (shared across project)
logger = init_logger("SmartFactory")

# Determine environment
env = os.getenv("FLASK_ENV", "development")
debug = env == "development"

# Create Flask app
app = create_app(env)

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", 5000))

    logger.info("════════════════════════════════════════════════════════")
    logger.info("  Smart Factory Control System (Development)")
    logger.info("  Flask + ESP32 + MQTT + OpenCV")
    logger.info(f"  Server: http://{host}:{port}")
    logger.info(f"  Debug Mode: {debug}")
    logger.info("════════════════════════════════════════════════════════")

    # Run Flask development server
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True,
        use_reloader=debug
    )
