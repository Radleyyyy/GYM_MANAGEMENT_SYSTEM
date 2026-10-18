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


# ===== Lab 16: attendance history =====
@attendance_bp.route("/history")
def history_search():
    q = request.args.get("q", "").strip()
    if q:
        members = [{"member": m, "visit_count": None, "last_visit": None}
                   for m in attendance_model.search_members(q)]
    else:
        members = [{"member": m, "visit_count": m["visit_count"], "last_visit": m["last_visit"]}
                   for m in attendance_model.recent_visitors()]
    return render_template("history_search.html", q=q, members=members)


@attendance_bp.route("/history/<int:member_id>")
def history(member_id):
    member = attendance_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("attendance.history_search"))

    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    try:
        d_from = date.fromisoformat(date_from) if date_from else None
        d_to = date.fromisoformat(date_to) if date_to else None
        if d_from and d_to and d_from > d_to:
            raise ValueError
    except ValueError:
        flash("Invalid date range. Showing all visits.", "error")
        date_from = date_to = ""

    rows = attendance_model.get_history(member_id, date_from or None, date_to or None)
    visits = []
    total_minutes = completed = 0
    for r in rows:
        cin = datetime.strptime(r["check_in_time"], "%Y-%m-%d %H:%M:%S")
        out_label = None
        if r["check_out_time"]:
            cout = datetime.strptime(r["check_out_time"], "%Y-%m-%d %H:%M:%S")
            out_label = attendance_model.format_time(cout)
            if cout.date() != cin.date():
                out_label += " (next day)"
        if r["duration_minutes"] is not None:
            total_minutes += r["duration_minutes"]
            completed += 1
        visits.append({
            "date": attendance_model.format_date(cin),
            "check_in": attendance_model.format_time(cin),
            "check_out": out_label,
            "duration": attendance_model.format_duration(r["duration_minutes"]),
        })
    summary = {
        "total": len(visits),
        "total_time": attendance_model.format_duration(total_minutes) if completed else "-",
        "average": attendance_model.format_duration(round(total_minutes / completed)) if completed else "-",
    }
    return render_template("history.html", member=member, visits=visits, summary=summary,
                           date_from=date_from, date_to=date_to)