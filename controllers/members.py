import re
import sqlite3
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import member_model

members_bp = Blueprint("members", __name__, url_prefix="/members")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,15}$")
FIELDS = ("first_name", "last_name", "gender", "date_of_birth",
          "contact_number", "email", "address", "emergency_contact")
REQUIRED = {
    "first_name": "First name", "last_name": "Last name", "gender": "Gender",
    "date_of_birth": "Date of birth", "contact_number": "Contact number",
    "email": "Email",
}
STATUSES = ("active", "inactive", "archived")


def read_form():
    form = {k: request.form.get(k, "").strip() for k in FIELDS}
    form["email"] = form["email"].lower()
    return form


def validate(f, member_id=None):
    errors = [f"{label} is required." for key, label in REQUIRED.items() if not f[key]]
    if errors:
        return errors
    if f["gender"] not in ("Male", "Female", "Other"):
        errors.append("Gender is invalid.")
    try:
        dob = date.fromisoformat(f["date_of_birth"])
        if dob >= date.today():
            errors.append("Date of birth must be in the past.")
    except ValueError:
        errors.append("Date of birth is invalid.")
    if not PHONE_RE.match(f["contact_number"]):
        errors.append("Contact number is invalid.")
    if not EMAIL_RE.match(f["email"]):
        errors.append("Email format is invalid.")
    if not errors:
        if member_model.email_exists(f["email"], member_id):
            errors.append("This email is already registered.")
        if member_model.contact_exists(f["contact_number"], member_id):
            errors.append("This contact number is already registered.")
    return errors


@members_bp.route("/")
def list_members():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    if status != "all" and status not in STATUSES:
        status = "all"
    members = member_model.list_members(q, status)
    return render_template("member_list.html", members=members, q=q, status=status)


@members_bp.route("/register", methods=["GET", "POST"])
def register():
    form = {k: "" for k in FIELDS}
    if request.method == "POST":
        form = read_form()
        errors = validate(form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            try:
                member_id = member_model.create_member(form)
                return redirect(url_for("members.success", member_id=member_id))
            except sqlite3.IntegrityError:
                flash("A member with this email or contact number already exists.", "error")
    return render_template("member_form.html", form=form, editing=False)


@members_bp.route("/success/<int:member_id>")
def success(member_id):
    member = member_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("members.list_members"))
    return render_template("member_success.html", member=member)


@members_bp.route("/<int:member_id>")
def view(member_id):
    member = member_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("members.list_members"))
    membership = member_model.get_current_membership(member_id)
    days_left = None
    if membership:
        days_left = (date.fromisoformat(membership["end_date"]) - date.today()).days
    payments = member_model.get_payment_history(member_id)
    visits = member_model.get_attendance_history(member_id)
    return render_template(
        "member_view.html", member=member, membership=membership,
        days_left=days_left, payments=payments, visits=visits,
    )


@members_bp.route("/<int:member_id>/edit", methods=["GET", "POST"])
def edit(member_id):
    member = member_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("members.list_members"))
    if request.method == "POST":
        form = read_form()
        errors = validate(form, member_id)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            try:
                member_model.update_member(member_id, form)
                flash("Member updated successfully.", "success")
                return redirect(url_for("members.view", member_id=member_id))
            except sqlite3.IntegrityError:
                flash("A member with this email or contact number already exists.", "error")
    else:
        form = {k: (member[k] or "") for k in FIELDS}
    return render_template("member_form.html", form=form, editing=True,
                           member_number=member["member_number"])


@members_bp.route("/<int:member_id>/status", methods=["POST"])
def change_status(member_id):
    member = member_model.get_member(member_id)
    new_status = request.form.get("status")
    if member is None:
        flash("Member not found.", "error")
    elif new_status not in STATUSES:
        flash("Invalid status.", "error")
    elif new_status in ("inactive", "archived") and member_model.has_active_membership(member_id):
        flash("Cannot deactivate or archive a member who has an active membership.", "error")
    else:
        member_model.set_status(member_id, new_status)
        flash(f"{member['first_name']} {member['last_name']} is now {new_status}.", "success")
    return redirect(request.referrer or url_for("members.list_members"))