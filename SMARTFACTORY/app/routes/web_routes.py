# app/routes/web_routes.py
from flask import Blueprint, render_template

web = Blueprint('web', __name__)

@web.route('/')
def index():
    return render_template('index.html')

@web.get("/wifi")
def wifi_page():
    return render_template("wifi.html")