from database.db import get_db


def code_exists(code, exclude_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM membership_plans WHERE upper(plan_code) = upper(?) AND plan_id != ?",
        (code, exclude_id or 0),
    ).fetchone()
    conn.close()
    return row is not None


def name_exists(name, exclude_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM membership_plans WHERE lower(plan_name) = lower(?) AND plan_id != ?",
        (name, exclude_id or 0),
    ).fetchone()
    conn.close()
    return row is not None


def create_plan(f):
    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO membership_plans
               (plan_code, plan_name, duration_months, price,
                description, benefits, access_type, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (f["plan_code"], f["plan_name"], int(f["duration_months"]),
             round(float(f["price"]), 2), f["description"], f["benefits"],
             f["access_type"], f["status"]),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_plan(plan_id, f):
    conn = get_db()
    try:
        conn.execute(
            """UPDATE membership_plans
               SET plan_code=?, plan_name=?, duration_months=?, price=?,
                   description=?, benefits=?, access_type=?, status=?
               WHERE plan_id=?""",
            (f["plan_code"], f["plan_name"], int(f["duration_months"]),
             round(float(f["price"]), 2), f["description"], f["benefits"],
             f["access_type"], f["status"], plan_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_plans(search="", status="all", duration=None):
    sql = "SELECT * FROM membership_plans WHERE 1=1"
    params = []
    if status == "all":
        sql += " AND status != 'archived'"
    else:
        sql += " AND status = ?"
        params.append(status)
    if duration:
        sql += " AND duration_months = ?"
        params.append(duration)
    if search:
        like = f"%{search}%"
        sql += """ AND (plan_code LIKE ? OR plan_name LIKE ?
                   OR description LIKE ? OR benefits LIKE ?)"""
        params += [like] * 4
    sql += " ORDER BY duration_months, price"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_durations():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT duration_months FROM membership_plans ORDER BY duration_months"
    ).fetchall()
    conn.close()
    return [r["duration_months"] for r in rows]


def get_plan(plan_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM membership_plans WHERE plan_id = ?", (plan_id,)
    ).fetchone()
    conn.close()
    return row


def set_status(plan_id, status):
    conn = get_db()
    conn.execute("UPDATE membership_plans SET status = ? WHERE plan_id = ?", (status, plan_id))
    conn.commit()
    conn.close()


def count_memberships(plan_id):
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM memberships WHERE plan_id = ?", (plan_id,)
    ).fetchone()["n"]
    conn.close()
    return n


def count_active_memberships(plan_id):
    conn = get_db()
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM memberships
           WHERE plan_id = ? AND status IN ('active','pending','suspended')""",
        (plan_id,),
    ).fetchone()["n"]
    conn.close()
    return n

def list_active_plans():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM membership_plans WHERE status = 'active' ORDER BY duration_months, price"
    ).fetchall()
    conn.close()
    return rows