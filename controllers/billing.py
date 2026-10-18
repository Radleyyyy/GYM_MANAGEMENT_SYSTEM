from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import billing_model

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")


@billing_bp.route("/")
def list_memberships():
    q = request.args.get("q", "").strip()
    memberships = billing_model.list_billable(q)
    return render_template("billing_list.html", memberships=memberships, q=q)


@billing_bp.route("/<int:membership_id>")
def bill(membership_id):
    membership = billing_model.get_membership(membership_id)
    if membership is None:
        flash("Membership not found.", "error")
        return redirect(url_for("billing.list_memberships"))
    if membership["status"] == "cancelled":
        flash("A cancelled membership cannot be billed.", "error")
        return redirect(url_for("billing.list_memberships"))

    form = {
        "discount_type": request.args.get("discount_type", "amount"),
        "discount": request.args.get("discount", ""),
        "charges": request.args.get("charges", ""),
    }
    result = None
    if request.args.get("calc"):
        try:
            result = billing_model.calculate_bill(
                membership["membership_fee"], form["discount_type"],
                form["discount"], form["charges"])
        except ValueError as e:
            flash(str(e), "error")
    return render_template("billing_form.html", m=membership, form=form, bill=result)