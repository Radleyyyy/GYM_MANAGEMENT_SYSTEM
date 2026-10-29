from flask import Blueprint, render_template, request
from models import report_model

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
def index():
    return render_template("report_index.html")


@reports_bp.route("/members")
def members():
    default_from, default_to = report_model.default_range()
    date_from = report_model.valid_date(request.args.get("date_from")) or default_from
    date_to = report_model.valid_date(request.args.get("date_to")) or default_to
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return render_template("report_members.html", r=report_model.member_report(date_from, date_to),
                           date_from=date_from, date_to=date_to)
