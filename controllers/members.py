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


def validate(f):
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
        if member_model.email_exists(f["email"]):
            errors.append("This email is already registered.")
        if member_model.contact_exists(f["contact_number"]):
            errors.append("This contact number is already registered.")
    return errors


@members_bp.route("/register", methods=["GET", "POST"])
def register():
    form = {k: "" for k in FIELDS}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in FIELDS}
        form["email"] = form["email"].lower()
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
    return render_template("member_form.html", form=form)


@members_bp.route("/success/<int:member_id>")
def success(member_id):
    member = member_model.get_member(member_id)
    if member is None:
        flash("Member not found.", "error")
        return redirect(url_for("members.register"))
    return render_template("member_success.html", member=member)