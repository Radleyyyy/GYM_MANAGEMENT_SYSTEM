from database.db import get_db


def list_courses():
    conn = get_db()
    rows = conn.execute(
        """SELECT c.course_id, c.course_name,
                  (SELECT COUNT(*) FROM members m WHERE m.course_id = c.course_id) AS member_count
           FROM courses c ORDER BY c.course_name"""
    ).fetchall()
    conn.close()
    return rows


def get_course(course_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM courses WHERE course_id = ?", (course_id,)
    ).fetchone()
    conn.close()
    return row


def name_exists(name, exclude_id=None):
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM courses WHERE lower(course_name) = lower(?) AND course_id != ?",
        (name, exclude_id or 0),
    ).fetchone()
    conn.close()
    return row is not None


def create_course(name):
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO courses (course_name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_course(course_id, name):
    conn = get_db()
    try:
        conn.execute("UPDATE courses SET course_name = ? WHERE course_id = ?", (name, course_id))
        conn.commit()
    finally:
        conn.close()


def count_members(course_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM members WHERE course_id = ?", (course_id,)
    ).fetchone()
    conn.close()
    return row["n"]


def delete_course(course_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM courses WHERE course_id = ?", (course_id,))
        conn.commit()
    finally:
        conn.close()