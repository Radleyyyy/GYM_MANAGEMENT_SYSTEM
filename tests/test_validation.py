"""Lab 37: system-wide validation tests.

Run from the project folder:   python -m unittest tests.test_validation -v
Uses a temporary database, so your real gym.db is never touched.
"""
import os
import re
import sys
import unittest
from datetime import date, timedelta

import tests                              # noqa: F401  (switches the app to a temporary database)
from app import app                      # noqa: E402
tests.quiet(app)
from database.db import get_db           # noqa: E402
from models import expiration_model      # noqa: E402

_n = [0]
TODAY = date.today()


def login(username, password="password123"):
    c = app.test_client()
    c.post("/login", data={"username": username, "password": password})
    return c


def one(sql, *params):
    db = get_db()
    row = db.execute(sql, params).fetchone()
    db.close()
    return row


def run(sql, *params):
    if len(params) == 1 and isinstance(params[0], tuple):
        params = params[0]
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
        cls.reception = login("reception")

    # ---- helpers that build data through the real pages ----
    def new_member_data(self, **over):
        _n[0] += 1
        data = {"first_name": "Val", "last_name": f"Tester{_n[0]}", "gender": "Male",
                "date_of_birth": "1999-01-01", "contact_number": f"0977{_n[0]:07d}",
                "email": f"val{_n[0]}@example.com", "address": "Test St",
                "emergency_contact": "Mom 09170000000", "course_id": "1", "status": "active"}
        data.update(over)
        return data

    def make_member(self):
        r = self.admin.post("/members/register", data=self.new_member_data())
        self.assertEqual(r.status_code, 302, messages(r))
        return int(re.search(r"/members/success/(\d+)", r.headers["Location"]).group(1))

    def make_membership(self, member_id=None, plan_id=1, start=None):
        member_id = member_id or self.make_member()
        r = self.admin.post("/memberships/register", data={
            "member_id": member_id, "plan_id": plan_id, "start_date": (start or TODAY).isoformat()})
        self.assertEqual(r.status_code, 302, messages(r))
        return member_id, one("SELECT membership_id FROM memberships WHERE member_id=? ORDER BY 1 DESC", member_id)[0]

    def pay(self, membership_id, amount, client=None):
        return (client or self.cashier).post(f"/payments/new/{membership_id}", follow_redirects=True, data={
            "discount_type": "amount", "discount": "0", "charges": "0", "method_id": "1",
            "amount_paid": str(amount)})

    def active_member(self, plan_id=1):
        member_id, msid = self.make_membership(plan_id=plan_id)
        self.pay(msid, one("SELECT membership_fee FROM memberships WHERE membership_id=?", msid)[0])
        self.assertEqual(one("SELECT status FROM memberships WHERE membership_id=?", msid)[0], "active")
        return member_id, msid

    def attendance_rows(self, member_id):
        return one("SELECT COUNT(*) FROM attendance WHERE member_id=?", member_id)[0]


