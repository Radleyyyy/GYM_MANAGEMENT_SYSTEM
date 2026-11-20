from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from database.db import get_db

MAX_ATTEMPTS = 5
LOCK_MINUTES = 5
_failures = {}  # username -> {"count": int, "locked_until": datetime | None}


def ensure_default_admin():
    # Safety net: make sure at least one account exists so login is possible
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("admin123"), "System Administrator", "Administrator"),
        )
        conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row


def locked_minutes(username):
    info = _failures.get(username)
    if info and info["locked_until"] and info["locked_until"] > datetime.now():
        return int((info["locked_until"] - datetime.now()).total_seconds() // 60) + 1
    return 0


def _record_failure(username):
    info = _failures.setdefault(username, {"count": 0, "locked_until": None})
    if info["locked_until"] and info["locked_until"] <= datetime.now():
        info["count"], info["locked_until"] = 0, None
    info["count"] += 1
    if info["count"] >= MAX_ATTEMPTS:
        info["locked_until"] = datetime.now() + timedelta(minutes=LOCK_MINUTES)


def authenticate(username, password):
    """Return (user_row, error_message). Error is generic to avoid leaking which part was wrong."""
    key = username.lower()
    mins = locked_minutes(key)
    if mins:
        return None, f"Too many failed attempts. Try again in {mins} minute(s)."
    user = get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        _record_failure(key)
        return None, "Invalid username or password."
    if user["status"] != "active":
        return None, "This account is inactive. Contact the administrator."
    _failures.pop(key, None)
    return user, None
