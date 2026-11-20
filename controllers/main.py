from flask import Blueprint, render_template
from database.db import get_db
from models import dashboard_model

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def dashboard():
    return render_template("dashboard.html", d=dashboard_model.dashboard_data())

@main_bp.route("/db-test")
def db_test():
    get_db().execute("SELECT 1")
    return "Database connection OK"