class TestDuplicateMembers(Base):
    def test_same_email_rejected(self):
        d = self.new_member_data()
        self.assertEqual(self.admin.post("/members/register", data=d).status_code, 302)
        d2 = self.new_member_data(email=d["email"])
        r = self.admin.post("/members/register", data=d2)
        self.assertEqual(r.status_code, 200)
        self.assertIn("already registered", messages(r))

    def test_same_email_different_case_rejected(self):
        d = self.new_member_data()
        self.admin.post("/members/register", data=d)
        r = self.admin.post("/members/register", data=self.new_member_data(email=d["email"].upper()))
        self.assertEqual(r.status_code, 200, "email duplicate check must ignore letter case")

    def test_same_phone_rejected(self):
        d = self.new_member_data()
        self.admin.post("/members/register", data=d)
        r = self.admin.post("/members/register", data=self.new_member_data(contact_number=d["contact_number"]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("already registered", messages(r))

    def test_email_with_spaces_rejected_as_duplicate(self):
        d = self.new_member_data()
        self.admin.post("/members/register", data=d)
        r = self.admin.post("/members/register", data=self.new_member_data(email="  " + d["email"] + "  "))
        self.assertEqual(r.status_code, 200)

    def test_edit_cannot_take_another_members_email(self):
        a, b = self.make_member(), self.make_member()
        email_a = one("SELECT email FROM members WHERE member_id=?", a)[0]
        d = self.new_member_data(email=email_a)
        r = self.admin.post(f"/members/{b}/edit", data=d)
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(one("SELECT email FROM members WHERE member_id=?", b)[0], email_a)

    def test_required_and_format_checks(self):
        for field, bad in [("first_name", ""), ("email", "not-an-email"), ("contact_number", "abc"),
                           ("date_of_birth", "2999-01-01"), ("date_of_birth", "31-31-2000"),
                           ("gender", "Robot"), ("course_id", "9999")]:
            r = self.admin.post("/members/register", data=self.new_member_data(**{field: bad}))
            self.assertEqual(r.status_code, 200, f"{field}={bad!r} should be rejected")


class TestInvalidPlans(Base):
    def plan(self, **over):
        _n[0] += 1
        d = {"plan_code": f"V{_n[0]}", "plan_name": f"Valid Plan {_n[0]}", "duration_months": "1", "price": "500",
             "access_type": "Full Access", "description": "d", "benefits": "b", "status": "active"}
        d.update(over)
        return self.admin.post("/plans/new", data=d)

    def test_valid_plan_saved(self):
        self.assertEqual(self.plan().status_code, 302)

    def test_bad_plan_fields_rejected(self):
        for over in [{"price": "0"}, {"price": "-10"}, {"price": "abc"}, {"price": ""},
                     {"duration_months": "0"}, {"duration_months": "-1"}, {"duration_months": "abc"},
                     {"duration_months": "1000"}, {"plan_name": ""}, {"plan_code": ""}]:
            r = self.plan(**over)
            self.assertEqual(r.status_code, 200, f"plan {over} should be rejected")

    def test_duplicate_plan_code_rejected(self):
        self.plan(plan_code="DUPX")
        self.assertEqual(self.plan(plan_code="DUPX").status_code, 200)

    def test_membership_with_missing_or_bad_plan_rejected(self):
        m = self.make_member()
        for plan_id in ["", "abc", "99999", "-1", "1; DROP TABLE memberships"]:
            r = self.admin.post("/memberships/register", data={"member_id": m, "plan_id": plan_id,
                                                               "start_date": TODAY.isoformat()})
            self.assertEqual(r.status_code, 200, f"plan_id={plan_id!r} should be rejected")
        self.assertEqual(one("SELECT COUNT(*) FROM memberships WHERE member_id=?", m)[0], 0)

    def test_inactive_plan_rejected(self):
        self.plan(plan_code="INACT1", status="inactive")
        pid = one("SELECT plan_id FROM membership_plans WHERE plan_code='INACT1'")[0]
        m = self.make_member()
        r = self.admin.post("/memberships/register", data={"member_id": m, "plan_id": pid,
                                                           "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)


class TestInvalidMembershipDates(Base):
    def register(self, start):
        m = self.make_member()
        r = self.admin.post("/memberships/register", data={"member_id": m, "plan_id": 1, "start_date": start})
        return m, r

    def test_bad_dates_rejected(self):
        for bad in ["", "abc", "2026-13-01", "2026-02-30", "01/02/2026", "0000-00-00", "9999-12-31", "1900-01-01"]:
            m, r = self.register(bad)
            self.assertEqual(r.status_code, 200, f"start_date={bad!r} should be rejected")
            self.assertEqual(one("SELECT COUNT(*) FROM memberships WHERE member_id=?", m)[0], 0)

    def test_end_date_always_calculated_by_server(self):
        m = self.make_member()
        r = self.admin.post("/memberships/register", data={
            "member_id": m, "plan_id": 1, "start_date": TODAY.isoformat(), "end_date": "2099-01-01"})
        ms = one("SELECT * FROM memberships WHERE member_id=?", m)
        if ms is not None:
            self.assertNotEqual(ms["end_date"], "2099-01-01")

    def test_unknown_or_inactive_member_rejected(self):
        for mid in ["", "abc", "99999"]:
            r = self.admin.post("/memberships/register", data={"member_id": mid, "plan_id": 1,
                                                               "start_date": TODAY.isoformat()})
            self.assertEqual(r.status_code, 200, f"member_id={mid!r} should be rejected")
        m = self.make_member()
        run("UPDATE members SET status='inactive' WHERE member_id=?", m)
        r = self.admin.post("/memberships/register", data={"member_id": m, "plan_id": 1,
                                                           "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)


class TestDuplicateActiveMemberships(Base):
    def test_second_membership_rejected(self):
        m, _ = self.make_membership()
        r = self.admin.post("/memberships/register", data={"member_id": m, "plan_id": 2,
                                                           "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertIn("already has", messages(r))
        self.assertEqual(one("SELECT COUNT(*) FROM memberships WHERE member_id=?", m)[0], 1)

    def test_database_blocks_two_active_memberships(self):
        m, msid = self.active_member()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            run("""INSERT INTO memberships (member_id, plan_id, start_date, end_date, membership_fee, status)
                   VALUES (?,1,?,?,1000,'active')""", m, TODAY.isoformat(), (TODAY + timedelta(days=30)).isoformat())


class TestExpiredMemberships(Base):
    def expire(self, msid):
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=40)).isoformat(), (TODAY - timedelta(days=10)).isoformat(), msid))

    def test_expired_membership_cannot_check_in(self):
        m, msid = self.active_member()
        self.expire(msid)                       # status still says 'active', but the date has passed
        r = self.admin.post(f"/attendance/check-in/{m}", follow_redirects=True)
        self.assertIn("Expired", messages(r))
        self.assertEqual(self.attendance_rows(m), 0)

    def test_status_update_marks_expired(self):
        m, msid = self.active_member()
        self.expire(msid)
        expiration_model.update_statuses()
        self.assertEqual(one("SELECT status FROM memberships WHERE membership_id=?", msid)[0], "expired")

    def test_cannot_reactivate_expired_membership(self):
        m, msid = self.active_member()
        self.expire(msid)
        expiration_model.update_statuses()
        self.admin.post(f"/memberships/{msid}/status", data={"new_status": "active"})
        self.assertEqual(one("SELECT status FROM memberships WHERE membership_id=?", msid)[0], "expired")


class TestUnauthorizedCheckins(Base):
    def test_not_logged_in(self):
        m, _ = self.active_member()
        r = app.test_client().post(f"/attendance/check-in/{m}")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])
        self.assertEqual(self.attendance_rows(m), 0)

    def test_role_without_attendance_access(self):
        m, _ = self.active_member()
        self.assertEqual(self.cashier.post(f"/attendance/check-in/{m}").status_code, 403)
        self.assertEqual(self.attendance_rows(m), 0)

    def test_no_membership_unpaid_suspended_cancelled_inactive(self):
        no_ms = self.make_member()
        unpaid, _ = self.make_membership()
        susp, s_id = self.active_member()
        run("UPDATE memberships SET status='suspended' WHERE membership_id=?", s_id)
        canc, c_id = self.active_member()
        run("UPDATE memberships SET status='cancelled' WHERE membership_id=?", c_id)
        inact, _ = self.active_member()
        run("UPDATE members SET status='inactive' WHERE member_id=?", inact)
        for m in (no_ms, unpaid, susp, canc, inact):
            self.admin.post(f"/attendance/check-in/{m}")
            self.assertEqual(self.attendance_rows(m), 0, f"member {m} must not be checked in")

    def test_unknown_member(self):
        for mid in ("99999", "0", "-5"):
            r = self.admin.post(f"/attendance/check-in/{mid}", follow_redirects=True)
            self.assertIn(r.status_code, (200, 404))
            self.assertNotEqual(r.status_code, 500)

    def test_check_in_requires_post(self):
        m, _ = self.active_member()
        self.assertEqual(self.admin.get(f"/attendance/check-in/{m}").status_code, 405)


class TestDuplicateAttendance(Base):
    def test_double_check_in(self):
        m, _ = self.active_member()
        self.admin.post(f"/attendance/check-in/{m}")
        r = self.admin.post(f"/attendance/check-in/{m}", follow_redirects=True)
        self.assertEqual(self.attendance_rows(m), 1)
        self.assertIn("Already Checked In", messages(r))

    def test_check_out_twice_and_unknown(self):
        m, _ = self.active_member()
        self.admin.post(f"/attendance/check-in/{m}")
        aid = one("SELECT attendance_id FROM attendance WHERE member_id=?", m)[0]
        self.admin.post(f"/attendance/check-out/{aid}")
        first = one("SELECT check_out_time FROM attendance WHERE attendance_id=?", aid)[0]
        self.assertIsNotNone(first)
        self.admin.post(f"/attendance/check-out/{aid}")
        self.assertEqual(one("SELECT check_out_time FROM attendance WHERE attendance_id=?", aid)[0], first)
        self.assertNotEqual(self.admin.post("/attendance/check-out/99999", follow_redirects=True).status_code, 500)

    def test_can_check_in_again_after_check_out(self):
        m, _ = self.active_member()
        self.admin.post(f"/attendance/check-in/{m}")
        aid = one("SELECT attendance_id FROM attendance WHERE member_id=?", m)[0]
        self.admin.post(f"/attendance/check-out/{aid}")
        self.admin.post(f"/attendance/check-in/{m}")
        self.assertEqual(self.attendance_rows(m), 2)


class TestInvalidPaymentAmounts(Base):
    def test_bad_amounts_rejected(self):
        _, msid = self.make_membership()
        for bad in ["", "   ", "abc", "-5", "0", "0.00", "10.999", "1e3", "nan", "inf", "-inf", "1,5", "1,00", "1,0000", "+5", "₱500", "0x10", "١٢٣"]:
            self.pay(msid, bad)
            self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0,
                             f"amount {bad!r} must not be saved")

    def test_thousands_separator_is_accepted(self):
        _, msid = self.make_membership(plan_id=4)
        self.pay(msid, "1,000")
        self.assertEqual(one("SELECT amount_paid FROM payments WHERE membership_id=?", msid)[0], 1000)

    def test_bad_method_rejected(self):
        _, msid = self.make_membership()
        for method in ["", "abc", "99999"]:
            self.cashier.post(f"/payments/new/{msid}", data={"discount_type": "amount", "discount": "0",
                              "charges": "0", "method_id": method, "amount_paid": "100"})
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0)

    def test_bad_discount_and_charges_rejected(self):
        _, msid = self.make_membership()
        for disc, ch, typ in [("-5", "0", "amount"), ("abc", "0", "amount"), ("0", "-1", "amount"),
                              ("150", "0", "percent"), ("99999", "0", "amount"), ("0", "abc", "amount"),
                              ("5", "0", "bogus")]:
            self.cashier.post(f"/payments/new/{msid}", data={"discount_type": typ, "discount": disc,
                              "charges": ch, "method_id": "1", "amount_paid": "100"})
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0)

    def test_unknown_membership_and_cancelled(self):
        self.assertNotEqual(self.cashier.post("/payments/new/99999", data={"method_id": "1", "amount_paid": "1"},
                                              follow_redirects=True).status_code, 500)
        _, msid = self.make_membership()
        run("UPDATE memberships SET status='cancelled' WHERE membership_id=?", msid)
        self.pay(msid, 100)
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0)


