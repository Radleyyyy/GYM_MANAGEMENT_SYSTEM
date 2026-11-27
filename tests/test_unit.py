"""Lab 39: unit tests - each test checks one function on its own.

Run from the project folder:   python -m unittest tests.test_unit -v
Make the Unit Testing Report:  python -m tests.report unit
"""
import itertools
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

import tests                                   # noqa: F401  (switches the app to a temporary database)
from app import app                            # noqa: F401  (creates and seeds the temporary database)
tests.quiet(app)
from controllers import members as member_ctl, plans as plan_ctl, memberships as ms_ctl   # noqa: E402
from database.db import get_db                 # noqa: E402
from models import (attendance_model, billing_model, expiration_model, member_model,     # noqa: E402
                    membership_model, payment_model, plan_model, renewal_model, report_model)

_counter = itertools.count(1)
TODAY = date.today()


# ---------- helpers that build test data ----------
def member_form(**over):
    n = next(_counter)
    form = {"first_name": "Una", "last_name": f"Unit{n}", "gender": "Female", "date_of_birth": "1997-04-12",
            "contact_number": f"0966{n:07d}", "email": f"unit{n}@example.com", "address": "Unit St",
            "emergency_contact": "Mom 09170000001", "course_id": "1"}
    form.update(over)
    return form


def plan_form(**over):
    n = next(_counter)
    form = {"plan_code": f"UP{n}", "plan_name": f"Unit Plan {n}", "duration_months": "3", "price": "1500",
            "description": "d", "benefits": "b", "access_type": "Full Access", "status": "active"}
    form.update(over)
    return form


def make_member(**over):
    return member_model.create_member(member_form(**over))


def sql(statement, *params):
    db = get_db()
    try:
        cur = db.execute(statement, params)
        db.commit()
        return cur.lastrowid
    finally:
        db.close()


def row(statement, *params):
    db = get_db()
    try:
        return db.execute(statement, params).fetchone()
    finally:
        db.close()


def add_membership(member_id=None, plan_id=1, start=None, end=None, status="active", fee=1500, renewal=0, created=None):
    """Insert a membership straight into the database (with its expiration record)."""
    member_id = member_id or make_member()
    start = start or TODAY - timedelta(days=5)
    end = end or TODAY + timedelta(days=25)
    ms_id = sql("""INSERT INTO memberships (member_id, plan_id, start_date, end_date, membership_fee, status, is_renewal)
                   VALUES (?,?,?,?,?,?,?)""", member_id, plan_id, start.isoformat(), end.isoformat(), fee, status, renewal)
    sql("INSERT INTO expiration_records (membership_id, expiration_date, expiry_status) VALUES (?,?,'active')",
        ms_id, end.isoformat())
    if created:
        sql("UPDATE memberships SET created_at = ? WHERE membership_id = ?", created, ms_id)
    return member_id, ms_id


def add_payment(member_id, ms_id, day, amount, method_id=1):
    n = next(_counter)
    sql("""INSERT INTO payments (payment_number, member_id, membership_id, method_id, payment_date, plan_price,
               discount, additional_charges, amount_due, amount_paid, balance, payment_status)
           VALUES (?,?,?,?,?,?,0,0,?,?,0,'paid')""", f"UT-{n:05d}", member_id, ms_id, method_id, day, amount,
        amount, amount)


