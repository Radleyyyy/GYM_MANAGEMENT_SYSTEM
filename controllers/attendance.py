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
            membership = attendance_model.get_active_membership(m["member_id"])
            inside = attendance_model.is_inside(m["member_id"])
            if m["status"] != "active":
                reason = "Member is not active."
            elif membership is None:
                reason = "No active membership."
            elif inside:
                reason = "Already checked in."
            else:
                reason = ""
            results.append({"member": m, "membership": membership,
                            "inside": inside, "reason": reason})
    return render_template("checkin.html", q=q, results=results)


@attendance_bp.route("/check-in/<int:member_id>", methods=["POST"])
def do_checkin(member_id):
    member = attendance_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("attendance.checkin"))
    back = url_for("attendance.checkin", q=member["member_number"])
    if member["status"] != "active":
        flash("Check-in denied: member is not active.", "error")
        return redirect(back)
    membership = attendance_model.get_active_membership(member_id)
    if membership is None:
        flash("Check-in denied: no active membership.", "error")
        return redirect(back)
    try:
        attendance_id = attendance_model.create_checkin(member_id, membership["membership_id"])
    except sqlite3.IntegrityError:
        flash("This member is already checked in.", "error")
        return redirect(back)
    return redirect(url_for("attendance.checkin_success", attendance_id=attendance_id))


@attendance_bp.route("/success/<int:attendance_id>")
def checkin_success(attendance_id):
    visit = attendance_model.get_visit(attendance_id)
    if visit is None:
        flash("Attendance record not found.", "error")
        return redirect(url_for("attendance.checkin"))
    days_left = (date.fromisoformat(visit["end_date"]) - date.today()).days
    return render_template("checkin_success.html", visit=visit, days_left=days_left)