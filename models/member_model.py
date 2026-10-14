from database.db import get_db


def generate_member_number(conn):
    row = conn.execute(
        "SELECT COALESCE(MAX(member_id), 0) + 1 AS next_id FROM members"
    ).fetchone()
    return f"GYM-{row['next_id']:04d}"


def email_exists(email, exclude_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM members WHERE lower(email) = lower(?) AND member_id != ?",
        (email, exclude_id or 0),
    ).fetchone()
    conn.close()
    return row is not None


def contact_exists(contact, exclude_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM members WHERE contact_number = ? AND member_id != ?",
        (contact, exclude_id or 0),
    ).fetchone()
    conn.close()
    return row is not None


def create_member(f):
    conn = get_db()
    try:
        number = generate_member_number(conn)
        cur = conn.execute(
            """INSERT INTO members
               (member_number, first_name, last_name, gender, date_of_birth,
                contact_number, email, address, emergency_contact)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (number, f["first_name"], f["last_name"], f["gender"],
             f["date_of_birth"], f["contact_number"], f["email"],
             f["address"], f["emergency_contact"]),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_member(member_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM members WHERE member_id = ?", (member_id,)
    ).fetchone()
    conn.close()
    return row


def list_members(search="", status="all"):
    sql = "SELECT * FROM members WHERE 1=1"
    params = []
    if status == "all":
        sql += " AND status != 'archived'"
    else:
        sql += " AND status = ?"
        params.append(status)
    if search:
        like = f"%{search}%"
        sql += """ AND (member_number LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                   OR (first_name || ' ' || last_name) LIKE ?
                   OR email LIKE ? OR contact_number LIKE ?)"""
        params += [like] * 6
    sql += " ORDER BY member_id DESC"
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def update_member(member_id, f):
    conn = get_db()
    try:
        conn.execute(
            """UPDATE members SET first_name=?, last_name=?, gender=?,
               date_of_birth=?, contact_number=?, email=?, address=?,
               emergency_contact=? WHERE member_id=?""",
            (f["first_name"], f["last_name"], f["gender"], f["date_of_birth"],
             f["contact_number"], f["email"], f["address"],
             f["emergency_contact"], member_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_status(member_id, status):
    conn = get_db()
    conn.execute("UPDATE members SET status = ? WHERE member_id = ?", (status, member_id))
    conn.commit()
    conn.close()


def has_active_membership(member_id):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM memberships WHERE member_id = ? AND status = 'active'",
        (member_id,),
    ).fetchone()
    conn.close()
    return row is not None