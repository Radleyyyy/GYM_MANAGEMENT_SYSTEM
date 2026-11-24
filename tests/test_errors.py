"""Lab 38: error handling tests.

Run from the project folder:   python -m unittest tests.test_errors -v
"""
import os
import re
import sqlite3
import sys
import unittest
from datetime import date
from unittest import mock

import tests                                  # noqa: F401  (switches the app to a temporary database)
import config
from app import app                           # noqa: E402
tests.quiet(app)
from database.db import get_db                # noqa: E402
from models import payment_model              # noqa: E402

BAD_WORDS = ("Traceback", "sqlite3", "OperationalError", "IntegrityError", "ZeroDivisionError",
             "The requested URL was not found", "Internal Server Error")


def login(username, password="password123"):
    c = app.test_client()
    c.post("/login", data={"username": username, "password": password})
    return c


def one(sql, *params):
    db = get_db()
    try:
        return db.execute(sql, params).fetchone()
    finally:
        db.close()


def run(sql, *params):
    db = get_db()
    try:
        db.execute(sql, params)
        db.commit()
    finally:
        db.close()


def messages(response):
    return " | ".join(re.findall(r'flash flash-[a-z]+">([^<]*)', response.data.decode()))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = login("admin", "admin123")
        cls.cashier = login("cashier")
        cls.trainer = login("trainer")

    def assertFriendly(self, response, code, title):
        text = response.data.decode()
        self.assertEqual(response.status_code, code)
        self.assertIn(title, text)
        for bad in BAD_WORDS:
            self.assertNotIn(bad, text, f"technical text {bad!r} must not be shown to the user")
        self.assertIn("Go Back", text)


class TestErrorPages(Base):
    def test_404_logged_in_and_out(self):
        self.assertFriendly(self.admin.get("/no/such/page"), 404, "Page Not Found")
        self.assertFriendly(app.test_client().get("/no/such/page"), 404, "Page Not Found")

    def test_405(self):
        self.assertFriendly(self.admin.put("/members/"), 405, "Action Not Allowed")
        self.assertFriendly(self.admin.get("/attendance/check-in/1"), 405, "Action Not Allowed")

    def test_bad_url_value(self):
        self.assertFriendly(self.admin.get("/members/abc"), 404, "Page Not Found")

    def test_unexpected_error_shows_friendly_500_and_is_logged(self):
        with mock.patch("controllers.members.member_model.list_members", side_effect=ZeroDivisionError("boom")):
            r = self.admin.get("/members/")
        self.assertFriendly(r, 500, "Something Went Wrong")
        with open(os.path.join(config.LOG_DIR, "error.log"), encoding="utf-8") as f:
            log = f.read()
        self.assertIn("ZeroDivisionError", log)
        self.assertIn("/members/", log)

    def test_database_errors(self):
        cases = [(sqlite3.OperationalError("database is locked"), 503, "Database Busy"),
                 (sqlite3.IntegrityError("UNIQUE constraint failed: members.email"), 409, "Record Conflict"),
                 (sqlite3.DatabaseError("file is not a database"), 500, "Database Error")]
        for error, code, title in cases:
            with mock.patch("controllers.plans.plan_model.list_plans", side_effect=error):
                self.assertFriendly(self.admin.get("/plans/"), code, title)

    def test_error_page_works_even_if_user_not_logged_in(self):
        with mock.patch("controllers.auth.user_model.get_user", side_effect=sqlite3.OperationalError("locked")):
            c = login("admin", "admin123")
            r = c.get("/members/")
        self.assertIn(r.status_code, (200, 302, 503))
        self.assertNotIn("Traceback", r.data.decode())


class TestMissingRecords(Base):
    URLS = [("GET", "/members/99999"), ("GET", "/members/99999/edit"), ("GET", "/members/success/99999"),
            ("POST", "/members/99999/status"), ("GET", "/plans/99999"), ("GET", "/plans/99999/edit"),
            ("POST", "/plans/99999/status"), ("GET", "/courses/99999/edit"), ("POST", "/memberships/99999/status"),
            ("GET", "/renewals/99999"), ("POST", "/renewals/99999"), ("GET", "/billing/99999"),
            ("GET", "/payments/new/99999"), ("POST", "/payments/new/99999"), ("GET", "/payments/99999"),
            ("GET", "/payments/99999/receipt"), ("POST", "/attendance/check-in/99999"),
            ("POST", "/attendance/check-out/99999")]

    def test_no_server_error_and_clear_message(self):
        for method, url in self.URLS:
            r = self.admin.open(url, method=method, follow_redirects=True)
            self.assertLess(r.status_code, 500, f"{method} {url}")
            text = r.data.decode()
            for bad in BAD_WORDS:
                self.assertNotIn(bad, text, f"{method} {url}")
            self.assertRegex(messages(r).lower(), r"not found|no active|invalid|not exist|unknown",
                             f"{method} {url} should explain that the record is missing")


