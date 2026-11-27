"""Lab 40: integration tests - each class checks that two modules work correctly together.

Run from the project folder:        python -m unittest tests.test_integration -v
Make the Integration Testing Report: python -m tests.report integration
"""
import itertools
import re
import unittest
from datetime import date, timedelta

import tests                                   # noqa: F401  (switches the app to a temporary database)
from app import app
tests.quiet(app)
from database.db import get_db                 # noqa: E402
from models import (dashboard_model, expiration_model, membership_model, payment_model,   # noqa: E402
                    report_model)

TODAY = date.today()
_n = itertools.count(1)


def login(username, password="password123"):
    client = app.test_client()
    client.post("/login", data={"username": username, "password": password})
    return client


def one(sql, *params):
    db = get_db()
    try:
        return db.execute(sql, params).fetchone()
    finally:
        db.close()


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
        cls.manager = login("manager")
        cls.reception = login("reception")
        cls.cashier = login("cashier")
        cls.reports = login("reports")

    # ----- everything below uses the real pages, like a person would -----
    def register_member(self, **over):
        n = next(_n)
        data = {"first_name": "Ivy", "last_name": f"Integ{n}", "gender": "Female", "date_of_birth": "1996-08-08",
                "contact_number": f"0955{n:07d}", "email": f"integ{n}@example.com", "address": "Test St",
                "emergency_contact": "Mom 09170000002", "course_id": "1", "status": "active"}
        data.update(over)
        r = self.reception.post("/members/register", data=data)
        self.assertEqual(r.status_code, 302, messages(r))
        return int(re.search(r"/members/success/(\d+)", r.headers["Location"]).group(1))

    def create_plan(self, months=2, price="1200", **over):
        n = next(_n)
        data = {"plan_code": f"IT{n}", "plan_name": f"Integration Plan {n}", "duration_months": str(months),
                "price": price, "access_type": "Full Access", "description": "d", "benefits": "b", "status": "active"}
        data.update(over)
        r = self.manager.post("/plans/new", data=data)
        self.assertEqual(r.status_code, 302, messages(r))
        return one("SELECT plan_id FROM membership_plans WHERE plan_code=?", data["plan_code"])["plan_id"]

    def subscribe(self, member_id=None, plan_id=1, start=None):
        member_id = member_id or self.register_member()
        r = self.reception.post("/memberships/register", data={
            "member_id": member_id, "plan_id": plan_id, "start_date": (start or TODAY).isoformat()})
        self.assertEqual(r.status_code, 302, messages(r))
        ms = one("SELECT * FROM memberships WHERE member_id=? ORDER BY membership_id DESC", member_id)
        return member_id, ms["membership_id"]

    def pay(self, ms_id, amount, **extra):
        data = {"discount_type": "amount", "discount": "0", "charges": "0", "method_id": "1", "amount_paid": str(amount)}
        data.update(extra)
        return self.cashier.post(f"/payments/new/{ms_id}", data=data, follow_redirects=True)

    def active_member(self, plan_id=1):
        member_id, ms_id = self.subscribe(plan_id=plan_id)
        self.pay(ms_id, one("SELECT membership_fee FROM memberships WHERE membership_id=?", ms_id)[0])
        return member_id, ms_id

    def status(self, ms_id):
        return one("SELECT status FROM memberships WHERE membership_id=?", ms_id)["status"]

    def check_in(self, member_id):
        return self.reception.post(f"/attendance/check-in/{member_id}", follow_redirects=True)

    def visits(self, member_id):
        return one("SELECT COUNT(*) n FROM attendance WHERE member_id=?", member_id)["n"]


