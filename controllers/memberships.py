import sqlite3
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import member_model, plan_model, membership_model

memberships_bp = Blueprint("memberships", __name__, url_prefix="/memberships")


@memberships_bp.route("/register", methods=["GET", "POST"])
def register():
    form = {
        "member_id": request.args.get("member_id", ""),
        "plan_id": request.args.get("plan_id", ""),
        "start_date": date.today().isoformat(),
    }
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        errors = []

        member = None
        if form["member_id"].isdigit():
            member = member_model.get_member(int(form["member_id"]))
        if member is None:
            errors.append("Please select a member.")
        elif member["status"] != "active":
            errors.append("Only active members can register for a membership.")
        elif membership_model.has_open_membership(member["member_id"]):
            errors.append("This member already has an active or pending membership.")

        plan = None
        if form["plan_id"].isdigit():
            plan = plan_model.get_plan(int(form["plan_id"]))
        if plan is None:
            errors.append("Please select a plan.")
        elif plan["status"] != "active":
            errors.append("The selected plan is not available.")

        start = None
        try:
            start = date.fromisoformat(form["start_date"])
            if start < date.today():
                errors.append("Start date cannot be in the past.")
        except ValueError:
            errors.append("Start date is invalid.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            end = membership_model.add_months(start, plan["duration_months"])
            try:
                membership_model.create_membership(member["member_id"], plan, start, end)
                flash(f"Membership registered for {member['first_name']} {member['last_name']} "
                      f"({plan['plan_name']}, {start} to {end}).", "success")
                return redirect(url_for("members.view", member_id=member["member_id"]))
            except sqlite3.IntegrityError:
                flash("This member already has an active membership.", "error")

    return render_template(
        "membership_form.html", form=form,
        members=membership_model.list_registrable_members(),
        plans=plan_model.list_active_plans(),
        today=date.today().isoformat(),
    )