class TestInvalidInput(Base):
    def test_bad_query_values(self):
        for url in ["/reports/revenue?date_from=abc&date_to=zzz", "/reports/members?status=bogus",
                    "/reports/attendance?date_from=2026-13-99", "/expiration/?filter=bogus",
                    "/notifications/?filter=bogus", "/members/?page=abc", "/members/?page=-5",
                    "/members/?q=%27%20OR%201%3D1--", "/payments/?status=%00"]:
            r = self.admin.get(url)
            self.assertLess(r.status_code, 500, url)

    def test_empty_and_malformed_forms(self):
        for url in ["/members/register", "/plans/new", "/courses/add", "/memberships/register",
                    "/payments/new/1", "/login"]:
            r = self.admin.post(url, data={})
            self.assertLess(r.status_code, 500, url)
        r = self.admin.post("/members/register", data={"first_name": "x" * 50000})
        self.assertLess(r.status_code, 500)

    def test_unicode_and_control_characters(self):
        r = self.admin.post("/members/register", data={"first_name": "Zoë \x00 日本", "last_name": "<script>x</script>",
                                                       "email": "ä@ö.com", "contact_number": "٠٩١٢"})
        self.assertLess(r.status_code, 500)
        self.assertNotIn(b"<script>x</script>", r.data)       # output is escaped


class TestInvalidLogin(Base):
    def attempt(self, username, password):
        return app.test_client().post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_wrong_password_and_unknown_user_look_the_same(self):
        a = messages(self.attempt("admin", "wrong"))
        b = messages(self.attempt("nobody-here", "wrong"))
        self.assertIn("Invalid username or password", a)
        self.assertEqual(a, b)

    def test_missing_fields(self):
        self.assertIn("required", messages(self.attempt("", "")))

    def test_inactive_account(self):
        run("UPDATE users SET status='inactive' WHERE username='trainer'")
        try:
            self.assertIn("inactive", messages(self.attempt("trainer", "password123")))
        finally:
            run("UPDATE users SET status='active' WHERE username='trainer'")

    def test_lockout_message(self):
        for _ in range(5):
            self.attempt("reports", "bad")
        self.assertIn("Too many failed attempts", messages(self.attempt("reports", "password123")))

    def test_session_of_removed_user_is_cleared(self):
        c = login("manager")
        run("UPDATE users SET status='inactive' WHERE username='manager'")
        try:
            r = c.get("/members/")
            self.assertEqual(r.status_code, 302)
            self.assertIn("/login", r.headers["Location"])
        finally:
            run("UPDATE users SET status='active' WHERE username='manager'")


class TestUnauthorizedAccess(Base):
    def test_not_logged_in_is_sent_to_login_with_message(self):
        r = app.test_client().get("/members/", follow_redirects=True)
        self.assertIn("Please log in", messages(r))

    def test_wrong_role_gets_access_denied_page(self):
        r = self.cashier.get("/members/")
        self.assertEqual(r.status_code, 403)
        self.assertIn("Access Denied", r.data.decode())
        self.assertNotIn("Traceback", r.data.decode())

    def test_denied_write_by_read_only_role(self):
        self.assertEqual(self.trainer.post("/members/1/status", data={"status": "inactive"}).status_code, 403)


