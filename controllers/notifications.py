from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import notification_model

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
def list_notifications():
    notification_model.generate_notifications()
    unread_only = request.args.get("filter") == "unread"
    return render_template(
        "notification_list.html",
        notifications=notification_model.list_notifications(unread_only),
        unread=notification_model.unread_count(),
        unread_only=unread_only,
        labels=notification_model.TYPE_LABELS,
    )


@notifications_bp.route("/generate", methods=["POST"])
def generate():
    created = notification_model.generate_notifications()
    flash(f"{created} new notification(s) generated.", "success")
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
def read(notification_id):
    notification_model.mark_read(notification_id)
    return redirect(url_for("notifications.list_notifications"))


@notifications_bp.route("/read-all", methods=["POST"])
def read_all():
    notification_model.mark_read()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.list_notifications"))
