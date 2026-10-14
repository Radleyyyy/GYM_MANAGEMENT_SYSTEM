import math
import re
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import plan_model

plans_bp = Blueprint("plans", __name__, url_prefix="/plans")

PLAN_CODE_RE = re.compile(r"^[A-Z0-9]{2,10}$")
ACCESS_TYPES = ("Full Access", "Off-Peak Access", "Gym Floor Only")
FIELDS = ("plan_code", "plan_name", "duration_months", "price",
          "description", "benefits", "access_type", "status")
REQUIRED = {
    "plan_code": "Plan code", "plan_name": "Plan name",
    "duration_months": "Duration", "price": "Price",
    "access_type": "Access type", "status": "Status",
}


def read_form():
    form = {k: request.form.get(k, "").strip() for k in FIELDS}
    form["plan_code"] = form["plan_code"].upper()
    return form


def validate(f, plan_id=None):
    errors = [f"{label} is required." for key, label in REQUIRED.items() if not f[key]]
    if errors:
        return errors
    if not PLAN_CODE_RE.match(f["plan_code"]):
        errors.append("Plan code must be 2-10 letters or numbers (example: MON).")
    if len(f["plan_name"]) > 50:
        errors.append("Plan name must be 50 characters or less.")
    try:
        duration = int(f["duration_months"])
        if not 1 <= duration <= 60:
            errors.append("Duration must be between 1 and 60 months.")
    except ValueError:
        errors.append("Duration must be a whole number of months.")
    try:
        price = float(f["price"])
        if not math.isfinite(price) or price <= 0 or price > 1_000_000:
            errors.append("Price must be greater than 0 and at most ₱1,000,000.")
    except ValueError:
        errors.append("Price must be a valid number.")
    if f["access_type"] not in ACCESS_TYPES:
        errors.append("Access type is invalid.")
    if f["status"] not in ("active", "inactive"):
        errors.append("Status is invalid.")
    if not errors:
        if plan_model.code_exists(f["plan_code"], plan_id):
            errors.append("This plan code is already used.")
        if plan_model.name_exists(f["plan_name"], plan_id):
            errors.append("This plan name already exists.")
    return errors


@plans_bp.route("/")
def list_plans():
    plans = plan_model.list_plans()
    return render_template("plan_list.html", plans=plans)


@plans_bp.route("/new", methods=["GET", "POST"])
def register():
    form = {k: "" for k in FIELDS}
    form["access_type"] = "Full Access"
    form["status"] = "active"
    if request.method == "POST":
        form = read_form()
        errors = validate(form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            try:
                plan_model.create_plan(form)
                flash(f"Plan '{form['plan_name']}' saved successfully.", "success")
                return redirect(url_for("plans.list_plans"))
            except sqlite3.IntegrityError:
                flash("A plan with this code already exists.", "error")
    return render_template("plan_form.html", form=form, editing=False,
                           access_types=ACCESS_TYPES)