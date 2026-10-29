from datetime import date
from database.db import get_db

TYPE_LABELS = {
    "30_days": "30 days before",
    "7_days": "7 days before",
    "1_day": "1 day before",
    "expired": "Expired",
}


def _type_for(days_left):
    """Pick the one notification type that fits the days left."""
    if days_left < 0:
        return "expired"
    if days_left <= 1:
        return "1_day"
    if days_left <= 7:
        return "7_days"
    if days_left <= 30:
        return "30_days"
    return None


def _message(ntype, days_left):
    if ntype == "expired":
        return ("Notice: Your gym membership has expired. "
                "Please renew your membership to continue accessing the gym.")
    if days_left == 0:
        when = "today"
    else:
        when = f"in {days_left} day{'s' if days_left != 1 else ''}"
    return (f"Reminder: Your gym membership will expire {when}. "
            "Please renew your membership to continue accessing the gym.")


def generate_notifications(today=None):
    """Creates reminders for memberships that are 30/7/1 days from expiring, or expired.
    Each membership gets each notification type only once. Returns how many were created."""
    today = today or date.today()
    conn = get_db()
    created = 0
    try:
        rows = conn.execute(
            """SELECT membership_id, member_id, end_date FROM memberships
               WHERE status IN ('active','pending','expired')""").fetchall()
        for r in rows:
            days_left = (date.fromisoformat(r["end_date"]) - today).days
            ntype = _type_for(days_left)
            if ntype is None:
                continue
            cur = conn.execute(
                """INSERT OR IGNORE INTO notifications
                   (member_id, membership_id, notification_type, message) VALUES (?,?,?,?)""",
                (r["member_id"], r["membership_id"], ntype, _message(ntype, days_left)))
            created += cur.rowcount
        conn.commit()
        return created
    finally:
        conn.close()


def list_notifications(unread_only=False):
    sql = """SELECT n.*, m.member_number, m.first_name, m.last_name
             FROM notifications n JOIN members m ON m.member_id = n.member_id"""
    if unread_only:
        sql += " WHERE n.is_read = 0"
    sql += " ORDER BY n.notification_id DESC"
    conn = get_db()
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def unread_count():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0").fetchone()[0]
    conn.close()
    return n


def mark_read(notification_id=None):
    """Mark one notification (or all when None) as read."""
    conn = get_db()
    if notification_id is None:
        conn.execute("UPDATE notifications SET is_read = 1")
    else:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE notification_id = ?",
                     (notification_id,))
    conn.commit()
    conn.close()