def add_visit(member_id, ms_id, check_in, minutes=None):
    out = (datetime.strptime(check_in, "%Y-%m-%d %H:%M:%S") + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S") \
        if minutes is not None else None
    return sql("""INSERT INTO attendance (member_id, membership_id, check_in_time, check_out_time, duration_minutes)
                  VALUES (?,?,?,?,?)""", member_id, ms_id, check_in, out, minutes)


class TestMemberRegistration(unittest.TestCase):
    """Member registration"""

    def test_valid_form_has_no_errors(self):
        """A complete, correct form passes validation"""
        self.assertEqual(member_ctl.validate(member_form()), [])

    def test_required_fields(self):
        """Each missing required field is reported"""
        for field in ("first_name", "last_name", "gender", "date_of_birth", "contact_number", "email", "course_id"):
            errors = member_ctl.validate(member_form(**{field: ""}))
            self.assertTrue(any("required" in e for e in errors), field)

    def test_invalid_values(self):
        """Bad email, phone, gender, course and birth dates are rejected"""
        cases = [("email", "no-at-sign", "Email format is invalid."),
                 ("contact_number", "abc", "Contact number is invalid."),
                 ("gender", "Robot", "Gender is invalid."),
                 ("course_id", "9999", "valid course"),
                 ("date_of_birth", "2999-01-01", "must be in the past"),
                 ("date_of_birth", "2000-02-30", "invalid")]
        for field, value, expected in cases:
            errors = member_ctl.validate(member_form(**{field: value}))
            self.assertTrue(any(expected in e for e in errors), f"{field}={value}: {errors}")

    def test_duplicate_email_and_phone_detected(self):
        """Duplicate email (any letter case) and phone number are rejected"""
        form = member_form()
        member_model.create_member(form)
        errors = member_ctl.validate(member_form(email=form["email"].upper(), contact_number=form["contact_number"]))
        self.assertTrue(any("email is already registered" in e.lower() for e in errors))
        self.assertTrue(any("contact number is already registered" in e.lower() for e in errors))

    def test_edit_may_keep_own_email(self):
        """A member can keep their own email and phone when editing"""
        form = member_form()
        member_id = member_model.create_member(form)
        self.assertEqual(member_ctl.validate(form, member_id), [])

    def test_member_number_is_generated(self):
        """Member numbers look like GYM-0001 and keep increasing"""
        a = member_model.get_member(make_member())["member_number"]
        b = member_model.get_member(make_member())["member_number"]
        self.assertRegex(a, r"^GYM-\d{4}$")
        self.assertLess(a, b)

    def test_create_member_saves_the_data(self):
        """create_member stores every field and starts the member as active"""
        form = member_form(first_name="Saved")
        saved = member_model.get_member(member_model.create_member(form))
        self.assertEqual((saved["first_name"], saved["email"], saved["status"]), ("Saved", form["email"], "active"))

    def test_update_member(self):
        """update_member changes the stored details"""
        member_id = make_member()
        member_model.update_member(member_id, member_form(first_name="Changed"))
        self.assertEqual(member_model.get_member(member_id)["first_name"], "Changed")

    def test_set_status(self):
        """set_status changes the member status"""
        member_id = make_member()
        member_model.set_status(member_id, "inactive")
        self.assertEqual(member_model.get_member(member_id)["status"], "inactive")

    def test_get_missing_member(self):
        """Looking up a member that does not exist gives None"""
        self.assertIsNone(member_model.get_member(999999))


class TestPlanRegistration(unittest.TestCase):
    """Plan registration"""

    def test_valid_plan_has_no_errors(self):
        """A complete, correct plan form passes validation"""
        self.assertEqual(plan_ctl.validate(plan_form()), [])

    def test_bad_values_rejected(self):
        """Bad code, duration, price, access type and status are rejected"""
        cases = [{"plan_code": "A"}, {"plan_code": "BAD CODE!"}, {"duration_months": "0"}, {"duration_months": "61"},
                 {"duration_months": "x"}, {"price": "0"}, {"price": "-5"}, {"price": "abc"}, {"price": "nan"},
                 {"price": "inf"}, {"price": "2000000"}, {"access_type": "VIP"}, {"status": "weird"},
                 {"plan_name": ""}, {"plan_name": "x" * 51}]
        for over in cases:
            self.assertTrue(plan_ctl.validate(plan_form(**over)), f"{over} should be rejected")

    def test_duplicate_code_and_name_detected(self):
        """A plan code or name that already exists is rejected"""
        form = plan_form()
        plan_model.create_plan(form)
        self.assertTrue(plan_ctl.validate(plan_form(plan_code=form["plan_code"])))
        self.assertTrue(plan_ctl.validate(plan_form(plan_name=form["plan_name"])))

    def test_create_plan_saves_the_data(self):
        """create_plan stores the plan and rounds the price to 2 decimals"""
        plan = plan_model.get_plan(plan_model.create_plan(plan_form(price="99.999", duration_months="6")))
        self.assertEqual((plan["price"], plan["duration_months"]), (100.0, 6))

    def test_update_plan(self):
        """update_plan changes the stored details"""
        plan_id = plan_model.create_plan(plan_form())
        plan_model.update_plan(plan_id, plan_form(plan_name="Renamed Plan", price="2000"))
        self.assertEqual(plan_model.get_plan(plan_id)["plan_name"], "Renamed Plan")

    def test_inactive_plan_not_offered(self):
        """Only active plans are offered for new memberships"""
        plan_id = plan_model.create_plan(plan_form())
        self.assertIn(plan_id, [p["plan_id"] for p in plan_model.list_active_plans()])
        plan_model.set_status(plan_id, "inactive")
        self.assertNotIn(plan_id, [p["plan_id"] for p in plan_model.list_active_plans()])


class TestMembershipCreation(unittest.TestCase):
    """Membership creation"""

    def form(self, member_id=None, plan_id=1, start=None):
        return {"member_id": str(member_id or make_member()), "plan_id": str(plan_id),
                "start_date": (start or TODAY).isoformat()}

    def test_valid_membership_calculates_end_date(self):
        """A valid request gives the plan price period: start + plan months"""
        errors, member, plan, start, end = ms_ctl.validate(self.form(plan_id=2))
        self.assertEqual(errors, [])
        self.assertEqual(end, membership_model.add_months(start, plan["duration_months"]))

    def test_invalid_start_dates(self):
        """Past, too-far-ahead and impossible start dates are rejected"""
        cases = [(TODAY - timedelta(days=1), "past"), (TODAY + timedelta(days=400), "1 year")]
        for start, expected in cases:
            errors = ms_ctl.validate(self.form(start=start))[0]
            self.assertTrue(any(expected in e for e in errors), (start, errors))
        for bad in ("", "abc", "2026-02-30", "9999-12-31"):
            form = self.form()
            form["start_date"] = bad
            self.assertTrue(ms_ctl.validate(form)[0], bad)

    def test_invalid_plan_or_member(self):
        """Unknown, inactive or missing plan/member are rejected"""
        for plan_id in ("", "abc", "99999"):
            form = self.form()
            form["plan_id"] = plan_id
            self.assertTrue(ms_ctl.validate(form)[0], plan_id)
        inactive_plan = plan_model.create_plan(plan_form(status="inactive"))
        self.assertTrue(ms_ctl.validate(self.form(plan_id=inactive_plan))[0])
        inactive_member = make_member()
        member_model.set_status(inactive_member, "inactive")
        self.assertTrue(ms_ctl.validate(self.form(member_id=inactive_member))[0])
        self.assertTrue(ms_ctl.validate({"member_id": "99999", "plan_id": "1", "start_date": TODAY.isoformat()})[0])

    def test_duplicate_open_membership_rejected(self):
        """A member with an active or pending membership cannot get another"""
        member_id, _ = add_membership(status="pending")
        self.assertTrue(membership_model.has_open_membership(member_id))
        errors = ms_ctl.validate(self.form(member_id=member_id))[0]
        self.assertTrue(any("already has" in e for e in errors))

    def test_create_membership_saves_pending_with_plan_price(self):
        """create_membership saves a pending membership with the plan price and an expiration record"""
        plan = plan_model.get_plan(2)
        member_id = make_member()
        end = membership_model.add_months(TODAY, plan["duration_months"])
        ms_id = membership_model.create_membership(member_id, plan, TODAY, end)
        saved = membership_model.get_membership(ms_id)
        self.assertEqual((saved["status"], saved["membership_fee"], saved["end_date"]),
                         ("pending", plan["price"], end.isoformat()))
        self.assertIsNotNone(row("SELECT 1 FROM expiration_records WHERE membership_id=?", ms_id))

    def test_wrong_end_date_refused(self):
        """create_membership refuses an end date that does not match the plan"""
        with self.assertRaises(ValueError):
            membership_model.create_membership(make_member(), plan_model.get_plan(1), TODAY, TODAY + timedelta(days=3))

    def test_status_change_rules(self):
        """Only allowed status changes are accepted"""
        _, pending = add_membership(status="pending")
        self.assertTrue(membership_model.change_status(pending, "active")[0])
        self.assertTrue(membership_model.change_status(pending, "suspended")[0])
        self.assertFalse(membership_model.change_status(pending, "pending")[0])
        _, expired = add_membership(status="expired", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=30))
        self.assertFalse(membership_model.change_status(expired, "active")[0])
        self.assertFalse(membership_model.change_status(999999, "active")[0])

    def test_registrable_members_exclude_open_memberships(self):
        """Members who already have an open membership are not offered"""
        member_id, _ = add_membership(status="active")
        self.assertNotIn(member_id, [m["member_id"] for m in membership_model.list_registrable_members()])


