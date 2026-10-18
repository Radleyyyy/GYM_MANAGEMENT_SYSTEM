from datetime import date, timedelta
from database.db import get_db
from models.membership_model import add_months

RENEWAL_WINDOW_DAYS = 30   # an active membership can be renewed this many days before it ends
MAX_DURATION_MONTHS = 60


def calculate_period(current_end, months, today=None):
    """New period starts the day after the current one ends (or today if already lapsed).
    Example: current end 2026-09-30, 1 month -> 2026-10-01 to 2026-10-31."""
    today = today or date.today()
    start = max(current_end + timedelta(days=1), today)
    end = add_months(start, months) - timedelta(days=1)
    return start, end


def get_context(member_id):
    """Everything the renewal pages need, including whether the member can renew now."""
    conn = get_db()
    member = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    if member is None:
        conn.close()
        return None
    current = conn.execute(
        """SELECT ms.*, p.plan_name, p.plan_code
           FROM memberships ms JOIN membership_plans p ON p.plan_id = ms.plan_id
           WHERE ms.member_id = ? AND ms.status IN ('active','expired','suspended')
           ORDER BY ms.end_date DESC, ms.membership_id DESC LIMIT 1""",
        (member_id,),
    ).fetchone()
    has_pending = conn.execute(
        "SELECT 1 FROM memberships WHERE member_id = ? AND status = 'pending'", (member_id,)
    ).fetchone() is not None
    conn.close()

    ctx = {"member": member, "current": current, "days_left": None,
           "effective_status": None, "eligible": False, "reason": ""}
    if member["status"] != "active":
        ctx["reason"] = "Member is not active."
    elif current is None:
        ctx["reason"] = "No previous membership. Register a membership first."
    elif has_pending:
        ctx["reason"] = "Member already has a pending membership (renewal already saved)."
    else:
        end = date.fromisoformat(current["end_date"])
        days_left = (end - date.today()).days
        status = current["status"]
        if status == "active" and days_left < 0:
            status = "expired"
        ctx["days_left"], ctx["effective_status"] = days_left, status
        if status == "expired":
            ctx["eligible"] = True
        elif status == "suspended":
            ctx["reason"] = "Membership is suspended. Reactivate or cancel it first."
        elif days_left <= RENEWAL_WINDOW_DAYS:
            ctx["eligible"] = True
        else:
            ctx["reason"] = (f"Membership still has {days_left} day(s) left. "
                             f"Renewal opens {RENEWAL_WINDOW_DAYS} days before it ends.")
    return ctx


def search_members(q=""):
    """Active members matching q. With no search text: only members who can renew now."""
    sql = "SELECT member_id FROM members WHERE status = 'active'"
    params = []
    if q:
        like = f"%{q}%"
        sql += """ AND (member_number LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                   OR (first_name || ' ' || last_name) LIKE ?)"""
        params = [like] * 4
    sql += " ORDER BY first_name, last_name LIMIT 100"
    conn = get_db()
    ids = [r["member_id"] for r in conn.execute(sql, params).fetchall()]
    conn.close()
    results = [get_context(i) for i in ids]
    return results if q else [r for r in results if r["eligible"]]


def save_renewal(member_id, plan, start, end):
    """Save the renewal as a new membership (is_renewal = 1) plus its expiration record."""
    status = "active" if start <= date.today() else "pending"
    today = date.today().isoformat()
    conn = get_db()
    try:
        # a lapsed membership must be marked expired first (only one active allowed)
        conn.execute(
            """UPDATE expiration_records SET expiry_status = 'expired', last_checked = CURRENT_TIMESTAMP
               WHERE membership_id IN (SELECT membership_id FROM memberships
                   WHERE member_id = ? AND status = 'active' AND end_date < ?)""",
            (member_id, today),
        )
        conn.execute(
            "UPDATE memberships SET status = 'expired' WHERE member_id = ? AND status = 'active' AND end_date < ?",
            (member_id, today),
        )
        cur = conn.execute(
            """INSERT INTO memberships
               (member_id, plan_id, start_date, end_date, membership_fee, status, is_renewal)
               VALUES (?,?,?,?,?,?,1)""",
            (member_id, plan["plan_id"], start.isoformat(), end.isoformat(), plan["price"], status),
        )
        conn.execute(
            "INSERT INTO expiration_records (membership_id, expiration_date, expiry_status) VALUES (?,?,'active')",
            (cur.lastrowid, end.isoformat()),
        )
        conn.commit()
        return cur.lastrowid, status
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()