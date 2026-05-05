from ..api import api_camera, api_mqtt, api_colors, api_wifi, api_pcls
from .web_routes import web

def register_routes(app):
    app.register_blueprint(web)
    app.register_blueprint(api_camera)
    app.register_blueprint(api_mqtt)
    app.register_blueprint(api_colors)
    app.register_blueprint(api_wifi)
    app.register_blueprint(api_pcls)
