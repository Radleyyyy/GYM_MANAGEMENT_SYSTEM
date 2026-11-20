from datetime import date, timedelta
from database.db import get_db
from models import report_model


def _last_months(n, today):
    """Returns the last n month keys (YYYY-MM), oldest first."""
    y, m = today.year, today.month
    keys = []
    for _ in range(n):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return keys[::-1]


def _series(conn, sql, months):
    data = {r[0]: r[1] for r in conn.execute(sql, (months[0] + "-01",))}
    return [data.get(k) or 0 for k in months]


def dashboard_data(today=None, months_back=6):
    today = today or date.today()
    t = today.isoformat()
    limit = (today + timedelta(days=30)).isoformat()
    month = t[:7]
    months = _last_months(months_back, today)
    conn = get_db()
    try:
        one = lambda sql, *p: conn.execute(sql, p).fetchone()[0]
        kpi = {
            "total_members": one("SELECT COUNT(*) FROM members WHERE status != 'archived'"),
            "active_members": one("SELECT COUNT(*) FROM members WHERE status = 'active'"),
            "expired_members": one(
                """SELECT COUNT(DISTINCT member_id) FROM memberships
                   WHERE status = 'expired' AND member_id NOT IN
                     (SELECT member_id FROM memberships WHERE status IN ('active','pending'))"""),
            "expiring": one(
                "SELECT COUNT(*) FROM memberships WHERE status = 'active' AND end_date BETWEEN ? AND ?",
                t, limit),
            "active_memberships": one("SELECT COUNT(*) FROM memberships WHERE status = 'active'"),
            "attendance_today": one(
                "SELECT COUNT(*) FROM attendance WHERE date(check_in_time) = ?", t),
            "inside_now": one("SELECT COUNT(*) FROM attendance WHERE check_out_time IS NULL"),
            "monthly_revenue": one(
                "SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE substr(payment_date, 1, 7) = ?",
                month),
            # Lab 36: counts for the workflow strip
            "plans": one("SELECT COUNT(*) FROM membership_plans WHERE status = 'active'"),
            "memberships_total": one("SELECT COUNT(*) FROM memberships WHERE status != 'cancelled'"),
            "awaiting_payment": one(
                """SELECT COUNT(*) FROM memberships WHERE status = 'pending'
                   AND membership_id NOT IN (SELECT membership_id FROM payments)"""),
            "payments_month": one(
                "SELECT COUNT(*) FROM payments WHERE substr(payment_date, 1, 7) = ?", month),
            "renewals": one(
                """SELECT COUNT(*) FROM memberships
                   WHERE is_renewal = 1 AND substr(date(created_at), 1, 7) = ?""", month),
        }

        new_members = _series(conn, """SELECT substr(registration_date, 1, 7), COUNT(*) FROM members
                                       WHERE registration_date >= ? GROUP BY 1""", months)
        attendance = _series(conn, """SELECT substr(check_in_time, 1, 7), COUNT(*) FROM attendance
                                      WHERE date(check_in_time) >= ? GROUP BY 1""", months)
        revenue = _series(conn, """SELECT substr(payment_date, 1, 7), SUM(amount_paid) FROM payments
                                   WHERE payment_date >= ? GROUP BY 1""", months)
        plans = conn.execute(
            """SELECT p.plan_name, COUNT(ms.membership_id) FROM membership_plans p
               LEFT JOIN memberships ms ON ms.plan_id = p.plan_id AND ms.status != 'cancelled'
               GROUP BY p.plan_id ORDER BY p.duration_months""").fetchall()
        methods = conn.execute(
            """SELECT pm.method_name, COUNT(*) FROM payments pay
               JOIN payment_methods pm ON pm.method_id = pay.method_id
               GROUP BY pm.method_id ORDER BY 2 DESC""").fetchall()
        ends = [r[0] for r in conn.execute(
            "SELECT end_date FROM memberships WHERE status = 'active' AND end_date BETWEEN ? AND ?",
            (t, limit))]
    finally:
        conn.close()

    revenue_info = report_model.revenue_report(t, t)
    kpi["outstanding"] = revenue_info["outstanding"]
    kpi["with_balance"] = revenue_info["counts"]["partial"] + revenue_info["counts"]["unpaid"]

    buckets = {"Today": 0, "1-7 days": 0, "8-14 days": 0, "15-30 days": 0}
    for e in ends:
        d = (date.fromisoformat(e) - today).days
        key = ("Today" if d == 0 else "1-7 days" if d <= 7 else
               "8-14 days" if d <= 14 else "15-30 days")
        buckets[key] += 1

    return {
        "kpi": kpi,
        "charts": {
            "months": months,
            "new_members": new_members,
            "attendance": attendance,
            "revenue": revenue,
            "plans": {"labels": [p[0] for p in plans], "values": [p[1] for p in plans]},
            "methods": {"labels": [m[0] for m in methods], "values": [m[1] for m in methods]},
            "expiring": {"labels": list(buckets), "values": list(buckets.values())},
        },
    }
