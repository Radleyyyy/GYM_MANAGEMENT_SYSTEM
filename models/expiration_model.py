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