class TestExpirationCalculation(unittest.TestCase):
    """Expiration calculation"""

    def test_add_months(self):
        """add_months handles month ends, leap years and year changes"""
        cases = [(date(2026, 1, 31), 1, date(2026, 2, 28)), (date(2028, 1, 31), 1, date(2028, 2, 29)),
                 (date(2028, 2, 29), 12, date(2029, 2, 28)), (date(2026, 12, 15), 1, date(2027, 1, 15)),
                 (date(2026, 11, 30), 3, date(2027, 2, 28)), (date(2026, 5, 31), 1, date(2026, 6, 30)),
                 (date(2026, 1, 15), 12, date(2027, 1, 15)), (date(2026, 1, 1), 60, date(2031, 1, 1))]
        for start, months, expected in cases:
            self.assertEqual(membership_model.add_months(start, months), expected, (start, months))

    def test_filter_conditions(self):
        """Each expiration filter builds the right date condition"""
        sql_text, params = expiration_model._condition("7days", TODAY)
        self.assertEqual(params, [TODAY.isoformat(), (TODAY + timedelta(days=7)).isoformat()])
        self.assertEqual(expiration_model._condition("today", TODAY)[1], [TODAY.isoformat()])
        self.assertEqual(expiration_model._condition("expired", TODAY)[1], [TODAY.isoformat()])
        self.assertEqual(expiration_model._condition("unknown", TODAY), ("", []))

    def test_filters_pick_the_right_memberships(self):
        """today / 7 days / 30 days / expired filters select by end date"""
        _, ends_today = add_membership(end=TODAY)
        _, in_five = add_membership(end=TODAY + timedelta(days=5))
        _, in_twenty = add_membership(end=TODAY + timedelta(days=20))
        _, lapsed = add_membership(start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))

        def ids(key):
            return {r["membership_id"] for r in expiration_model.list_memberships(key, TODAY)}
        self.assertIn(ends_today, ids("today"))
        self.assertNotIn(in_five, ids("today"))
        self.assertTrue({ends_today, in_five} <= ids("7days"))
        self.assertNotIn(in_twenty, ids("7days"))
        self.assertTrue({ends_today, in_five, in_twenty} <= ids("30days"))
        self.assertIn(lapsed, ids("expired"))
        self.assertNotIn(lapsed, ids("active"))

    def test_counts_cover_every_filter(self):
        """counts returns one number for each filter"""
        counts = expiration_model.counts(TODAY)
        self.assertEqual(set(counts), set(expiration_model.FILTERS))
        self.assertTrue(all(isinstance(v, int) for v in counts.values()))

    def test_total_outstanding(self):
        """total_outstanding adds up the balances that are not fully paid"""
        rows = [{"balance": 100, "payment_status": "partial"}, {"balance": 50, "payment_status": "unpaid"},
                {"balance": 0, "payment_status": "paid"}]
        self.assertEqual(expiration_model.total_outstanding(rows), 150)

    def test_status_update_marks_expired_and_activates_paid(self):
        """The daily update expires lapsed memberships and activates paid pending ones"""
        saved = tests.snapshot()
        try:
            _, lapsed = add_membership(start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))
            member_id, soon = add_membership(status="pending", start=TODAY + timedelta(days=2),
                                             end=TODAY + timedelta(days=32))
            payment_model.record_payment(soon, 1, "100")            # paid, but its start date is still ahead
            _, unpaid = add_membership(status="pending", start=TODAY + timedelta(days=2),
                                       end=TODAY + timedelta(days=32))
            expiration_model.update_statuses(TODAY)
            status = lambda i: row("SELECT status FROM memberships WHERE membership_id=?", i)["status"]
            self.assertEqual((status(lapsed), status(soon), status(unpaid)), ("expired", "pending", "pending"))
            expiration_model.update_statuses(TODAY + timedelta(days=2))
            self.assertEqual((status(soon), status(unpaid)), ("active", "pending"))
        finally:
            tests.restore(saved)


