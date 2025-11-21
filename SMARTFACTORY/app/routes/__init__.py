from ..api import api_camera, api_mqtt, api_colors
from .web_routes import web  

def register_routes(app):
    """Register all app blueprints"""
    app.register_blueprint(web)         # Web pages
    app.register_blueprint(api_camera)   # Camera API
    app.register_blueprint(api_mqtt)    # MQTT API
    app.register_blueprint(api_colors)
