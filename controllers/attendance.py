import sqlite3
from datetime import date, datetime
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


# ===== Lab 15: check-out =====
@attendance_bp.route("/check-out")
def checkout():
    q = request.args.get("q", "").strip()
    now = datetime.now()
    visits = []
    for v in attendance_model.list_open_visits(q):
        started = datetime.strptime(v["check_in_time"], "%Y-%m-%d %H:%M:%S")
        minutes_inside = max(0, int((now - started).total_seconds() // 60))
        visits.append({"visit": v, "minutes_inside": minutes_inside})
    return render_template("checkout.html", q=q, visits=visits)


@attendance_bp.route("/check-out/<int:attendance_id>", methods=["POST"])
def do_checkout(attendance_id):
    if attendance_model.checkout(attendance_id):
        return redirect(url_for("attendance.checkout_summary", attendance_id=attendance_id))
    flash("This visit was not found or the member is already checked out.", "error")
    return redirect(url_for("attendance.checkout"))


@attendance_bp.route("/summary/<int:attendance_id>")
def checkout_summary(attendance_id):
    visit = attendance_model.get_visit(attendance_id)
    if visit is None or visit["check_out_time"] is None:
        flash("Attendance summary not available.", "error")
        return redirect(url_for("attendance.checkout"))
    return render_template("checkout_summary.html", visit=visit)