class TestAttendanceRecording(unittest.TestCase):
    """Attendance recording"""

    def active_member(self):
        return add_membership(status="active")

    def test_check_in_creates_an_open_visit(self):
        """create_checkin saves an open visit and the member counts as inside"""
        member_id, ms_id = self.active_member()
        visit_id = attendance_model.create_checkin(member_id, ms_id)
        self.assertTrue(attendance_model.is_inside(member_id))
        self.assertIsNone(attendance_model.get_visit(visit_id)["check_out_time"])

    def test_check_out_records_time_and_duration(self):
        """checkout saves the time out and the length of the visit"""
        member_id, ms_id = self.active_member()
        visit_id = add_visit(member_id, ms_id, (datetime.now() - timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S"))
        self.assertTrue(attendance_model.checkout(visit_id))
        visit = attendance_model.get_visit(visit_id)
        self.assertIsNotNone(visit["check_out_time"])
        self.assertIn(visit["duration_minutes"], (90, 91))
        self.assertFalse(attendance_model.is_inside(member_id))

    def test_check_out_twice_or_unknown(self):
        """A visit can only be checked out once; unknown visits are refused"""
        member_id, ms_id = self.active_member()
        visit_id = attendance_model.create_checkin(member_id, ms_id)
        self.assertTrue(attendance_model.checkout(visit_id))
        self.assertFalse(attendance_model.checkout(visit_id))
        self.assertFalse(attendance_model.checkout(999999))

    def test_access_rules(self):
        """validate_checkin allows only active, paid, unexpired, not-inside members"""
        member_id, _ = self.active_member()
        self.assertTrue(attendance_model.validate_checkin(member_id)["ok"])

        def denied(member_id, text):
            result = attendance_model.validate_checkin(member_id)
            self.assertFalse(result["ok"])
            self.assertIn(text, result["reason"])

        denied(999999, "Member Not Found")
        denied(make_member(), "No Membership")
        denied(add_membership(status="pending")[0], "Payment Required")
        denied(add_membership(status="suspended")[0], "Suspended")
        denied(add_membership(status="cancelled")[0], "Cancelled")
        denied(add_membership(status="expired", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))[0], "Expired")
        denied(add_membership(status="active", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))[0], "Expired")
        inactive, _ = self.active_member()
        member_model.set_status(inactive, "inactive")
        denied(inactive, "Inactive")
        inside, ms_id = self.active_member()
        attendance_model.create_checkin(inside, ms_id)
        denied(inside, "Already Checked In")

    def test_history_filters_by_date(self):
        """get_history returns a member's visits, newest first, within the dates asked"""
        member_id, ms_id = self.active_member()
        add_visit(member_id, ms_id, "2001-01-10 09:00:00", 30)
        add_visit(member_id, ms_id, "2001-02-10 09:00:00", 30)
        add_visit(member_id, ms_id, "2001-03-10 09:00:00", 30)
        self.assertEqual(len(attendance_model.get_history(member_id)), 3)
        self.assertEqual(attendance_model.get_history(member_id)[0]["check_in_time"][:7], "2001-03")
        self.assertEqual(len(attendance_model.get_history(member_id, "2001-02-01", "2001-02-28")), 1)

    def test_formatting(self):
        """Dates, times and durations are shown in a friendly format"""
        self.assertEqual(attendance_model.format_date(date(2026, 3, 5)), "Mar 5, 2026")
        for hour, minute, text in [(0, 5, "12:05 AM"), (9, 30, "9:30 AM"), (12, 0, "12:00 PM"), (13, 45, "1:45 PM")]:
            self.assertEqual(attendance_model.format_time(datetime(2026, 1, 1, hour, minute)), text)
        for minutes, text in [(None, "-"), (1, "1 min"), (45, "45 mins"), (60, "1 hr"), (90, "1.5 hrs"), (120, "2 hrs")]:
            self.assertEqual(attendance_model.format_duration(minutes), text)

    def test_daily_statistics(self):
        """get_daily_stats counts visits, members and the average duration of a day"""
        (a, ma), (b, mb) = self.active_member(), self.active_member()
        add_visit(a, ma, "2001-05-05 08:00:00", 30)
        add_visit(b, mb, "2001-05-05 10:00:00", 60)
        self.assertEqual(attendance_model.get_daily_stats("2001-05-05"), {"members": 2, "visits": 2, "avg_minutes": 45})
        self.assertEqual(attendance_model.get_daily_stats("2001-05-06")["visits"], 0)


