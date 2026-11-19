from datetime import date, timedelta
from database.db import get_db

AGE_GROUPS = [("Under 18", 0, 17), ("18-24", 18, 24), ("25-34", 25, 34),
              ("35-44", 35, 44), ("45-54", 45, 54), ("55 and above", 55, 200)]


def _age(dob, today):
    born = date.fromisoformat(dob)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def valid_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return None


def member_report(date_from, date_to, today=None):
    """Lab 25. date_from/date_to (ISO strings) filter the 'new members' and
    'registration date' sections. Counts for total/active/inactive/gender/age cover all members."""
    today = today or date.today()
    conn = get_db()
    try:
        members = conn.execute(
            "SELECT member_id, gender, date_of_birth, registration_date, status FROM members"
        ).fetchall()
        by_status = {"active": 0, "inactive": 0, "archived": 0}
        for m in members:
            by_status[m["status"]] += 1

        gender = {"Male": 0, "Female": 0, "Other": 0}
        ages = {label: 0 for label, _, _ in AGE_GROUPS}
        for m in members:
            if m["status"] == "archived":
                continue
            gender[m["gender"]] += 1
            a = _age(m["date_of_birth"], today)
            for label, lo, hi in AGE_GROUPS:
                if lo <= a <= hi:
                    ages[label] += 1
                    break

        new_rows = conn.execute(
            """SELECT member_number, first_name, last_name, registration_date, status
               FROM members WHERE registration_date BETWEEN ? AND ?
               ORDER BY registration_date DESC, member_id DESC""", (date_from, date_to)).fetchall()
        by_month = conn.execute(
            """SELECT substr(registration_date, 1, 7) AS month, COUNT(*) AS total
               FROM members WHERE registration_date BETWEEN ? AND ?
               GROUP BY month ORDER BY month DESC""", (date_from, date_to)).fetchall()
    finally:
        conn.close()

    return {
        "total": len(members),
        "active": by_status["active"],
        "inactive": by_status["inactive"],
        "archived": by_status["archived"],
        "gender": gender,
        "ages": ages,
        "new_members": new_rows,
        "by_month": by_month,
    }


def default_range(today=None):
    today = today or date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


# ===== Lab 26: membership reports =====
MEMBERSHIP_VIEWS = {
    "active":    ("Active Memberships", "Status is active"),
    "expired":   ("Expired Memberships", "Status is expired"),
    "expiring":  ("Expiring Memberships", "Active, ends in the next 30 days"),
    "new":       ("New Memberships", "First memberships created in date range"),
    "renewed":   ("Renewed Memberships", "Renewals created in date range"),
    "cancelled": ("Cancelled Memberships", "Status is cancelled"),
}

_MS_SELECT = """SELECT ms.membership_id, ms.start_date, ms.end_date, ms.membership_fee, ms.status,
                       ms.is_renewal, date(ms.created_at) AS created_date,
                       m.member_number, m.first_name, m.last_name, p.plan_name
                FROM memberships ms
                JOIN members m ON m.member_id = ms.member_id
                JOIN membership_plans p ON p.plan_id = ms.plan_id"""


def _membership_condition(view, date_from, date_to, today):
    t = today.isoformat()
    limit = (today + timedelta(days=30)).isoformat()
    return {
        "active": (" WHERE ms.status = 'active'", []),
        "expired": (" WHERE ms.status = 'expired'", []),
        "expiring": (" WHERE ms.status = 'active' AND ms.end_date BETWEEN ? AND ?", [t, limit]),
        "new": (" WHERE ms.is_renewal = 0 AND date(ms.created_at) BETWEEN ? AND ?", [date_from, date_to]),
        "renewed": (" WHERE ms.is_renewal = 1 AND date(ms.created_at) BETWEEN ? AND ?", [date_from, date_to]),
        "cancelled": (" WHERE ms.status = 'cancelled'", []),
    }[view]


def membership_report(view, date_from, date_to, today=None):
    today = today or date.today()
    conn = get_db()
    try:
        counts = {}
        for key in MEMBERSHIP_VIEWS:
            cond, params = _membership_condition(key, date_from, date_to, today)
            counts[key] = conn.execute(
                "SELECT COUNT(*) FROM memberships ms" + cond, params).fetchone()[0]
        cond, params = _membership_condition(view, date_from, date_to, today)
        rows = conn.execute(_MS_SELECT + cond + " ORDER BY ms.end_date, ms.membership_id", params).fetchall()
        by_plan = conn.execute(
            """SELECT p.plan_name, COUNT(ms.membership_id) AS total,
                      COALESCE(SUM(ms.status = 'active'), 0) AS active,
                      COALESCE(SUM(ms.status = 'expired'), 0) AS expired,
                      COALESCE(SUM(ms.status = 'cancelled'), 0) AS cancelled
               FROM membership_plans p LEFT JOIN memberships ms ON ms.plan_id = p.plan_id
               GROUP BY p.plan_id ORDER BY p.duration_months""").fetchall()
    finally:
        conn.close()
    return {"counts": counts, "rows": rows, "by_plan": by_plan}