class TestDuplicateRecords(Base):
    def test_race_between_check_and_insert_is_handled(self):
        data = {"first_name": "Dup", "last_name": "Case", "gender": "Male", "date_of_birth": "1999-01-01",
                "contact_number": "09881110000", "email": "dup.case@example.com", "address": "x",
                "emergency_contact": "y", "course_id": "1"}
        self.assertEqual(self.admin.post("/members/register", data=data).status_code, 302)
        # pretend the duplicate check missed it: the database constraint must still be handled nicely
        with mock.patch("controllers.members.member_model.email_exists", return_value=False), \
             mock.patch("controllers.members.member_model.contact_exists", return_value=False):
            r = self.admin.post("/members/register", data=data)
        self.assertEqual(r.status_code, 200)
        self.assertIn("already exists", messages(r))

    def test_unhandled_integrity_error_becomes_conflict_page(self):
        with mock.patch("controllers.plans.plan_model.create_plan", side_effect=sqlite3.IntegrityError("UNIQUE")):
            r = self.admin.post("/plans/new", data={"plan_code": "ZZ1", "plan_name": "Z", "duration_months": "1",
                                                   "price": "100", "access_type": "Full Access", "status": "active"})
        self.assertIn(r.status_code, (200, 409))
        self.assertNotIn("IntegrityError", r.data.decode())


class TestInvalidPaymentsAndExpired(Base):
    def test_invalid_payment_messages(self):
        r = self.admin.post("/members/register", data={"first_name": "Pay", "last_name": "Err", "gender": "Male",
            "date_of_birth": "1999-01-01", "contact_number": "09882220000", "email": "pay.err@example.com",
            "address": "x", "emergency_contact": "y", "course_id": "1"})
        mid = int(re.search(r"/members/success/(\d+)", r.headers["Location"]).group(1))
        self.admin.post("/memberships/register", data={"member_id": mid, "plan_id": 1, "start_date": date.today().isoformat()})
        msid = one("SELECT membership_id FROM memberships WHERE member_id=?", mid)[0]
        for amount, expect in [("abc", "must be a number"), ("-5", "greater than zero"), ("0", "greater than zero"),
                               ("99999", "Overpayment"), ("", "required")]:
            r = self.cashier.post(f"/payments/new/{msid}", follow_redirects=True, data={
                "discount_type": "amount", "discount": "0", "charges": "0", "method_id": "1", "amount_paid": amount})
            self.assertIn(expect, messages(r), amount)
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0)

    def test_expired_membership_message(self):
        run("UPDATE memberships SET status='expired', end_date='2020-01-01', start_date='2019-12-01' WHERE membership_id=2")
        r = self.admin.post("/attendance/check-in/2", follow_redirects=True)
        self.assertIn("Expired", messages(r))


class TestFailedTransactions(Base):
    def test_payment_is_rolled_back_when_a_step_fails(self):
        r = self.admin.post("/members/register", data={"first_name": "Roll", "last_name": "Back", "gender": "Male",
            "date_of_birth": "1999-01-01", "contact_number": "09883330000", "email": "roll.back@example.com",
            "address": "x", "emergency_contact": "y", "course_id": "1"})
        mid = int(re.search(r"/members/success/(\d+)", r.headers["Location"]).group(1))
        self.admin.post("/memberships/register", data={"member_id": mid, "plan_id": 1, "start_date": date.today().isoformat()})
        msid = one("SELECT membership_id FROM memberships WHERE member_id=?", mid)[0]

        real_get_db = payment_model.get_db

        class FailingConnection:
            """Behaves like the real connection, but the membership update step fails."""
            def __init__(self):
                self._c = real_get_db()

            def execute(self, sql, *args):
                if "UPDATE memberships SET status = 'active'" in sql:
                    raise sqlite3.OperationalError("simulated failure")
                return self._c.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(self._c, name)

        with mock.patch.object(payment_model, "get_db", FailingConnection):
            r = self.cashier.post(f"/payments/new/{msid}", data={"discount_type": "amount", "discount": "0",
                                  "charges": "0", "method_id": "1", "amount_paid": "500"})
        self.assertIn(r.status_code, (200, 302, 503))
        self.assertNotIn("simulated failure", r.data.decode())
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0,
                         "half-finished payment must be rolled back")
        self.assertEqual(one("SELECT status FROM memberships WHERE membership_id=?", msid)[0], "pending")
        # and the system still works afterwards
        r = self.cashier.post(f"/payments/new/{msid}", follow_redirects=True, data={
            "discount_type": "amount", "discount": "0", "charges": "0", "method_id": "1", "amount_paid": "500"})
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 1)

    def test_failed_daily_update_does_not_break_pages(self):
        mod = sys.modules["app"]
        mod._last_run["date"] = None
        with mock.patch("models.expiration_model.update_statuses", side_effect=RuntimeError("daily job broke")):
            r = self.admin.get("/members/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(mod._last_run["date"], "must retry on the next request")


if __name__ == "__main__":
    unittest.main(verbosity=2)
