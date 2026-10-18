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


# ===== Lab 14: attendance validation =====
def get_latest_membership(member_id):
    """The member's most recent membership (any status), or None."""
    conn = get_db()
    row = conn.execute(
        """SELECT * FROM memberships WHERE member_id = ?
           ORDER BY end_date DESC, membership_id DESC LIMIT 1""",
        (member_id,),
    ).fetchone()
    conn.close()
    return row


def validate_checkin(member_id):
    """Check every access rule. Returns a dict:
    {"ok": bool, "reason": "Access Denied – ..." or "", "member": row, "membership": row}"""
    result = {"ok": False, "reason": "", "member": None, "membership": None}

    # 1. Member exists
    member = get_member(member_id)
    result["member"] = member
    if member is None:
        result["reason"] = "Access Denied – Member Not Found"
        return result

    # 2. Member is active
    if member["status"] != "active":
        result["reason"] = f"Access Denied – Member {member['status'].capitalize()}"
        return result

    # 3. Membership is active and has not expired
    membership = get_active_membership(member_id)
    result["membership"] = membership
    if membership is None:
        latest = get_latest_membership(member_id)
        if latest is None:
            result["reason"] = "Access Denied – No Membership"
        elif latest["status"] == "pending":
            result["reason"] = "Access Denied – Membership Not Yet Active"
        elif latest["status"] == "suspended":
            result["reason"] = "Access Denied – Membership Suspended"
        elif latest["status"] == "cancelled":
            result["reason"] = "Access Denied – Membership Cancelled"
        else:  # 'expired', or 'active' whose end date has passed
            result["reason"] = "Access Denied – Membership Expired"
        return result

    # 4. Member has not already checked in
    if is_inside(member_id):
        result["reason"] = "Access Denied – Already Checked In"
        return result

    result["ok"] = True
    return result


# ===== Lab 15: check-out =====
def list_open_visits(q=""):
    """Visits that are still open (members currently inside), optionally filtered."""
    sql = """SELECT a.*, m.member_number, m.first_name, m.last_name, p.plan_name
             FROM attendance a
             JOIN members m ON m.member_id = a.member_id
             JOIN memberships ms ON ms.membership_id = a.membership_id
             JOIN membership_plans p ON p.plan_id = ms.plan_id
             WHERE a.check_out_time IS NULL"""
    params = []
    if q:
        like = f"%{q}%"
        sql += """ AND (m.member_number LIKE ? OR m.first_name LIKE ? OR m.last_name LIKE ?
                   OR (m.first_name || ' ' || m.last_name) LIKE ?)"""
        params = [like] * 4
    sql += " ORDER BY a.check_in_time"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def checkout(attendance_id):
    """Record the check-out time and visit duration (in minutes).
    Returns True if saved, False if the visit was missing or already checked out."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT check_in_time, check_out_time FROM attendance WHERE attendance_id = ?",
            (attendance_id,),
        ).fetchone()
        if row is None or row["check_out_time"] is not None:
            return False
        check_in = datetime.strptime(row["check_in_time"], "%Y-%m-%d %H:%M:%S")
        now = max(datetime.now().replace(microsecond=0), check_in)
        minutes = round((now - check_in).total_seconds() / 60)
        conn.execute(
            """UPDATE attendance SET check_out_time = ?, duration_minutes = ?
               WHERE attendance_id = ? AND check_out_time IS NULL""",
            (now.strftime("%Y-%m-%d %H:%M:%S"), minutes, attendance_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ===== Lab 16: attendance history =====
def recent_visitors(limit=20):
    """Members who have attendance records, most recent visitor first."""
    conn = get_db()
    rows = conn.execute(
        """SELECT m.*, MAX(a.check_in_time) AS last_visit, COUNT(*) AS visit_count
           FROM attendance a JOIN members m ON m.member_id = a.member_id
           GROUP BY m.member_id ORDER BY last_visit DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def get_history(member_id, date_from=None, date_to=None):
    """All visits of a member (newest first), optionally between two dates (YYYY-MM-DD)."""
    sql = "SELECT * FROM attendance WHERE member_id = ?"
    params = [member_id]
    if date_from:
        sql += " AND date(check_in_time) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date(check_in_time) <= ?"
        params.append(date_to)
    sql += " ORDER BY check_in_time DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def format_date(d):
    return f"{d:%b} {d.day}, {d.year}"


def format_time(t):
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def format_duration(minutes):
    if minutes is None:
        return "-"
    if minutes < 60:
        return f"{minutes} min" + ("" if minutes == 1 else "s")
    hours = round(minutes / 60, 1)
    text = f"{hours:g}"
    return f"{text} hr" + ("" if hours == 1 else "s")


# ===== Lab 17: attendance monitoring =====
def get_daily_stats(day):
    """Stats for one day (YYYY-MM-DD): distinct members, total visits, average duration."""
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(DISTINCT member_id) AS members, COUNT(*) AS visits,
                  AVG(duration_minutes) AS avg_minutes
           FROM attendance WHERE date(check_in_time) = ?""",
        (day,),
    ).fetchone()
    conn.close()
    return {
        "members": row["members"],
        "visits": row["visits"],
        "avg_minutes": round(row["avg_minutes"]) if row["avg_minutes"] is not None else None,
    }


def get_hourly_counts(day):
    """Check-ins per hour of the day: {hour (0-23): count}."""
    conn = get_db()
    rows = conn.execute(
        """SELECT CAST(substr(check_in_time, 12, 2) AS INTEGER) AS hr, COUNT(*) AS n
           FROM attendance WHERE date(check_in_time) = ? GROUP BY hr""",
        (day,),
    ).fetchall()
    conn.close()
    return {r["hr"]: r["n"] for r in rows}


def hour_label(h):
    return f"{h % 12 or 12}:00 {'AM' if h % 24 < 12 else 'PM'}"