from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date
from database.db import get_db
from models import billing_model

CENT = Decimal("0.01")

_SELECT = """SELECT pay.*, m.member_number, m.first_name, m.last_name,
                    pm.method_name, ms.start_date, ms.end_date, p.plan_name
             FROM payments pay
             JOIN members m ON m.member_id = pay.member_id
             JOIN memberships ms ON ms.membership_id = pay.membership_id
             JOIN membership_plans p ON p.plan_id = ms.plan_id
             JOIN payment_methods pm ON pm.method_id = pay.method_id"""


def list_payments(q="", status=""):
    sql = _SELECT + " WHERE 1=1"
    params = []
    if q:
        like = f"%{q}%"
        sql += """ AND (pay.payment_number LIKE ? OR m.member_number LIKE ? OR m.first_name LIKE ?
                   OR m.last_name LIKE ? OR (m.first_name || ' ' || m.last_name) LIKE ?)"""
        params += [like] * 5
    if status in ("paid", "partial", "unpaid"):
        sql += " AND pay.payment_status = ?"
        params.append(status)
    sql += " ORDER BY pay.payment_id DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_payment(payment_id):
    conn = get_db()
    row = conn.execute(_SELECT + " WHERE pay.payment_id = ?", (payment_id,)).fetchone()
    conn.close()
    return row


def list_methods():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM payment_methods WHERE status = 'active' ORDER BY method_id").fetchall()
    conn.close()
    return rows


def get_pay_context(membership_id):
    """Returns the membership, its payment history and the outstanding balance.
    outstanding is None when no payment exists yet (first payment: bill is computed)."""
    membership = billing_model.get_membership(membership_id)
    if membership is None:
        return None
    conn = get_db()
    last = conn.execute(
        "SELECT * FROM payments WHERE membership_id = ? ORDER BY payment_id DESC LIMIT 1",
        (membership_id,)).fetchone()
    conn.close()
    outstanding = None if last is None else Decimal(str(last["balance"])).quantize(CENT)
    return {"membership": membership, "last": last, "outstanding": outstanding}


def _next_payment_number(conn):
    row = conn.execute("SELECT COALESCE(MAX(payment_id), 0) + 1 AS n FROM payments").fetchone()
    return f"PAY-{row['n']:04d}"


def record_payment(membership_id, method_id, amount_paid_text,
                   discount_type="amount", discount="", charges=""):
    """Validates and saves one payment. Returns the new payment_id. Raises ValueError."""
    ctx = get_pay_context(membership_id)
    if ctx is None:
        raise ValueError("Membership not found.")
    ms = ctx["membership"]
    if ms["status"] == "cancelled":
        raise ValueError("A cancelled membership cannot receive payments.")

    if ctx["outstanding"] is None:
        bill = billing_model.calculate_bill(ms["membership_fee"], discount_type, discount, charges)
        price, disc, extra, due = bill["price"], bill["discount"], bill["charges"], bill["total"]
    else:
        if ctx["outstanding"] <= 0:
            raise ValueError("This membership is already fully paid.")
        price = Decimal(str(ms["membership_fee"])).quantize(CENT)
        disc = extra = Decimal("0")
        due = ctx["outstanding"]

    text = (amount_paid_text or "").strip().replace(",", "")
    try:
        paid = Decimal(text)
    except InvalidOperation:
        raise ValueError("Amount paid must be a number.")
    if not paid.is_finite():
        raise ValueError("Amount paid must be a number.")
    paid = paid.quantize(CENT, ROUND_HALF_UP)
    if paid <= 0:
        raise ValueError("Amount paid must be greater than zero.")
    if paid > due:
        raise ValueError(f"Amount paid cannot be more than the amount due (₱{due:,.2f}).")

    balance = due - paid
    status = "paid" if balance == 0 else "partial"

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        method = conn.execute(
            "SELECT method_id FROM payment_methods WHERE method_id = ? AND status = 'active'",
            (method_id,)).fetchone()
        if method is None:
            raise ValueError("Please select a valid payment method.")
        # Re-check the balance inside the transaction so two cashiers cannot overpay
        last = conn.execute(
            "SELECT balance FROM payments WHERE membership_id = ? ORDER BY payment_id DESC LIMIT 1",
            (membership_id,)).fetchone()
        current = None if last is None else Decimal(str(last["balance"])).quantize(CENT)
        if current != ctx["outstanding"]:
            raise ValueError("This membership was just updated by another payment. Please try again.")
        cur = conn.execute(
            """INSERT INTO payments (payment_number, member_id, membership_id, method_id,
                   payment_date, plan_price, discount, additional_charges,
                   amount_due, amount_paid, balance, payment_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (_next_payment_number(conn), ms["member_id"], membership_id, method["method_id"],
             date.today().isoformat(), float(price), float(disc), float(extra),
             float(due), float(paid), float(balance), status))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()