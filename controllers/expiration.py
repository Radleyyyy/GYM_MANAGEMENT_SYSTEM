from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import expiration_model

expiration_bp = Blueprint("expiration", __name__, url_prefix="/expiration")


@expiration_bp.route("/")
def monitor():
    expiration_model.update_statuses()
    key = request.args.get("filter", "7days")
    if key not in expiration_model.FILTERS:
        key = "7days"
    return render_template(
        "expiration_monitor.html",
        rows=expiration_model.list_memberships(key),
        counts=expiration_model.counts(),
        filters=expiration_model.FILTERS,
        current=key,
    )


@expiration_bp.route("/update", methods=["POST"])
def run_update():
    changed = expiration_model.update_statuses()
    flash(f"Expiration processing done. {changed} membership(s) marked expired.", "success")
    return redirect(url_for("expiration.monitor"))
