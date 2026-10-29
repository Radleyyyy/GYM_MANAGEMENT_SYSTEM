from datetime import date, timedelta
from database.db import get_db

AGE_GROUPS = [("Under 18", 0, 17), ("18-24", 18, 24), ("25-34", 25, 34),
              ("35-44", 35, 44), ("45-54", 45, 54), ("55 and above", 55, 200)]


def _age(dob, today):
    born = date.fromisoformat(dob)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def valid_date(text):
    try:
        return date.fromisoformat(text).isoformat()
    except (TypeError, ValueError):
        return None


def member_report(date_from, date_to, today=None):
    """Lab 25. date_from/date_to (ISO strings) filter the 'new members' and
    'registration date' sections. Counts for total/active/inactive/gender/age cover all members."""
    today = today or date.today()
    conn = get_db()
    try:
        members = conn.execute(
            "SELECT member_id, gender, date_of_birth, registration_date, status FROM members"
        ).fetchall()
        by_status = {"active": 0, "inactive": 0, "archived": 0}
        for m in members:
            by_status[m["status"]] += 1

        gender = {"Male": 0, "Female": 0, "Other": 0}
        ages = {label: 0 for label, _, _ in AGE_GROUPS}
        for m in members:
            if m["status"] == "archived":
                continue
            gender[m["gender"]] += 1
            a = _age(m["date_of_birth"], today)
            for label, lo, hi in AGE_GROUPS:
                if lo <= a <= hi:
                    ages[label] += 1
                    break

        new_rows = conn.execute(
            """SELECT member_number, first_name, last_name, registration_date, status
               FROM members WHERE registration_date BETWEEN ? AND ?
               ORDER BY registration_date DESC, member_id DESC""", (date_from, date_to)).fetchall()
        by_month = conn.execute(
            """SELECT substr(registration_date, 1, 7) AS month, COUNT(*) AS total
               FROM members WHERE registration_date BETWEEN ? AND ?
               GROUP BY month ORDER BY month DESC""", (date_from, date_to)).fetchall()
    finally:
        conn.close()

    return {
        "total": len(members),
        "active": by_status["active"],
        "inactive": by_status["inactive"],
        "archived": by_status["archived"],
        "gender": gender,
        "ages": ages,
        "new_members": new_rows,
        "by_month": by_month,
    }


def default_range(today=None):
    today = today or date.today()
    return (today - timedelta(days=30)).isoformat(), today.isoformat()
