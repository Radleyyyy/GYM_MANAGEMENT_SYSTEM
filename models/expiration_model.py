from datetime import date, timedelta
from database.db import get_db

# key -> (label, description)
FILTERS = {
    "active":  ("Active", "Not yet expired"),
    "today":   ("Expiring Today", "Ends today"),
    "7days":   ("Within 7 Days", "Ends in 0-7 days"),
    "30days":  ("Within 30 Days", "Ends in 0-30 days"),
    "expired": ("Expired", "End date has passed"),
}

_SELECT = """SELECT ms.membership_id, ms.start_date, ms.end_date, ms.status,
                    m.member_id, m.member_number, m.first_name, m.last_name,
                    m.contact_number, p.plan_name
             FROM memberships ms
             JOIN members m ON m.member_id = ms.member_id
             JOIN membership_plans p ON p.plan_id = ms.plan_id
             WHERE ms.status != 'cancelled'"""


def _condition(key, today):
    """Returns (sql_condition, params) for one filter."""
    t = today.isoformat()
    if key == "active":
        return " AND ms.status = 'active' AND ms.end_date >= ?", [t]
    if key == "today":
        return " AND ms.status IN ('active','pending') AND ms.end_date = ?", [t]
    if key in ("7days", "30days"):
        days = 7 if key == "7days" else 30
        limit = (today + timedelta(days=days)).isoformat()
        return " AND ms.status IN ('active','pending') AND ms.end_date BETWEEN ? AND ?", [t, limit]
    if key == "expired":
        return " AND ms.end_date < ?", [t]
    return "", []


def list_memberships(key, today=None):
    today = today or date.today()
    cond, params = _condition(key, today)
    conn = get_db()
    rows = conn.execute(_SELECT + cond + " ORDER BY ms.end_date, m.last_name", params).fetchall()
    conn.close()
    result = []
    for r in rows:
        row = dict(r)
        row["days_left"] = (date.fromisoformat(r["end_date"]) - today).days
        result.append(row)
    return result


def counts(today=None):
    today = today or date.today()
    return {key: len(list_memberships(key, today)) for key in FILTERS}


def update_statuses(today=None):
    """Lab 23: automatic expiration processing.
    expiration_records.expiry_status: end > today -> active, end = today -> expiring, end < today -> expired.
    memberships.status: active/pending memberships past their end date become expired.
    Cancelled and suspended memberships are left alone.
    Returns how many memberships were newly marked expired."""
    t = (today or date.today()).isoformat()
    conn = get_db()
    try:
        # make sure every live membership has an expiration record
        conn.execute(
            """INSERT INTO expiration_records (membership_id, expiration_date, expiry_status)
               SELECT membership_id, end_date, 'active' FROM memberships
               WHERE status IN ('active','pending','expired')
                 AND membership_id NOT IN (SELECT membership_id FROM expiration_records)""")
        conn.execute(
            """UPDATE expiration_records
               SET expiration_date = (SELECT end_date FROM memberships ms
                                      WHERE ms.membership_id = expiration_records.membership_id),
                   expiry_status = CASE
                       WHEN expiration_date > ? THEN 'active'
                       WHEN expiration_date = ? THEN 'expiring'
                       ELSE 'expired' END,
                   last_checked = CURRENT_TIMESTAMP
               WHERE membership_id IN (SELECT membership_id FROM memberships
                                       WHERE status IN ('active','pending','expired'))""",
            (t, t))
        cur = conn.execute(
            "UPDATE memberships SET status = 'expired' "
            "WHERE status IN ('active','pending') AND end_date < ?", (t,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
