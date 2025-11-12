"""
WSGI Entry Point
Smart Factory Control System (Production)
For deployment via Gunicorn / uWSGI
"""

import os
from app import create_app
from app.logging_config import init_logger

# Initialize logger (shared across project)
logger = init_logger("SmartFactoryWSGI")

# Determine environment
env = os.getenv("FLASK_ENV", "production")

# Create Flask app
app = create_app(env)

logger.info("════════════════════════════════════════════════════════")
logger.info("  Smart Factory Control System (WSGI Mode)")
logger.info("  Ready for Gunicorn / uWSGI deployment")
logger.info(f"  Environment: {env}")
logger.info("════════════════════════════════════════════════════════")
