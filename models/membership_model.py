import calendar
from datetime import date
from database.db import get_db


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