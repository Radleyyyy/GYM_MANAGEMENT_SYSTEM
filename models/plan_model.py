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


def list_plans():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM membership_plans ORDER BY duration_months, price"
    ).fetchall()
    conn.close()
    return rows


def get_plan(plan_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM membership_plans WHERE plan_id = ?", (plan_id,)
    ).fetchone()
    conn.close()
    return row