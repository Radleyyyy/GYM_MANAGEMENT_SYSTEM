import sqlite3
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import attendance_model

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.route("/")
def checkin():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        for m in attendance_model.search_members(q):
            check = attendance_model.validate_checkin(m["member_id"])
            results.append({
                "member": m,
                "membership": check["membership"],
                "inside": attendance_model.is_inside(m["member_id"]),
                "reason": check["reason"],
            })
    return render_template("checkin.html", q=q, results=results)


@attendance_bp.route("/check-in/<int:member_id>", methods=["POST"])
def do_checkin(member_id):
    check = attendance_model.validate_checkin(member_id)
    if check["member"] is None:
        flash(check["reason"], "error")
        return redirect(url_for("attendance.checkin"))
    if not check["ok"]:
        flash(check["reason"], "error")
        return redirect(url_for("attendance.checkin", q=check["member"]["member_number"]))
    try:
        attendance_id = attendance_model.create_checkin(
            member_id, check["membership"]["membership_id"])
    except sqlite3.IntegrityError:
        flash("Access Denied – Already Checked In", "error")
        return redirect(url_for("attendance.checkin", q=check["member"]["member_number"]))
    return redirect(url_for("attendance.checkin_success", attendance_id=attendance_id))


@attendance_bp.route("/success/<int:attendance_id>")
def checkin_success(attendance_id):
    visit = attendance_model.get_visit(attendance_id)
    if visit is None:
        flash("Attendance record not found.", "error")
        return redirect(url_for("attendance.checkin"))
    days_left = (date.fromisoformat(visit["end_date"]) - date.today()).days
    return render_template("checkin_success.html", visit=visit, days_left=days_left)