class TestMemberToMembership(Base):
    """Member → Membership"""

    def test_new_member_can_subscribe(self):
        """Expected: a registered member can subscribe, and the membership is linked to that member"""
        member_id = self.register_member()
        form = self.reception.get(f"/memberships/register?member_id={member_id}").data.decode()
        self.assertIn(f'<option value="{member_id}" >', form)
        _, ms_id = self.subscribe(member_id)
        self.assertEqual(one("SELECT member_id FROM memberships WHERE membership_id=?", ms_id)["member_id"], member_id)

    def test_member_pages_lead_to_subscription(self):
        """Expected: the member's success page and profile both link to Register Membership"""
        member_id = self.register_member()
        self.assertIn(f"/memberships/register?member_id={member_id}", self.reception.get(f"/members/success/{member_id}").data.decode())
        self.assertIn(f"/memberships/register?member_id={member_id}", self.reception.get(f"/members/{member_id}").data.decode())

    def test_membership_shows_on_member_profile(self):
        """Expected: after subscribing, the profile shows the plan and period"""
        member_id, ms_id = self.subscribe(plan_id=2)
        ms = one("SELECT * FROM memberships WHERE membership_id=?", ms_id)
        page = self.reception.get(f"/members/{member_id}").data.decode()
        self.assertIn(ms["start_date"], page)
        self.assertIn(ms["end_date"], page)

    def test_member_cannot_subscribe_twice(self):
        """Expected: a member with an open membership is not offered another one"""
        member_id, _ = self.subscribe()
        r = self.reception.post("/memberships/register", data={"member_id": member_id, "plan_id": 1, "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertIn("already has", messages(r))
        self.assertNotIn(f'<option value="{member_id}" >', self.reception.get("/memberships/register").data.decode())

    def test_inactive_member_cannot_subscribe(self):
        """Expected: an inactive member is refused"""
        member_id = self.register_member()
        self.admin.post(f"/members/{member_id}/status", data={"status": "inactive"})
        r = self.reception.post("/memberships/register", data={"member_id": member_id, "plan_id": 1, "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(one("SELECT COUNT(*) n FROM memberships WHERE member_id=?", member_id)["n"], 0)


class TestPlanToMembership(Base):
    """Plan → Membership"""

    def test_price_and_duration_come_from_the_plan(self):
        """Expected: the membership fee equals the plan price and the end date follows the plan duration"""
        plan_id = self.create_plan(months=2, price="1234.50")
        _, ms_id = self.subscribe(plan_id=plan_id, start=TODAY)
        ms = one("SELECT * FROM memberships WHERE membership_id=?", ms_id)
        self.assertEqual(ms["membership_fee"], 1234.5)
        self.assertEqual(ms["end_date"], membership_model.add_months(TODAY, 2).isoformat())
        self.assertEqual(ms["plan_id"], plan_id)

    def test_form_offers_plan_price_and_duration(self):
        """Expected: the membership form carries each plan's duration and price for the live preview"""
        plan_id = self.create_plan(months=3, price="999")
        page = self.reception.get(f"/memberships/register?plan_id={plan_id}").data.decode()
        self.assertIn(f'<option value="{plan_id}" data-months="3"', page)
        self.assertIn("999", page)

    def test_later_price_change_does_not_change_existing_membership(self):
        """Expected: an existing membership keeps the price it was sold at"""
        plan_id = self.create_plan(price="1000")
        _, ms_id = self.subscribe(plan_id=plan_id)
        self.manager.post(f"/plans/{plan_id}/edit", data={
            "plan_code": one("SELECT plan_code FROM membership_plans WHERE plan_id=?", plan_id)["plan_code"],
            "plan_name": "Renamed Integration Plan", "duration_months": "2", "price": "5000",
            "access_type": "Full Access", "description": "d", "benefits": "b", "status": "active"})
        self.assertEqual(one("SELECT price FROM membership_plans WHERE plan_id=?", plan_id)["price"], 5000)
        self.assertEqual(one("SELECT membership_fee FROM memberships WHERE membership_id=?", ms_id)["membership_fee"], 1000)

    def test_inactive_plan_is_not_offered(self):
        """Expected: an inactive plan cannot be used for a new membership"""
        plan_id = self.create_plan(status="inactive")
        self.assertNotIn(f'<option value="{plan_id}" data-months', self.reception.get("/memberships/register").data.decode())
        member_id = self.register_member()
        r = self.reception.post("/memberships/register", data={"member_id": member_id, "plan_id": plan_id, "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 200)

    def test_plan_page_lists_its_members(self):
        """Expected: the plan page lists the members subscribed to it"""
        plan_id = self.create_plan()
        member_id, _ = self.subscribe(plan_id=plan_id)
        name = one("SELECT last_name FROM members WHERE member_id=?", member_id)["last_name"]
        self.assertIn(name, self.manager.get(f"/plans/{plan_id}").data.decode())


class TestMembershipToAttendance(Base):
    """Membership → Attendance"""

    def test_active_member_can_check_in(self):
        """Expected: a member with an active, paid membership can check in; the visit is linked to the membership"""
        member_id, ms_id = self.active_member()
        self.check_in(member_id)
        self.assertEqual(one("SELECT membership_id FROM attendance WHERE member_id=?", member_id)["membership_id"], ms_id)

    def test_only_active_memberships_get_in(self):
        """Expected: pending (unpaid), suspended, cancelled and missing memberships are all denied"""
        unpaid, _ = self.subscribe()
        suspended, s_id = self.active_member()
        self.reception.post(f"/memberships/{s_id}/status", data={"new_status": "suspended"})
        cancelled, c_id = self.active_member()
        self.reception.post(f"/memberships/{c_id}/status", data={"new_status": "cancelled"})
        nothing = self.register_member()
        for member_id in (unpaid, suspended, cancelled, nothing):
            self.check_in(member_id)
            self.assertEqual(self.visits(member_id), 0, f"member {member_id} must be denied")

    def test_status_change_takes_effect_immediately(self):
        """Expected: suspending blocks the next check-in and re-activating allows it again"""
        member_id, ms_id = self.active_member()
        self.reception.post(f"/memberships/{ms_id}/status", data={"new_status": "suspended"})
        self.assertIn("Suspended", messages(self.check_in(member_id)))
        self.reception.post(f"/memberships/{ms_id}/status", data={"new_status": "active"})
        self.check_in(member_id)
        self.assertEqual(self.visits(member_id), 1)

    def test_visit_shows_in_history(self):
        """Expected: the check-in shows on the member profile attendance history"""
        member_id, _ = self.active_member()
        self.check_in(member_id)
        visit = one("SELECT check_in_time FROM attendance WHERE member_id=?", member_id)["check_in_time"]
        self.assertIn(visit[:10], self.reception.get(f"/members/{member_id}").data.decode())

    def test_profile_shows_access_status(self):
        """Expected: the profile shows Access Allowed with a Check In button, or the reason for denial"""
        allowed, _ = self.active_member()
        denied, _ = self.subscribe()
        self.assertIn("Access Allowed", self.reception.get(f"/members/{allowed}").data.decode())
        page = self.reception.get(f"/members/{denied}").data.decode()
        self.assertIn("Payment Required", page)
        self.assertNotIn(f"/attendance/check-in/{denied}", page)


class TestMembershipToPayment(Base):
    """Membership → Payment"""

    def test_billing_uses_the_membership_fee(self):
        """Expected: the bill is the membership fee - discount + charges (1200 - 10% + 50 = 1,130.00)"""
        plan_id = self.create_plan(price="1200")
        _, ms_id = self.subscribe(plan_id=plan_id)
        page = self.cashier.get(f"/billing/{ms_id}?calc=1&discount_type=percent&discount=10&charges=50").data.decode()
        self.assertIn("1,130.00", page)

    def test_payment_records_the_correct_amount_due(self):
        """Expected: the saved payment carries the plan price, discount, charges and amount due"""
        plan_id = self.create_plan(price="1200")
        member_id, ms_id = self.subscribe(plan_id=plan_id)
        self.pay(ms_id, "1130", discount_type="percent", discount="10", charges="50")
        pay = one("SELECT * FROM payments WHERE membership_id=?", ms_id)
        self.assertEqual((pay["plan_price"], pay["discount"], pay["additional_charges"], pay["amount_due"], pay["balance"]),
                         (1200, 120, 50, 1130, 0))
        self.assertEqual((pay["member_id"], pay["payment_status"]), (member_id, "paid"))

    def test_unpaid_membership_appears_for_billing(self):
        """Expected: a new membership shows up on the cashier's billing list"""
        member_id, _ = self.subscribe()
        name = one("SELECT last_name FROM members WHERE member_id=?", member_id)["last_name"]
        self.assertIn(name, self.cashier.get("/billing/").data.decode())

    def test_amount_checks(self):
        """Expected: overpayment, zero and text amounts are refused and nothing is saved"""
        _, ms_id = self.subscribe(plan_id=self.create_plan(price="500"))
        for amount in ("501", "0", "abc", "-5"):
            self.pay(ms_id, amount)
        self.assertEqual(one("SELECT COUNT(*) n FROM payments WHERE membership_id=?", ms_id)["n"], 0)

    def test_cancelled_membership_cannot_be_paid(self):
        """Expected: a cancelled membership cannot receive payments"""
        _, ms_id = self.subscribe()
        self.reception.post(f"/memberships/{ms_id}/status", data={"new_status": "cancelled"})
        self.assertIn("cancelled", messages(self.pay(ms_id, 100)).lower())


class TestPaymentToMembership(Base):
    """Payment → Membership"""

    def test_first_payment_activates_the_membership(self):
        """Expected: a partial payment makes the membership active and the payment status partial"""
        _, ms_id = self.subscribe(plan_id=self.create_plan(price="1000"))
        self.assertEqual(self.status(ms_id), "pending")
        self.pay(ms_id, 400)
        self.assertEqual(self.status(ms_id), "active")
        pay = one("SELECT * FROM payments WHERE membership_id=?", ms_id)
        self.assertEqual((pay["payment_status"], pay["balance"]), ("partial", 600))

    def test_final_payment_marks_it_paid(self):
        """Expected: paying the balance changes the status to paid"""
        _, ms_id = self.subscribe(plan_id=self.create_plan(price="1000"))
        self.pay(ms_id, 400)
        self.pay(ms_id, 600)
        self.assertEqual(payment_model.payment_summary(ms_id), ("paid", 0))

    def test_payment_status_shows_in_the_system(self):
        """Expected: the membership list and the member profile show the payment status and balance"""
        member_id, ms_id = self.subscribe(plan_id=self.create_plan(price="1000"))
        self.pay(ms_id, 400)
        for page in (self.reception.get("/memberships/").data.decode(), self.reception.get(f"/members/{member_id}").data.decode()):
            self.assertIn("partial", page)
            self.assertIn("600.00", page)

    def test_future_start_stays_pending_until_start_date(self):
        """Expected: a paid membership starting later stays pending, then becomes active on its start date"""
        saved = tests.snapshot()
        try:
            _, ms_id = self.subscribe(plan_id=self.create_plan(price="1000"), start=TODAY + timedelta(days=3))
            self.pay(ms_id, 1000)
            self.assertEqual(self.status(ms_id), "pending")
            expiration_model.update_statuses(TODAY + timedelta(days=3))
            self.assertEqual(self.status(ms_id), "active")
        finally:
            tests.restore(saved)

    def test_refused_payment_does_not_change_the_membership(self):
        """Expected: a rejected payment leaves the membership pending"""
        _, ms_id = self.subscribe(plan_id=self.create_plan(price="500"))
        self.pay(ms_id, 9999)
        self.assertEqual(self.status(ms_id), "pending")


class TestExpirationToAttendance(Base):
    """Expiration → Attendance"""

    def expire(self, ms_id, days_ago=1):
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=40)).isoformat(), (TODAY - timedelta(days=days_ago)).isoformat(), ms_id))

    def test_expired_member_is_denied(self):
        """Expected: a membership whose end date has passed is denied, even before the daily update runs"""
        member_id, ms_id = self.active_member()
        self.expire(ms_id)
        self.assertEqual(self.status(ms_id), "active")
        self.assertIn("Expired", messages(self.check_in(member_id)))
        self.assertEqual(self.visits(member_id), 0)

    def test_daily_update_marks_expired_and_still_denies(self):
        """Expected: the daily update changes the status to expired and the member stays denied"""
        member_id, ms_id = self.active_member()
        self.expire(ms_id)
        expiration_model.update_statuses()
        self.assertEqual(self.status(ms_id), "expired")
        self.check_in(member_id)
        self.assertEqual(self.visits(member_id), 0)

    def test_last_day_is_still_allowed(self):
        """Expected: a membership ending today still lets the member in"""
        member_id, ms_id = self.active_member()
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=10)).isoformat(), TODAY.isoformat(), ms_id))
        self.check_in(member_id)
        self.assertEqual(self.visits(member_id), 1)

    def test_expiration_monitor_lists_the_expired_member(self):
        """Expected: the expiration monitor shows the expired member with the access result"""
        member_id, ms_id = self.active_member()
        self.expire(ms_id)
        name = one("SELECT last_name FROM members WHERE member_id=?", member_id)["last_name"]
        self.assertIn(name, self.manager.get("/expiration/?filter=expired").data.decode())

    def test_profile_shows_denied(self):
        """Expected: the member profile shows access denied for an expired membership"""
        member_id, ms_id = self.active_member()
        self.expire(ms_id)
        self.assertIn("Expired", self.reception.get(f"/members/{member_id}").data.decode())


