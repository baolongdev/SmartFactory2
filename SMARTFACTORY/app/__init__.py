"""
Flask Application Factory Module.

This module implements the Application Factory pattern for creating Flask instances.
Each call to create_app() creates a new, isolated application instance.

Responsibilities:
--------------
1. Create and configure Flask application
2. Initialize structured logging (structlog)
3. Set up CORS protection
4. Initialize application services (camera, MQTT)
5. Register URL routes and blueprints
6. Register error handlers
7. Inject global template variables

Usage:
------
    from app import create_app

    # Create development app
    app = create_app(env="development")

    # Create production app
    app = create_app(env="production")

Environment Variables:
-------------------
    FLASK_ENV: development|production
    FLASK_HOST: Bind address (default: 0.0.0.0)
    FLASK_PORT: Port number (default: 5000)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import logging initialization (backward-compatible wrapper)
from app.logging_config import init_logger

# Import logging middleware for request context
from app.middleware.logging_middleware import init_logging_middleware

# Import route registration
from .routes import register_routes

# Import services for initialization
from app.services import camera_service, uart_service

import structlog


def create_app(env: str | None = None) -> Flask:
    """
    Application factory function.

    Creates and configures a new Flask application instance with:
    - Structured logging (structlog) initialized
    - Request-scoped logging context (middleware)
    - CORS protection enabled
    - Camera and MQTT services initialized
    - All routes and blueprints registered
    - Error handlers configured

    Args:
        env: Environment name ("development", "production", etc.)
              If provided, sets FLASK_ENV and DEBUG config

    Returns:
        Flask: Configured Flask application instance
    """
    # ---------------------------------------------------------------------------
    # Create Flask Application
    # ---------------------------------------------------------------------------
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ---------------------------------------------------------------------------
    # Environment Configuration
    # ---------------------------------------------------------------------------
    if env:
        app.config["ENV"] = env
        app.config["DEBUG"] = env.lower() == "development"
        if env.lower() == "development":
            app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # ---------------------------------------------------------------------------
    # Initialize Structured Logging
    # Creates structlog logger and attaches to Flask's app.logger
    # This enables structured logging throughout the application
    # ---------------------------------------------------------------------------
    logger = init_logger(name="SmartFactory")
    app.logger = logger
    logger.info("flask_app_creating", env=env)

    # ---------------------------------------------------------------------------
    # Initialize Logging Middleware
    # Adds request-scoped context (request_id, method, path, etc.)
    # Automatically logs request_started and request_finished events
    # ---------------------------------------------------------------------------
    init_logging_middleware(app)

    # ---------------------------------------------------------------------------
    # CORS Configuration
    # Allows cross-origin requests from any origin
    # TODO: Restrict origins in production
    # ---------------------------------------------------------------------------
    CORS(app, resources={r"/*": {"origins": "*"}})

    # ---------------------------------------------------------------------------
    # Initialize Services
    # Camera and MQTT services need Flask app reference for logging
    # ---------------------------------------------------------------------------
    camera_service.init_app(app)
    uart_service.init_app(app)

    # ---------------------------------------------------------------------------
    # Register Routes
    # All URL routes and blueprints are registered here
    # ---------------------------------------------------------------------------
    register_routes(app)

    # ---------------------------------------------------------------------------
    # Register Error Handlers
    # Custom error pages for common HTTP errors
    # ---------------------------------------------------------------------------
    register_error_handlers(app)

    # ---------------------------------------------------------------------------
    # Register Context Processors
    # Inject global variables into all templates
    # ---------------------------------------------------------------------------
    register_context_processors(app)

    logger.info("flask_app_created")
    return app


def register_error_handlers(app: Flask):
    """
    Register error handlers for common HTTP errors.

    Each handler:
    - Logs the error with appropriate level
    - Returns JSON response with error details
    - Includes request path in log context
    """
    logger = structlog.get_logger(__name__)

    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 Not Found errors."""
        logger.warning("route_not_found", path=request.path if request else "unknown")
        return jsonify({"error": "Not Found", "message": "The requested resource was not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        """Handle 500 Internal Server Error."""
        logger.exception("internal_server_error", error=str(e))
        return jsonify({"error": "Internal Server Error", "message": "An internal error occurred"}), 500

    @app.errorhandler(403)
    def forbidden_error(e):
        """Handle 403 Forbidden errors."""
        logger.warning("access_forbidden", path=request.path if request else "unknown")
        return jsonify({"error": "Forbidden", "message": "You do not have permission"}), 403

    @app.errorhandler(400)
    def bad_request(e):
        """Handle 400 Bad Request errors."""
        logger.warning("bad_request", path=request.path if request else "unknown", error=str(e))
        return jsonify({"error": "Bad Request", "message": "Invalid request"}), 400


def register_context_processors(app: Flask):
    """
    Register context processors for Jinja2 templates.

    Injects global variables available in all templates:
    - app_name: Display name of the application
    - version: Application version string
    """
    @app.context_processor
    def inject_config():
        """Inject global template variables."""
        return {"app_name": "Smart Factory Control", "version": "1.0.0"}
