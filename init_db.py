import os
import sqlite3
from werkzeug.security import generate_password_hash
from config import DATABASE, BASE_DIR


def init_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(os.path.join(BASE_DIR, "database", "schema.sql"), encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
        ("admin", generate_password_hash("admin123"), "System Administrator", "Administrator"),
    )
    conn.commit()
    return conn


def show(conn, title, sql):
    print(f"\n--- {title} ---")
    for row in conn.execute(sql):
        print(dict(row))


if __name__ == "__main__":
    conn = init_db()
    print("Database created.")
    show(conn, "Member -> Membership -> Plan", """
        SELECT m.member_number, m.first_name, p.plan_name, ms.start_date, ms.end_date, ms.status
        FROM memberships ms
        JOIN members m ON m.member_id = ms.member_id
        JOIN membership_plans p ON p.plan_id = ms.plan_id""")
    show(conn, "Membership -> Payments", """
        SELECT pay.payment_number, m.first_name, pay.amount_due, pay.amount_paid, pay.balance, pay.payment_status
        FROM payments pay JOIN members m ON m.member_id = pay.member_id""")
    show(conn, "Membership -> Attendance", """
        SELECT m.first_name, a.check_in_time, a.check_out_time, a.duration_minutes
        FROM attendance a JOIN members m ON m.member_id = a.member_id""")
    show(conn, "Membership -> Expiration", """
        SELECT ms.membership_id, e.expiration_date, e.expiry_status
        FROM expiration_records e JOIN memberships ms ON ms.membership_id = e.membership_id""")
    conn.close()