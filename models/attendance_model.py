from datetime import date, datetime
from database.db import get_db


def search_members(q):
    """Members (not archived) matching member number or name."""
    like = f"%{q}%"
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM members
           WHERE status != 'archived'
             AND (member_number LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                  OR (first_name || ' ' || last_name) LIKE ?)
           ORDER BY first_name, last_name LIMIT 30""",
        (like, like, like, like),
    ).fetchall()
    conn.close()
    return rows


def get_member(member_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    conn.close()
    return row


def get_active_membership(member_id):
    """The member's active membership that has not passed its end date, or None."""
    conn = get_db()
    row = conn.execute(
        """SELECT ms.*, p.plan_name
           FROM memberships ms JOIN membership_plans p ON p.plan_id = ms.plan_id
           WHERE ms.member_id = ? AND ms.status = 'active' AND ms.end_date >= ?
           ORDER BY ms.end_date DESC LIMIT 1""",
        (member_id, date.today().isoformat()),
    ).fetchone()
    conn.close()
    return row


def is_inside(member_id):
    """True if the member has an open visit (checked in, not yet checked out)."""
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM attendance WHERE member_id = ? AND check_out_time IS NULL", (member_id,)
    ).fetchone()
    conn.close()
    return row is not None


def create_checkin(member_id, membership_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO attendance (member_id, membership_id, check_in_time) VALUES (?,?,?)",
            (member_id, membership_id, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_visit(attendance_id):
    conn = get_db()
    row = conn.execute(
        """SELECT a.*, m.member_number, m.first_name, m.last_name,
                  ms.end_date, p.plan_name
           FROM attendance a
           JOIN members m ON m.member_id = a.member_id
           JOIN memberships ms ON ms.membership_id = a.membership_id
           JOIN membership_plans p ON p.plan_id = ms.plan_id
           WHERE a.attendance_id = ?""",
        (attendance_id,),
    ).fetchone()
    conn.close()
    return row