class TestRenewalToExpiration(Base):
    """Renewal → Expiration"""

    def test_lapsed_membership_renewal_gets_new_dates(self):
        """Expected: renewing a lapsed membership starts today and ends after the plan duration"""
        plan_id = self.create_plan(months=2, price="800")
        member_id, ms_id = self.active_member(plan_id=plan_id)
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=70)).isoformat(), (TODAY - timedelta(days=5)).isoformat(), ms_id))
        r = self.reception.post(f"/renewals/{member_id}", data={"plan_id": str(plan_id)}, follow_redirects=True)
        new = one("SELECT * FROM memberships WHERE member_id=? AND is_renewal=1", member_id)
        self.assertIsNotNone(new, messages(r))
        self.assertEqual(new["start_date"], TODAY.isoformat())
        self.assertEqual(new["end_date"], (membership_model.add_months(TODAY, 2) - timedelta(days=1)).isoformat())
        record = one("SELECT * FROM expiration_records WHERE membership_id=?", new["membership_id"])
        self.assertEqual(record["expiration_date"], new["end_date"])
        self.assertEqual(self.status(ms_id), "expired")

    def test_early_renewal_follows_the_current_period(self):
        """Expected: renewing early starts the day after the current end date; the old one keeps working until then"""
        member_id, ms_id = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=4)).isoformat(), ms_id))
        self.reception.post(f"/renewals/{member_id}", data={"plan_id": "1"})
        new = one("SELECT * FROM memberships WHERE member_id=? AND is_renewal=1", member_id)
        self.assertEqual(new["start_date"], (TODAY + timedelta(days=5)).isoformat())
        self.check_in(member_id)
        self.assertEqual(self.visits(member_id), 1)

    def test_paid_renewal_takes_over_on_the_start_date(self):
        """Expected: when the old membership ends, the paid renewal becomes active with the new expiration date"""
        saved = tests.snapshot()
        try:
            member_id, ms_id = self.active_member()
            run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=2)).isoformat(), ms_id))
            self.reception.post(f"/renewals/{member_id}", data={"plan_id": "1"})
            new = one("SELECT * FROM memberships WHERE member_id=? AND is_renewal=1", member_id)
            self.pay(new["membership_id"], 100)
            self.assertEqual(self.status(new["membership_id"]), "pending")
            expiration_model.update_statuses(TODAY + timedelta(days=3))
            self.assertEqual((self.status(ms_id), self.status(new["membership_id"])), ("expired", "active"))
            self.assertIn(new["end_date"], self.reception.get(f"/members/{member_id}").data.decode())
        finally:
            tests.restore(saved)

    def test_unpaid_renewal_stays_pending(self):
        """Expected: a renewal that is not paid does not grant access"""
        member_id, ms_id = self.active_member()
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=40)).isoformat(), (TODAY - timedelta(days=2)).isoformat(), ms_id))
        self.reception.post(f"/renewals/{member_id}", data={"plan_id": "1"})
        self.assertIn("Payment Required", messages(self.check_in(member_id)))
        self.assertEqual(self.visits(member_id), 0)

    def test_renewal_is_not_allowed_too_early(self):
        """Expected: a membership with many days left cannot be renewed yet"""
        member_id, _ = self.active_member(plan_id=self.create_plan(months=12, price="5000"))
        self.reception.post(f"/renewals/{member_id}", data={"plan_id": "1"})
        self.assertEqual(one("SELECT COUNT(*) n FROM memberships WHERE member_id=? AND is_renewal=1", member_id)["n"], 0)