class TestOverpayments(Base):
    def test_overpayment_rejected(self):
        _, msid = self.make_membership()
        fee = one("SELECT membership_fee FROM memberships WHERE membership_id=?", msid)[0]
        self.pay(msid, fee + 0.01)
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 0)

    def test_overpaying_the_remaining_balance_rejected(self):
        _, msid = self.make_membership()
        fee = one("SELECT membership_fee FROM memberships WHERE membership_id=?", msid)[0]
        self.pay(msid, 100)
        self.pay(msid, fee - 100 + 1)
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 1)

    def test_partial_then_full_and_then_nothing_more(self):
        _, msid = self.make_membership()
        fee = one("SELECT membership_fee FROM memberships WHERE membership_id=?", msid)[0]
        self.pay(msid, 100)
        self.pay(msid, fee - 100)
        row = one("SELECT payment_status, balance FROM payments WHERE membership_id=? ORDER BY payment_id DESC", msid)
        self.assertEqual((row[0], round(row[1], 2)), ("paid", 0))
        self.pay(msid, 1)
        self.assertEqual(one("SELECT COUNT(*) FROM payments WHERE membership_id=?", msid)[0], 2)


class TestInvalidRenewals(Base):
    def renew(self, member_id, plan_id="1", client=None):
        return (client or self.admin).post(f"/renewals/{member_id}", data={"plan_id": plan_id}, follow_redirects=True)

    def renewal_count(self, member_id):
        return one("SELECT COUNT(*) FROM memberships WHERE member_id=? AND is_renewal=1", member_id)[0]

    def test_no_previous_membership(self):
        m = self.make_member()
        self.renew(m)
        self.assertEqual(self.renewal_count(m), 0)

    def test_too_early(self):
        m, _ = self.active_member(plan_id=4)      # long plan: far from ending
        self.renew(m)
        self.assertEqual(self.renewal_count(m), 0)

    def test_unknown_member(self):
        self.assertNotEqual(self.renew(99999).status_code, 500)

    def test_bad_plan_rejected(self):
        m, msid = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=3)).isoformat(), msid))
        for plan_id in ["", "abc", "99999"]:
            self.renew(m, plan_id)
        self.assertEqual(self.renewal_count(m), 0)

    def test_suspended_and_inactive_member(self):
        m, msid = self.active_member()
        run("UPDATE memberships SET end_date=?, status='suspended' WHERE membership_id=?",
            ((TODAY + timedelta(days=3)).isoformat(), msid))
        self.renew(m)
        self.assertEqual(self.renewal_count(m), 0)
        m2, ms2 = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=3)).isoformat(), ms2))
        run("UPDATE members SET status='inactive' WHERE member_id=?", m2)
        self.renew(m2)
        self.assertEqual(self.renewal_count(m2), 0)

    def test_double_renewal_rejected(self):
        m, msid = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=3)).isoformat(), msid))
        self.renew(m)
        self.renew(m)
        self.assertEqual(self.renewal_count(m), 1)

    def test_role_without_renewal_access(self):
        m, msid = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=3)).isoformat(), msid))
        self.assertEqual(self.renew(m, client=self.cashier).status_code, 403)
        self.assertEqual(self.renewal_count(m), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
