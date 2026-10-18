import calendar
from datetime import date
from database.db import get_db


STATUS_RULES = {
    "pending": ["active", "cancelled"],
    "active": ["suspended", "cancelled"],
    "suspended": ["active", "cancelled"],
    "expired": [],
    "cancelled": [],
}


def add_months(start, months):
    """Return the date `months` after `start` (clamps to the last day of the month)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def list_registrable_members():
    conn = get_db()
    rows = conn.execute(
        """SELECT member_id, member_number, first_name, last_name
           FROM members WHERE status = 'active'
           ORDER BY first_name, last_name"""
    ).fetchall()
    conn.close()
    return rows


def has_open_membership(member_id):
    """True if the member already has an active or pending membership."""
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM memberships WHERE member_id = ? AND status IN ('active','pending')",
        (member_id,),
    ).fetchone()
    conn.close()
    return row is not None


def create_membership(member_id, plan, start, end):
    """Insert the membership and its expiration record in one transaction."""
    # Last line of defense: never save a wrongly calculated expiration date
    if end <= start or end != add_months(start, plan["duration_months"]):
        raise ValueError("Incorrect expiration date for the selected plan.")
    status = "active" if start <= date.today() else "pending"
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO memberships
               (member_id, plan_id, start_date, end_date, membership_fee, status)
               VALUES (?,?,?,?,?,?)""",
            (member_id, plan["plan_id"], start.isoformat(), end.isoformat(),
             plan["price"], status),
        )
        membership_id = cur.lastrowid
        conn.execute(
            """INSERT INTO expiration_records (membership_id, expiration_date, expiry_status)
               VALUES (?,?,'active')""",
            (membership_id, end.isoformat()),
        )
        conn.commit()
        return membership_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_membership(membership_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM memberships WHERE membership_id = ?", (membership_id,)
    ).fetchone()
    conn.close()
    return row


def change_status(membership_id, new_status):
    """Move a membership to a new status. Returns (ok, message)."""
    membership = get_membership(membership_id)
    if membership is None:
        return False, "Membership not found."
    current = membership["status"]
    if new_status not in STATUS_RULES.get(current, []):
        return False, f"Changing {current} to {new_status} is not allowed."
    if new_status == "active" and membership["end_date"] < date.today().isoformat():
        return False, "This membership already passed its end date."
    conn = get_db()
    conn.execute(
        "UPDATE memberships SET status = ? WHERE membership_id = ?",
        (new_status, membership_id),
    )
    conn.commit()
    conn.close()
    return True, f"Membership is now {new_status}."

def list_memberships():
    conn = get_db()
    rows = conn.execute(
        """SELECT ms.membership_id, ms.start_date, ms.end_date, ms.membership_fee,
                  ms.status, m.member_id, m.member_number, m.first_name, m.last_name,
                  p.plan_name
           FROM memberships ms
           JOIN members m ON m.member_id = ms.member_id
           JOIN membership_plans p ON p.plan_id = ms.plan_id
           ORDER BY ms.membership_id DESC"""
    ).fetchall()
    conn.close()
    return rows

def mark_expired_memberships():
    """Mark active/pending memberships past their end date as expired. Returns how many changed."""
    today = date.today().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """UPDATE expiration_records
               SET expiry_status = 'expired', last_checked = CURRENT_TIMESTAMP
               WHERE membership_id IN (
                   SELECT membership_id FROM memberships
                   WHERE status IN ('active','pending') AND end_date < ?)""",
            (today,),
        )
        cur = conn.execute(
            "UPDATE memberships SET status = 'expired' WHERE status IN ('active','pending') AND end_date < ?",
            (today,),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()