class TestPaymentCalculation(unittest.TestCase):
    """Payment calculation"""

    def test_bill_total(self):
        """Total = plan price - discount + additional charges"""
        bill = billing_model.calculate_bill(1000, "amount", "100", "50")
        self.assertEqual((bill["discount"], bill["charges"], bill["total"]), (Decimal("100.00"), Decimal("50.00"), Decimal("950.00")))

    def test_percent_discount_and_rounding(self):
        """A percent discount is worked out and rounded to centavos"""
        self.assertEqual(billing_model.calculate_bill(1000, "percent", "10", "")["total"], Decimal("900.00"))
        self.assertEqual(billing_model.calculate_bill("999.99", "percent", "15", "0")["discount"], Decimal("150.00"))
        self.assertEqual(billing_model.calculate_bill(1000, "amount", "", "")["total"], Decimal("1000.00"))
        self.assertEqual(billing_model.calculate_bill(1000, "amount", "1,000", "")["total"], Decimal("0.00"))

    def test_bad_bill_inputs(self):
        """Impossible discounts and bad numbers are refused"""
        for args in [(1000, "amount", "1001", ""), (1000, "percent", "101", ""), (1000, "bogus", "5", ""),
                     (1000, "amount", "-5", ""), (1000, "amount", "abc", ""), (1000, "amount", "1e3", ""),
                     (1000, "amount", "0", "-1"), (1000, "amount", "0", "9999999")]:
            with self.assertRaises(ValueError, msg=str(args)):
                billing_model.calculate_bill(*args)

    def test_payment_amount_checks(self):
        """validate_payment returns the balance and the payment status"""
        self.assertEqual(payment_model.validate_payment(Decimal("1000.00"), "400"),
                         (Decimal("400.00"), Decimal("600.00"), "partial"))
        self.assertEqual(payment_model.validate_payment(Decimal("1000.00"), "1,000.00")[2], "paid")
        for bad in ("", "abc", "0", "-1", "1000.01", "10.999", "1e3", "nan"):
            with self.assertRaises(ValueError, msg=bad):
                payment_model.validate_payment(Decimal("1000.00"), bad)

    def test_partial_then_full_payment(self):
        """Payments reduce the balance until the membership is paid"""
        member_id, ms_id = add_membership(status="pending", start=TODAY, end=TODAY + timedelta(days=30), fee=1500)
        first = payment_model.get_payment(payment_model.record_payment(ms_id, 1, "500", received_by=1))
        self.assertEqual((first["payment_status"], first["balance"], first["received_by"]), ("partial", 1000, 1))
        self.assertRegex(first["payment_number"], r"^PAY-\d{4,}$")
        second = payment_model.get_payment(payment_model.record_payment(ms_id, 1, "1000"))
        self.assertEqual((second["payment_status"], second["balance"]), ("paid", 0))
        self.assertEqual(payment_model.payment_summary(ms_id), ("paid", 0))
        with self.assertRaises(ValueError):
            payment_model.record_payment(ms_id, 1, "1")

    def test_first_payment_applies_discount(self):
        """The first payment uses the discounted bill as the amount due"""
        _, ms_id = add_membership(status="pending", start=TODAY, end=TODAY + timedelta(days=30), fee=1000)
        pay = payment_model.get_payment(payment_model.record_payment(ms_id, 1, "900", "percent", "10", "0"))
        self.assertEqual((pay["amount_due"], pay["balance"], pay["payment_status"]), (900, 0, "paid"))

    def test_payment_refused_cases(self):
        """Overpayment, bad method, cancelled and unknown memberships are refused"""
        _, ms_id = add_membership(status="pending", start=TODAY, end=TODAY + timedelta(days=30), fee=1000)
        for args in [(ms_id, 1, "1000.01"), (ms_id, 99999, "100"), (ms_id, "abc", "100"), (999999, 1, "100")]:
            with self.assertRaises(ValueError, msg=str(args)):
                payment_model.record_payment(*args)
        _, cancelled = add_membership(status="cancelled", fee=1000)
        with self.assertRaises(ValueError):
            payment_model.record_payment(cancelled, 1, "100")
        self.assertEqual(row("SELECT COUNT(*) n FROM payments WHERE membership_id=?", ms_id)["n"], 0)

    def test_summary_before_any_payment(self):
        """An unpaid membership shows 'unpaid' and the full fee as the balance"""
        _, ms_id = add_membership(status="pending", fee=1234)
        self.assertEqual(payment_model.payment_summary(ms_id), ("unpaid", 1234))
        self.assertIsNone(payment_model.get_pay_context(999999))

    def test_payment_activates_pending_membership(self):
        """The first payment turns a pending membership active"""
        _, ms_id = add_membership(status="pending", start=TODAY, end=TODAY + timedelta(days=30), fee=1000)
        payment_model.record_payment(ms_id, 1, "1")
        self.assertEqual(row("SELECT status FROM memberships WHERE membership_id=?", ms_id)["status"], "active")


