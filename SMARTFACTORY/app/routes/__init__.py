from ..api import api_camera, api_mqtt
from .web_routes import web  # import trực tiếp Blueprint từ web_routes

def register_routes(app):
    """Register all app blueprints"""
    app.register_blueprint(web)         # Web pages
    app.register_blueprint(api_camera)   # Camera API
    app.register_blueprint(api_mqtt)    # MQTT API
