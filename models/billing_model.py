from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from database.db import get_db

MAX_AMOUNT = Decimal("1000000")
CENT = Decimal("0.01")


def _to_decimal(text, label):
    text = (text or "").strip().replace(",", "")
    if text == "":
        return Decimal("0")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} must be a number.")
    if not value.is_finite():
        raise ValueError(f"{label} must be a number.")
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    if value > MAX_AMOUNT:
        raise ValueError(f"{label} is too large.")
    return value


def calculate_bill(plan_price, discount_type, discount_value, charges):
    """Total Amount = Plan Price - Discount + Additional Charges.
    discount_type is 'amount' (pesos) or 'percent'. Raises ValueError with a message."""
    price = Decimal(str(plan_price)).quantize(CENT)
    value = _to_decimal(discount_value, "Discount")
    extra = _to_decimal(charges, "Additional charges").quantize(CENT, ROUND_HALF_UP)

    if discount_type == "percent":
        if value > 100:
            raise ValueError("Discount percent cannot be more than 100.")
        discount = (price * value / 100).quantize(CENT, ROUND_HALF_UP)
    elif discount_type == "amount":
        discount = value.quantize(CENT, ROUND_HALF_UP)
        if discount > price:
            raise ValueError("Discount cannot be more than the plan price.")
    else:
        raise ValueError("Invalid discount type.")

    total = price - discount + extra
    return {"price": price, "discount": discount, "charges": extra, "total": total}


_SELECT = """SELECT ms.*, m.member_number, m.first_name, m.last_name, m.status AS member_status,
                    p.plan_name, p.plan_code,
                    COALESCE((SELECT SUM(pay.amount_paid) FROM payments pay
                              WHERE pay.membership_id = ms.membership_id), 0) AS paid
             FROM memberships ms
             JOIN members m ON m.member_id = ms.member_id
             JOIN membership_plans p ON p.plan_id = ms.plan_id"""


def list_billable(q=""):
    """Memberships that can be billed (everything except cancelled)."""
    sql = _SELECT + " WHERE ms.status != 'cancelled'"
    params = []
    if q:
        like = f"%{q}%"
        sql += """ AND (m.member_number LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ?
                   OR (m.first_name || ' ' || m.last_name) LIKE ? OR p.plan_name LIKE ?)"""
        params = [like] * 5
    sql += " ORDER BY ms.membership_id DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_membership(membership_id):
    conn = get_db()
    row = conn.execute(_SELECT + " WHERE ms.membership_id = ?", (membership_id,)).fetchone()
    conn.close()
    return row