from database.db import get_db


def generate_member_number(conn):
    row = conn.execute(
        "SELECT COALESCE(MAX(member_id), 0) + 1 AS next_id FROM members"
    ).fetchone()
    return f"GYM-{row['next_id']:04d}"


def email_exists(email):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM members WHERE lower(email) = lower(?)", (email,)
    ).fetchone()
    conn.close()
    return row is not None


def contact_exists(contact):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM members WHERE contact_number = ?", (contact,)
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