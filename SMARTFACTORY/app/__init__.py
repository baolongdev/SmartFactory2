from flask import Flask, jsonify
from flask_cors import CORS
from app.logging_config import init_logger
from .routes import register_routes
from app.services import camera_service, mqtt_service

def create_app(env: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Config
    if env:
        app.config["ENV"] = env
        app.config["DEBUG"] = env.lower() == "development"

    # Logger
    logger = init_logger(name="SmartFactory")
    app.logger = logger
    app.logger.info(f"Creating Flask app with env='{env}'")

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Init services
    camera_service.init_app(app)
    mqtt_service.init_app(app)

    # Register routes
    register_routes(app)

    # Error handlers
    register_error_handlers(app)

    # Context processors
    register_context_processors(app)

    app.logger.info("Flask app creation complete")
    return app

def register_error_handlers(app: Flask):
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not Found", "message": "The requested resource was not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception(f"Internal Server Error: {e}")
        return jsonify({"error": "Internal Server Error", "message": "An internal error occurred"}), 500

    @app.errorhandler(403)
    def forbidden_error(e):
        return jsonify({"error": "Forbidden", "message": "You do not have permission"}), 403

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad Request", "message": "Invalid request"}), 400

def register_context_processors(app: Flask):
    @app.context_processor
    def inject_config():
        return {"app_name": "Smart Factory Control", "version": "1.0.0"}
