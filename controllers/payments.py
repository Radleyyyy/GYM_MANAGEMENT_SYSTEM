from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from models import payment_model, billing_model

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/")
def list_payments():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    payments = payment_model.list_payments(q, status)
    return render_template("payment_list.html", payments=payments, q=q, status=status)


@payments_bp.route("/new/<int:membership_id>", methods=["GET", "POST"])
def new_payment(membership_id):
    ctx = payment_model.get_pay_context(membership_id)
    if ctx is None:
        flash("Membership not found.", "error")
        return redirect(url_for("billing.list_memberships"))
    if ctx["membership"]["status"] == "cancelled":
        flash("A cancelled membership cannot receive payments.", "error")
        return redirect(url_for("billing.list_memberships"))
    if ctx["outstanding"] is not None and ctx["outstanding"] <= 0:
        flash("This membership is already fully paid.", "info")
        return redirect(url_for("payments.list_payments", q=ctx["membership"]["member_number"]))

    form = {
        "discount_type": "amount", "discount": "", "charges": "",
        "method_id": "", "amount_paid": "",
    }
    if request.method == "POST":
        for key in form:
            form[key] = request.form.get(key, form[key]).strip()
        try:
            payment_id = payment_model.record_payment(
                membership_id, form["method_id"], form["amount_paid"],
                form["discount_type"], form["discount"], form["charges"],
                received_by=g.user["user_id"])
        except ValueError as e:
            flash(str(e), "error")
        else:
            after = billing_model.get_membership(membership_id)
            msg = "Payment recorded."
            if ctx["membership"]["status"] == "pending" and after["status"] == "active":
                msg += " The membership is now active."
            elif after["status"] == "pending":
                msg += f" The membership will become active on its start date ({after['start_date']})."
            flash(msg, "success")
            return redirect(url_for("payments.view_payment", payment_id=payment_id))

    return render_template("payment_form.html", ctx=ctx, m=ctx["membership"], form=form,
                           methods=payment_model.list_methods())


@payments_bp.route("/<int:payment_id>")
def view_payment(payment_id):
    payment = payment_model.get_payment(payment_id)
    if payment is None:
        flash("Payment not found.", "error")
        return redirect(url_for("payments.list_payments"))
    return render_template("payment_view.html", p=payment)


@payments_bp.route("/<int:payment_id>/receipt")
def receipt(payment_id):
    payment = payment_model.get_payment(payment_id)
    if payment is None:
        flash("Payment not found.", "error")
        return redirect(url_for("payments.list_payments"))
    return render_template("payment_receipt.html", p=payment, gym_name="GymPro")
