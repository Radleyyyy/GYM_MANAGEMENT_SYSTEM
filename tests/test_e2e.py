"""Lab 41: end-to-end system test - one complete gym transaction, step by step, through the real pages.

Run from the project folder:             python -m unittest tests.test_e2e -v
Make the End-to-End Testing Report:      python -m tests.report e2e
"""
import re
import unittest
from datetime import date, timedelta

import tests                                   # noqa: F401  (switches the app to a temporary database)
from app import app
tests.quiet(app)
from database.db import get_db                 # noqa: E402
from models import attendance_model, dashboard_model, membership_model, report_model   # noqa: E402

TODAY = date.today()


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


class TestCompleteScenario(unittest.TestCase):
    """Complete scenario: one member, from registration to reports"""

    s = {}          # shared between the steps (the steps run in order: 01, 02, 03 ...)

    @classmethod
    def setUpClass(cls):
        cls.reception = login("reception")      # front desk: members, memberships, attendance, renewals
        cls.manager = login("manager")          # manager: plans, expiration
        cls.cashier = login("cashier")          # cashier: billing and payments
        cls.reports = login("reports")          # report officer: reports and dashboard
        start, end = report_model.default_range()
        cls.s = {"range": (start, end),
                 "kpi": dashboard_model.dashboard_data()["kpi"],
                 "members": report_model.member_report(start, end)["total"],
                 "ms": report_model.membership_report("new", start, end)["counts"],
                 "revenue": report_model.revenue_report(start, end),
                 "visits": report_model.attendance_report(start, end)["visits"]}

    def check_in(self):
        return self.reception.post(f"/attendance/check-in/{self.s['member_id']}", follow_redirects=True)

    def status(self, ms_id):
        return one("SELECT status FROM memberships WHERE membership_id=?", ms_id)["status"]

    # ---------- the 13 steps ----------
    def test_01_register_a_member(self):
        """Step 1 - Register a member: the member is saved and gets a member number"""
        self.assertEqual(self.reception.get("/members/register").status_code, 200)
        r = self.reception.post("/members/register", data={
            "first_name": "Juan", "last_name": "Endtoend", "gender": "Male", "date_of_birth": "1998-03-14",
            "contact_number": "09191234567", "email": "juan.e2e@example.com", "address": "12 Rizal St, Bayombong",
            "emergency_contact": "Maria Endtoend 09181234567", "course_id": "1", "status": "active"})
        self.assertEqual(r.status_code, 302, messages(r))
        self.s["member_id"] = int(re.search(r"/members/success/(\d+)", r.headers["Location"]).group(1))
        member = one("SELECT * FROM members WHERE member_id=?", self.s["member_id"])
        self.assertRegex(member["member_number"], r"^GYM-\d{4}$")
        self.assertEqual(member["status"], "active")
        self.assertIn(member["member_number"], self.reception.get(f"/members/success/{self.s['member_id']}").data.decode())

    def test_02_create_a_membership_plan(self):
        """Step 2 - Create a membership plan: a 1-month plan priced at 1,500 is saved and active"""
        r = self.manager.post("/plans/new", data={
            "plan_code": "E2E1", "plan_name": "End-to-End Monthly", "duration_months": "1", "price": "1500",
            "access_type": "Full Access", "description": "Monthly plan for the end-to-end test",
            "benefits": "Gym floor, lockers", "status": "active"})
        self.assertEqual(r.status_code, 302, messages(r))
        plan = one("SELECT * FROM membership_plans WHERE plan_code='E2E1'")
        self.s["plan_id"] = plan["plan_id"]
        self.assertEqual((plan["price"], plan["duration_months"], plan["status"]), (1500, 1, "active"))
        self.assertIn("End-to-End Monthly", self.manager.get("/plans/").data.decode())

    def test_03_assign_the_plan(self):
        """Step 3 - Assign the plan: a pending membership is created with the plan price and the right dates"""
        r = self.reception.post("/memberships/register", data={
            "member_id": self.s["member_id"], "plan_id": self.s["plan_id"], "start_date": TODAY.isoformat()})
        self.assertEqual(r.status_code, 302, messages(r))
        ms = one("SELECT * FROM memberships WHERE member_id=?", self.s["member_id"])
        self.s["ms_id"] = ms["membership_id"]
        self.assertEqual((ms["status"], ms["membership_fee"], ms["start_date"], ms["end_date"]),
                         ("pending", 1500, TODAY.isoformat(), membership_model.add_months(TODAY, 1).isoformat()))
        self.assertIn("Endtoend", self.reception.get("/memberships/").data.decode())

    def test_04_calculate_the_membership_fee(self):
        """Step 4 - Calculate the fee: 1,500 - 10% discount + 100 charges = 1,450.00"""
        page = self.cashier.get(f"/billing/{self.s['ms_id']}?calc=1&discount_type=percent&discount=10&charges=100").data.decode()
        self.assertIn("1,450.00", page)
        self.assertEqual(self.cashier.get("/billing/").status_code, 200)
        self.assertIn("Endtoend", self.cashier.get("/billing/").data.decode())

    def test_05_process_the_payment(self):
        """Step 5 - Process the payment: the payment is saved as paid and a receipt can be opened"""
        r = self.cashier.post(f"/payments/new/{self.s['ms_id']}", follow_redirects=True, data={
            "discount_type": "percent", "discount": "10", "charges": "100", "method_id": "1", "amount_paid": "1450"})
        self.assertIn("Payment recorded", messages(r))
        pay = one("SELECT * FROM payments WHERE membership_id=?", self.s["ms_id"])
        self.s["payment_id"] = pay["payment_id"]
        self.assertEqual((pay["amount_due"], pay["amount_paid"], pay["balance"], pay["payment_status"]), (1450, 1450, 0, "paid"))
        receipt = self.cashier.get(f"/payments/{pay['payment_id']}/receipt")
        self.assertEqual(receipt.status_code, 200)
        self.assertIn(pay["payment_number"], receipt.data.decode())

    def test_06_activate_the_membership(self):
        """Step 6 - Activate the membership: the payment made the membership active"""
        self.assertEqual(self.status(self.s["ms_id"]), "active")
        page = self.reception.get(f"/members/{self.s['member_id']}").data.decode()
        self.assertIn("Access Allowed", page)

    def test_07_check_the_member_in(self):
        """Step 7 - Check the member in: the visit is recorded, and a second check-in is refused"""
        self.check_in()
        visit = one("SELECT * FROM attendance WHERE member_id=?", self.s["member_id"])
        self.s["visit_id"] = visit["attendance_id"]
        self.assertEqual(visit["membership_id"], self.s["ms_id"])
        self.assertIsNone(visit["check_out_time"])
        self.assertIn("Already Checked In", messages(self.check_in()))
        self.assertEqual(one("SELECT COUNT(*) n FROM attendance WHERE member_id=?", self.s["member_id"])["n"], 1)

    def test_08_check_the_member_out(self):
        """Step 8 - Check the member out: the time out and the visit duration are recorded"""
        # pretend the visit started 75 minutes ago so the duration is meaningful
        run("UPDATE attendance SET check_in_time=datetime('now','localtime','-75 minutes') WHERE attendance_id=?", self.s["visit_id"])
        self.assertEqual(self.reception.post(f"/attendance/check-out/{self.s['visit_id']}").status_code, 302)
        visit = one("SELECT * FROM attendance WHERE attendance_id=?", self.s["visit_id"])
        self.assertIsNotNone(visit["check_out_time"])
        self.assertIn(visit["duration_minutes"], (75, 76))
        self.assertEqual(self.reception.get(f"/attendance/summary/{self.s['visit_id']}").status_code, 200)

    def test_09_view_attendance_history(self):
        """Step 9 - View attendance history: the visit appears in the member's history and on the monitor"""
        page = self.reception.get(f"/attendance/history/{self.s['member_id']}").data.decode()
        self.assertIn("Endtoend", page)
        self.assertIn(attendance_model.format_duration(75), page)       # the 75-minute visit from step 8
        self.assertIn(attendance_model.format_date(TODAY), page)
        self.assertEqual(self.reception.get("/attendance/monitor").status_code, 200)

    def test_10_monitor_expiration(self):
        """Step 10 - Monitor expiration: the membership shows as expiring soon, then as expired, and entry is denied"""
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=25)).isoformat(), (TODAY + timedelta(days=5)).isoformat(), self.s["ms_id"]))
        soon = self.manager.get("/expiration/?filter=7days").data.decode()
        self.assertIn("Endtoend", soon)
        self.assertIn("paid", soon)
        # time passes: the membership period ends
        run("UPDATE memberships SET start_date=?, end_date=? WHERE membership_id=?",
            ((TODAY - timedelta(days=40)).isoformat(), (TODAY - timedelta(days=2)).isoformat(), self.s["ms_id"]))
        self.assertIn("Endtoend", self.manager.get("/expiration/?filter=expired").data.decode())
        self.assertIn("Expired", messages(self.check_in()))
        self.assertEqual(one("SELECT COUNT(*) n FROM attendance WHERE member_id=?", self.s["member_id"])["n"], 1)

    def test_11_renew_the_membership(self):
        """Step 11 - Renew the membership: renewal is saved, paid, activated, and the member can enter again"""
        self.assertEqual(self.reception.get(f"/renewals/{self.s['member_id']}").status_code, 200)
        r = self.reception.post(f"/renewals/{self.s['member_id']}", data={"plan_id": str(self.s["plan_id"])}, follow_redirects=True)
        renewal = one("SELECT * FROM memberships WHERE member_id=? AND is_renewal=1", self.s["member_id"])
        self.assertIsNotNone(renewal, messages(r))
        self.s["renewal_id"] = renewal["membership_id"]
        self.assertEqual((renewal["status"], renewal["start_date"]), ("pending", TODAY.isoformat()))
        self.assertEqual(renewal["end_date"], (membership_model.add_months(TODAY, 1) - timedelta(days=1)).isoformat())
        self.assertEqual(self.status(self.s["ms_id"]), "expired")
        self.assertIn("Payment Required", messages(self.check_in()))          # not paid yet: still no entry
        self.cashier.post(f"/payments/new/{renewal['membership_id']}", data={
            "discount_type": "amount", "discount": "0", "charges": "0", "method_id": "2", "amount_paid": "1500"})
        self.assertEqual(self.status(renewal["membership_id"]), "active")
        self.check_in()
        self.assertEqual(one("SELECT COUNT(*) n FROM attendance WHERE member_id=?", self.s["member_id"])["n"], 2)
        self.assertIn(renewal["end_date"], self.reception.get(f"/members/{self.s['member_id']}").data.decode())

    def test_12_generate_reports(self):
        """Step 12 - Generate reports: member, membership, attendance and revenue reports include the transaction"""
        start, end = self.s["range"]
        for url in ("/reports/members", "/reports/memberships", "/reports/attendance", "/reports/revenue"):
            self.assertEqual(self.reports.get(url).status_code, 200, url)
        number = one("SELECT member_number FROM members WHERE member_id=?", self.s["member_id"])["member_number"]
        self.assertIn(number, self.reports.get("/reports/members").data.decode())
        self.assertEqual(report_model.member_report(start, end)["total"], self.s["members"] + 1)
        counts = report_model.membership_report("new", start, end)["counts"]
        self.assertEqual((counts["new"], counts["renewed"]), (self.s["ms"]["new"] + 1, self.s["ms"]["renewed"] + 1))
        self.assertEqual(report_model.attendance_report(start, end)["visits"], self.s["visits"] + 2)
        revenue = report_model.revenue_report(start, end)
        self.assertAlmostEqual(revenue["revenue"] - self.s["revenue"]["revenue"], 2950)
        self.assertEqual(revenue["payment_count"], self.s["revenue"]["payment_count"] + 2)
        self.assertAlmostEqual(revenue["renewal_revenue"] - self.s["revenue"]["renewal_revenue"], 1500)

    def test_13_verify_the_dashboard(self):
        """Step 13 - Verify the dashboard: the figures moved by exactly what this transaction did"""
        before, after = self.s["kpi"], dashboard_model.dashboard_data()["kpi"]
        self.assertEqual(after["total_members"], before["total_members"] + 1)
        self.assertEqual(after["active_memberships"], before["active_memberships"] + 1)
        self.assertEqual(after["attendance_today"], before["attendance_today"] + 2)
        self.assertEqual(after["renewals"], before["renewals"] + 1)
        self.assertAlmostEqual(after["monthly_revenue"] - before["monthly_revenue"], 2950)
        page = self.reports.get("/").data.decode()
        self.assertEqual(page.count('class="flow-label"'), 10)
        self.assertIn("System Workflow", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
