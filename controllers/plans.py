import math
import re
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import plan_model

plans_bp = Blueprint("plans", __name__, url_prefix="/plans")

PLAN_CODE_RE = re.compile(r"^[A-Z0-9]{2,10}$")
ACCESS_TYPES = ("Full Access", "Off-Peak Access", "Gym Floor Only")
STATUSES = ("active", "inactive", "archived")
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
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    if status != "all" and status not in STATUSES:
        status = "all"
    duration_raw = request.args.get("duration", "")
    duration = int(duration_raw) if duration_raw.isdigit() else None
    plans = plan_model.list_plans(q, status, duration)
    return render_template(
        "plan_list.html", plans=plans, q=q, status=status,
        duration=duration, durations=plan_model.get_durations(),
    )


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


@plans_bp.route("/<int:plan_id>")
def view(plan_id):
    plan = plan_model.get_plan(plan_id)
    if plan is None:
        flash("Plan not found.", "error")
        return redirect(url_for("plans.list_plans"))
    return render_template(
        "plan_view.html", plan=plan,
        total_memberships=plan_model.count_memberships(plan_id),
        active_memberships=plan_model.count_active_memberships(plan_id),
    )


@plans_bp.route("/<int:plan_id>/edit", methods=["GET", "POST"])
def edit(plan_id):
    plan = plan_model.get_plan(plan_id)
    if plan is None:
        flash("Plan not found.", "error")
        return redirect(url_for("plans.list_plans"))
    if plan["status"] == "archived":
        flash("Restore this plan before editing it.", "error")
        return redirect(url_for("plans.list_plans", status="archived"))
    if request.method == "POST":
        form = read_form()
        errors = validate(form, plan_id)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            try:
                plan_model.update_plan(plan_id, form)
                flash("Plan updated. Existing memberships keep their original fee and dates.", "success")
                return redirect(url_for("plans.view", plan_id=plan_id))
            except sqlite3.IntegrityError:
                flash("A plan with this code already exists.", "error")
    else:
        form = {k: ("" if plan[k] is None else str(plan[k])) for k in FIELDS}
        form["price"] = f"{plan['price']:.2f}"
    return render_template("plan_form.html", form=form, editing=True,
                           access_types=ACCESS_TYPES)


@plans_bp.route("/<int:plan_id>/status", methods=["POST"])
def change_status(plan_id):
    plan = plan_model.get_plan(plan_id)
    new_status = request.form.get("status")
    if plan is None:
        flash("Plan not found.", "error")
    elif new_status not in STATUSES:
        flash("Invalid status.", "error")
    elif new_status == "archived" and plan_model.count_active_memberships(plan_id) > 0:
        flash("Cannot archive a plan that has active, pending or suspended memberships.", "error")
    else:
        plan_model.set_status(plan_id, new_status)
        flash(f"Plan '{plan['plan_name']}' is now {new_status}.", "success")
    return redirect(request.referrer or url_for("plans.list_plans"))

@plans_bp.route("/compare")
def compare():
    active = plan_model.list_active_plans()
    ids = [int(i) for i in request.args.getlist("ids") if i.isdigit()]
    selected = active
    if ids:
        picked = [p for p in active if p["plan_id"] in ids]
        if len(picked) < 2:
            flash("Select at least 2 plans to compare.", "error")
        else:
            selected = picked

    baseline = next((p for p in active if p["plan_code"] == "MON"), None)
    if baseline is None:
        baseline = next((p for p in active if p["duration_months"] == 1), None)

    rows = []
    for p in selected:
        per_month = p["price"] / p["duration_months"]
        savings = None
        if baseline:
            savings = round((1 - per_month / (baseline["price"] / baseline["duration_months"])) * 100, 1)
        rows.append({"plan": p, "per_month": per_month, "savings": savings})

    best_id = min(rows, key=lambda r: r["per_month"])["plan"]["plan_id"] if rows else None
    return render_template(
        "plan_compare.html", rows=rows, active=active,
        selected_ids=[r["plan"]["plan_id"] for r in rows],
        baseline=baseline, best_id=best_id,
    )