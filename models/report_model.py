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


# ===== Lab 27: attendance reports =====
def attendance_report(date_from, date_to):
    """All figures cover visits whose check-in date falls between date_from and date_to."""
    where = "date(a.check_in_time) BETWEEN ? AND ?"
    p = (date_from, date_to)
    conn = get_db()
    try:
        summary = conn.execute(
            f"""SELECT COUNT(*) AS visits, COUNT(DISTINCT a.member_id) AS members,
                       AVG(a.duration_minutes) AS avg_minutes
                FROM attendance a WHERE {where}""", p).fetchone()
        daily = conn.execute(
            f"""SELECT date(a.check_in_time) AS day, COUNT(*) AS visits,
                       COUNT(DISTINCT a.member_id) AS members
                FROM attendance a WHERE {where} GROUP BY day ORDER BY day DESC""", p).fetchall()
        weekly = conn.execute(
            f"""SELECT date(a.check_in_time, '-6 days', 'weekday 1') AS week, COUNT(*) AS visits,
                       COUNT(DISTINCT a.member_id) AS members
                FROM attendance a WHERE {where} GROUP BY week ORDER BY week DESC""", p).fetchall()
        monthly = conn.execute(
            f"""SELECT substr(a.check_in_time, 1, 7) AS month, COUNT(*) AS visits,
                       COUNT(DISTINCT a.member_id) AS members
                FROM attendance a WHERE {where} GROUP BY month ORDER BY month DESC""", p).fetchall()
        by_member = conn.execute(
            f"""SELECT m.member_number, m.first_name, m.last_name, COUNT(*) AS visits,
                       COALESCE(SUM(a.duration_minutes), 0) AS total_minutes,
                       AVG(a.duration_minutes) AS avg_minutes,
                       MAX(a.check_in_time) AS last_visit
                FROM attendance a JOIN members m ON m.member_id = a.member_id
                WHERE {where} GROUP BY m.member_id
                ORDER BY visits DESC, m.last_name""", p).fetchall()
        hours = {r["hr"]: r["n"] for r in conn.execute(
            f"""SELECT CAST(substr(a.check_in_time, 12, 2) AS INTEGER) AS hr, COUNT(*) AS n
                FROM attendance a WHERE {where} GROUP BY hr""", p)}
    finally:
        conn.close()

    days = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1
    peak = max(hours.values()) if hours else 0
    peak_rows = [{"hour": f"{h:02d}:00 - {h:02d}:59", "visits": hours.get(h, 0),
                  "is_peak": peak > 0 and hours.get(h, 0) == peak,
                  "pct": round(hours.get(h, 0) * 100 / peak) if peak else 0}
                 for h in range(24) if hours.get(h, 0) > 0]
    return {
        "visits": summary["visits"],
        "members": summary["members"],
        "avg_minutes": summary["avg_minutes"],
        "avg_per_day": summary["visits"] / days,
        "avg_per_member": summary["visits"] / summary["members"] if summary["members"] else 0,
        "daily": daily, "weekly": weekly, "monthly": monthly,
        "by_member": by_member, "top_members": by_member[:5], "peak_hours": peak_rows,
    }