class TestRenewalProcessing(unittest.TestCase):
    """Renewal processing"""

    def test_period_after_current_membership(self):
        """A renewal starts the day after the current membership ends"""
        self.assertEqual(renewal_model.calculate_period(date(2026, 9, 30), 1, today=date(2026, 9, 1)),
                         (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(renewal_model.calculate_period(date(2026, 1, 30), 1, today=date(2026, 1, 2)),
                         (date(2026, 1, 31), date(2026, 2, 27)))

    def test_period_for_lapsed_membership(self):
        """A lapsed membership renews from today"""
        self.assertEqual(renewal_model.calculate_period(date(2026, 1, 31), 1, today=date(2026, 3, 10)),
                         (date(2026, 3, 10), date(2026, 4, 9)))
        self.assertEqual(renewal_model.calculate_period(date(2026, 1, 31), 12, today=date(2026, 3, 10)),
                         (date(2026, 3, 10), date(2027, 3, 9)))

    def test_eligibility_rules(self):
        """get_context says who may renew and why not"""
        self.assertIsNone(renewal_model.get_context(999999))
        ctx = renewal_model.get_context(make_member())
        self.assertFalse(ctx["eligible"])
        self.assertIn("No previous membership", ctx["reason"])
        far, _ = add_membership(end=TODAY + timedelta(days=90))
        self.assertFalse(renewal_model.get_context(far)["eligible"])
        self.assertIn("day(s) left", renewal_model.get_context(far)["reason"])
        near, _ = add_membership(end=TODAY + timedelta(days=10))
        self.assertTrue(renewal_model.get_context(near)["eligible"])
        lapsed, _ = add_membership(status="expired", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))
        self.assertTrue(renewal_model.get_context(lapsed)["eligible"])
        suspended, _ = add_membership(status="suspended", end=TODAY + timedelta(days=5))
        self.assertFalse(renewal_model.get_context(suspended)["eligible"])
        inactive, _ = add_membership(end=TODAY + timedelta(days=5))
        member_model.set_status(inactive, "inactive")
        self.assertFalse(renewal_model.get_context(inactive)["eligible"])
        waiting, _ = add_membership(status="expired", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))
        add_membership(waiting, status="pending", start=TODAY, end=TODAY + timedelta(days=30))
        self.assertIn("pending", renewal_model.get_context(waiting)["reason"])

    def test_save_renewal(self):
        """save_renewal stores a pending renewal with its expiration record"""
        member_id, old = add_membership(end=TODAY + timedelta(days=5))
        plan = plan_model.get_plan(1)
        start, end = renewal_model.calculate_period(TODAY + timedelta(days=5), plan["duration_months"])
        new_id, status = renewal_model.save_renewal(member_id, plan, start, end)
        saved = membership_model.get_membership(new_id)
        self.assertEqual((status, saved["is_renewal"], saved["start_date"], saved["end_date"], saved["membership_fee"]),
                         ("pending", 1, start.isoformat(), end.isoformat(), plan["price"]))
        self.assertEqual(row("SELECT expiration_date FROM expiration_records WHERE membership_id=?", new_id)[0], end.isoformat())
        self.assertEqual(row("SELECT status FROM memberships WHERE membership_id=?", old)["status"], "active")

    def test_save_renewal_expires_lapsed_membership(self):
        """Renewing a lapsed membership marks the old one expired"""
        member_id, old = add_membership(status="active", start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=3))
        plan = plan_model.get_plan(1)
        start, end = renewal_model.calculate_period(TODAY - timedelta(days=3), plan["duration_months"])
        renewal_model.save_renewal(member_id, plan, start, end)
        self.assertEqual(row("SELECT status FROM memberships WHERE membership_id=?", old)["status"], "expired")