class TestTransactionsToReports(Base):
    """Transactions → Reports"""

    def kpi(self):
        return dashboard_model.dashboard_data()["kpi"]

    def test_new_member_appears_in_reports_and_dashboard(self):
        """Expected: the member report and dashboard count a newly registered member"""
        before_report, before_kpi = report_model.member_report(*report_model.default_range())["total"], self.kpi()["total_members"]
        member_id = self.register_member()
        self.assertEqual(report_model.member_report(*report_model.default_range())["total"], before_report + 1)
        self.assertEqual(self.kpi()["total_members"], before_kpi + 1)
        number = one("SELECT member_number FROM members WHERE member_id=?", member_id)["member_number"]
        self.assertIn(number, self.reports.get("/reports/members").data.decode())

    def test_new_membership_appears_in_the_membership_report(self):
        """Expected: the membership report counts a new membership and its renewal separately"""
        start, end = report_model.default_range()
        before = report_model.membership_report("new", start, end)["counts"]
        self.subscribe()
        after = report_model.membership_report("new", start, end)["counts"]
        self.assertEqual((after["new"], after["renewed"]), (before["new"] + 1, before["renewed"]))

    def test_payment_appears_in_revenue_and_dashboard(self):
        """Expected: a payment raises revenue, payment count and monthly revenue; the unpaid balance drops by the amount paid"""
        start, end = report_model.default_range()
        before, kpi_before = report_model.revenue_report(start, end), self.kpi()
        _, ms_id = self.subscribe(plan_id=self.create_plan(price="1000"))
        unpaid = report_model.revenue_report(start, end)
        self.assertAlmostEqual(float(unpaid["outstanding"]) - float(before["outstanding"]), 1000)
        self.pay(ms_id, 400)
        after, kpi_after = report_model.revenue_report(start, end), self.kpi()
        self.assertAlmostEqual(after["revenue"] - before["revenue"], 400)
        self.assertEqual(after["payment_count"], before["payment_count"] + 1)
        self.assertAlmostEqual(float(after["outstanding"]) - float(before["outstanding"]), 600)
        self.assertAlmostEqual(kpi_after["monthly_revenue"] - kpi_before["monthly_revenue"], 400)
        self.assertEqual(self.reports.get("/reports/revenue").status_code, 200)

    def test_check_in_appears_in_attendance_reports(self):
        """Expected: a check-in raises the attendance report visits and the dashboard check-ins today"""
        start, end = report_model.default_range()
        before, kpi_before = report_model.attendance_report(start, end)["visits"], self.kpi()["attendance_today"]
        member_id, _ = self.active_member()
        self.check_in(member_id)
        self.assertEqual(report_model.attendance_report(start, end)["visits"], before + 1)
        self.assertEqual(self.kpi()["attendance_today"], kpi_before + 1)

    def test_status_changes_appear_in_reports(self):
        """Expected: activating raises and cancelling lowers the active memberships count"""
        before = self.kpi()["active_memberships"]
        _, ms_id = self.active_member()
        self.assertEqual(self.kpi()["active_memberships"], before + 1)
        self.reception.post(f"/memberships/{ms_id}/status", data={"new_status": "cancelled"})
        self.assertEqual(self.kpi()["active_memberships"], before)

    def test_renewal_appears_in_reports(self):
        """Expected: a renewal raises the renewed count and the dashboard renewals figure"""
        start, end = report_model.default_range()
        member_id, ms_id = self.active_member()
        run("UPDATE memberships SET end_date=? WHERE membership_id=?", ((TODAY + timedelta(days=3)).isoformat(), ms_id))
        before, kpi_before = report_model.membership_report("renewed", start, end)["counts"]["renewed"], self.kpi()["renewals"]
        self.reception.post(f"/renewals/{member_id}", data={"plan_id": "1"})
        self.assertEqual(report_model.membership_report("renewed", start, end)["counts"]["renewed"], before + 1)
        self.assertEqual(self.kpi()["renewals"], kpi_before + 1)

    def test_every_report_page_opens_for_the_report_officer(self):
        """Expected: all report pages and the dashboard load with current data"""
        for url in ("/", "/reports/", "/reports/members", "/reports/memberships", "/reports/attendance", "/reports/revenue"):
            self.assertEqual(self.reports.get(url).status_code, 200, url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
