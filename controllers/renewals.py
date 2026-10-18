import sqlite3
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import plan_model, renewal_model

renewals_bp = Blueprint("renewals", __name__, url_prefix="/renewals")


@renewals_bp.route("/")
def search():
    q = request.args.get("q", "").strip()
    results = renewal_model.search_members(q)
    return render_template("renewal_search.html", results=results, q=q)


@renewals_bp.route("/<int:member_id>", methods=["GET", "POST"])
def renew(member_id):
    ctx = renewal_model.get_context(member_id)
    if ctx is None:
        flash("Member not found.", "error")
        return redirect(url_for("renewals.search"))
    if not ctx["eligible"]:
        flash(ctx["reason"], "error")
        return redirect(url_for("renewals.search", q=ctx["member"]["member_number"]))

    current = ctx["current"]
    current_end = date.fromisoformat(current["end_date"])
    plans = plan_model.list_active_plans()
    selected = str(current["plan_id"])

    if request.method == "POST":
        selected = request.form.get("plan_id", "").strip()
        plan = plan_model.get_plan(int(selected)) if selected.isdigit() else None
        if plan is None:
            flash("Please select a renewal plan.", "error")
        elif plan["status"] != "active":
            flash("The selected plan is not available.", "error")
        elif not 1 <= plan["duration_months"] <= renewal_model.MAX_DURATION_MONTHS:
            flash("The selected plan has an invalid duration.", "error")
        else:
            start, end = renewal_model.calculate_period(current_end, plan["duration_months"])
            try:
                _, status = renewal_model.save_renewal(member_id, plan, start, end)
                flash(f"Membership renewed ({plan['plan_name']}, {start} to {end}, "
                      f"₱{plan['price']:,.2f}). Status: {status}.", "success")
                return redirect(url_for("members.view", member_id=member_id))
            except sqlite3.IntegrityError:
                flash("Could not save the renewal: the member already has an active membership.", "error")

    base_start = max(current_end.toordinal() + 1, date.today().toordinal())
    return render_template("renewal_form.html", ctx=ctx, plans=plans, selected=selected,
                           base_start=date.fromordinal(base_start).isoformat())