class TestReportGeneration(unittest.TestCase):
    """Report generation"""

    def test_helpers(self):
        """Report helpers: default range, date check and age"""
        self.assertEqual(report_model.default_range(date(2026, 3, 31)), ("2026-03-01", "2026-03-31"))
        self.assertEqual(report_model.valid_date("2026-02-28"), "2026-02-28")
        for bad in ("2026-02-30", "abc", "", None):
            self.assertIsNone(report_model.valid_date(bad))
        self.assertEqual(report_model._age("2000-06-15", date(2026, 6, 14)), 25)
        self.assertEqual(report_model._age("2000-06-15", date(2026, 6, 15)), 26)

    def test_member_report(self):
        """The member report counts members by status, gender, age and registration date"""
        a = make_member(gender="Male", date_of_birth="2000-01-01")
        b = make_member(gender="Female", date_of_birth="1980-01-01")
        sql("UPDATE members SET registration_date='2001-03-10' WHERE member_id=?", a)
        sql("UPDATE members SET registration_date='2001-03-20' WHERE member_id=?", b)
        report = report_model.member_report("2001-03-01", "2001-03-31")
        self.assertEqual(len(report["new_members"]), 2)
        self.assertEqual([(r["month"], r["total"]) for r in report["by_month"]], [("2001-03", 2)])
        self.assertEqual(report["total"], report["active"] + report["inactive"] + report["archived"])
        not_archived = report["total"] - report["archived"]
        self.assertEqual(sum(report["gender"].values()), not_archived)
        self.assertEqual(sum(report["ages"].values()), not_archived)
        empty = report_model.member_report("1990-01-01", "1990-01-31")
        self.assertEqual((len(empty["new_members"]), empty["total"]), (0, report["total"]))

    def test_membership_report(self):
        """The membership report separates new memberships from renewals"""
        a, _ = add_membership(created="2001-04-10 10:00:00")
        b, _ = add_membership(created="2001-04-12 10:00:00")
        c, _ = add_membership(created="2001-04-15 10:00:00", renewal=1)
        report = report_model.membership_report("new", "2001-04-01", "2001-04-30")
        self.assertEqual((report["counts"]["new"], report["counts"]["renewed"]), (2, 1))
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(len(report_model.membership_report("renewed", "2001-04-01", "2001-04-30")["rows"]), 1)
        self.assertEqual(set(report["counts"]), set(report_model.MEMBERSHIP_VIEWS))
        self.assertTrue(report["by_plan"])

    def test_attendance_report(self):
        """The attendance report totals visits, members, durations and peak hours"""
        (a, ma), (b, mb) = add_membership(), add_membership()
        add_visit(a, ma, "2001-08-05 08:10:00", 30)
        add_visit(b, mb, "2001-08-05 08:40:00", 60)
        add_visit(a, ma, "2001-08-06 17:00:00", 90)
        report = report_model.attendance_report("2001-08-01", "2001-08-31")
        self.assertEqual((report["visits"], report["members"], report["avg_minutes"]), (3, 2, 60))
        self.assertAlmostEqual(report["avg_per_day"], 3 / 31)
        self.assertEqual(report["avg_per_member"], 1.5)
        self.assertEqual(report["by_member"][0]["visits"], 2)
        self.assertEqual([r["hour"] for r in report["peak_hours"] if r["is_peak"]], ["08:00 - 08:59"])
        self.assertEqual(report_model.attendance_report("1990-01-01", "1990-01-31")["visits"], 0)

    def test_revenue_report(self):
        """The revenue report adds up payments by date, method and renewals"""
        a, ms_a = add_membership()
        b, ms_b = add_membership(renewal=1)
        add_payment(a, ms_a, "2001-06-10", 500, method_id=1)
        add_payment(a, ms_a, "2001-06-20", 300, method_id=2)
        add_payment(b, ms_b, "2001-06-25", 200, method_id=1)
        add_payment(a, ms_a, "2001-07-01", 999, method_id=1)           # outside the range
        report = report_model.revenue_report("2001-06-01", "2001-06-30")
        self.assertEqual((report["revenue"], report["payment_count"], report["renewal_revenue"]), (1000, 3, 200))
        self.assertEqual({r["method_name"]: r["revenue"] for r in report["by_method"]}.get("Cash"), 700)
        self.assertEqual([(r["month"], r["revenue"]) for r in report["monthly"]], [("2001-06", 1000)])
        self.assertEqual(set(report["counts"]), {"paid", "partial", "unpaid"})
        self.assertEqual(report_model.revenue_report("1990-01-01", "1990-01-31")["revenue"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
