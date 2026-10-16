import sqlite3
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import member_model, plan_model, membership_model

memberships_bp = Blueprint("memberships", __name__, url_prefix="/memberships")

MAX_ADVANCE_DAYS = 365      # a membership may start at most 1 year from today
MAX_DURATION_MONTHS = 60    # sanity limit for a plan's duration


def validate(form):
    """Lab 10: check every rule. Returns (errors, member, plan, start, end)."""
    errors = []

    # 1. Member must exist, be active, and have no active/pending membership
    member = None
    if form["member_id"].isdigit():
        member = member_model.get_member(int(form["member_id"]))
    if member is None:
        errors.append("Please select a valid member.")
    elif member["status"] != "active":
        errors.append("Membership cannot be registered for an inactive or archived member.")
    elif membership_model.has_open_membership(member["member_id"]):
        errors.append("This member already has an active or pending membership.")

    # 2. Plan must exist, be active, and have a valid duration
    plan = None
    if form["plan_id"].isdigit():
        plan = plan_model.get_plan(int(form["plan_id"]))
    if plan is None:
        errors.append("Please select a valid plan.")
    else:
        if plan["status"] != "active":
            errors.append("The selected plan is not available.")
        if not 1 <= plan["duration_months"] <= MAX_DURATION_MONTHS:
            errors.append("The selected plan has an invalid duration.")
        if plan["price"] < 0:
            errors.append("The selected plan has an invalid price.")

    # 3. Start date must be a real date, not in the past, not too far ahead
    start = None
    try:
        start = date.fromisoformat(form["start_date"])
        today = date.today()
        if start < today:
            errors.append("Start date cannot be in the past.")
        elif start > today + timedelta(days=MAX_ADVANCE_DAYS):
            errors.append("Start date cannot be more than 1 year from today.")
    except ValueError:
        errors.append("Start date is invalid.")

    # 4. Expiration date is always calculated by the system, then re-checked
    end = None
    if plan is not None and start is not None and not any("duration" in e for e in errors):
        end = membership_model.add_months(start, plan["duration_months"])
        if end <= start:
            errors.append("Expiration date must be after the start date.")

    return errors, member, plan, start, end


@memberships_bp.route("/register", methods=["GET", "POST"])
def register():
    form = {
        "member_id": request.args.get("member_id", ""),
        "plan_id": request.args.get("plan_id", ""),
        "start_date": date.today().isoformat(),
    }
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        errors, member, plan, start, end = validate(form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            try:
                membership_model.create_membership(member["member_id"], plan, start, end)
                flash(f"Membership registered for {member['first_name']} {member['last_name']} "
                      f"({plan['plan_name']}, {start} to {end}).", "success")
                return redirect(url_for("members.view", member_id=member["member_id"]))
            except ValueError as e:
                flash(str(e), "error")
            except sqlite3.IntegrityError:
                flash("This member already has an active membership.", "error")

    return render_template(
        "membership_form.html", form=form,
        members=membership_model.list_registrable_members(),
        plans=plan_model.list_active_plans(),
        today=date.today().isoformat(),
        max_date=(date.today() + timedelta(days=MAX_ADVANCE_DAYS)).isoformat(),
    )