# Gym Management System - Integration Testing Report

- **Date:** November 27, 2026 10:48 AM
- **Environment:** Python 3.13.18 on Linux, SQLite (temporary test database)
- **Scope:** Each test checks that two modules work correctly together.

## Summary

| Total tests | Passed | Failed | Errors | Pass rate | Time |
|---|---|---|---|---|---|
| 42 | 42 | 0 | 0 | 100% | 4.9 s |

## Results by area

| Area | Tests | Passed | Result |
|---|---|---|---|
| Member → Membership | 5 | 5 | PASS |
| Plan → Membership | 5 | 5 | PASS |
| Membership → Attendance | 5 | 5 | PASS |
| Membership → Payment | 5 | 5 | PASS |
| Payment → Membership | 5 | 5 | PASS |
| Expiration → Attendance | 5 | 5 | PASS |
| Renewal → Expiration | 5 | 5 | PASS |
| Transactions → Reports | 7 | 7 | PASS |

## Member → Membership

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_inactive_member_cannot_subscribe` | Expected: an inactive member is refused | PASS |
| 2 | `test_member_cannot_subscribe_twice` | Expected: a member with an open membership is not offered another one | PASS |
| 3 | `test_member_pages_lead_to_subscription` | Expected: the member's success page and profile both link to Register Membership | PASS |
| 4 | `test_membership_shows_on_member_profile` | Expected: after subscribing, the profile shows the plan and period | PASS |
| 5 | `test_new_member_can_subscribe` | Expected: a registered member can subscribe, and the membership is linked to that member | PASS |

## Plan → Membership

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_form_offers_plan_price_and_duration` | Expected: the membership form carries each plan's duration and price for the live preview | PASS |
| 2 | `test_inactive_plan_is_not_offered` | Expected: an inactive plan cannot be used for a new membership | PASS |
| 3 | `test_later_price_change_does_not_change_existing_membership` | Expected: an existing membership keeps the price it was sold at | PASS |
| 4 | `test_plan_page_lists_its_members` | Expected: the plan page lists the members subscribed to it | PASS |
| 5 | `test_price_and_duration_come_from_the_plan` | Expected: the membership fee equals the plan price and the end date follows the plan duration | PASS |

## Membership → Attendance

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_active_member_can_check_in` | Expected: a member with an active, paid membership can check in; the visit is linked to the membership | PASS |
| 2 | `test_only_active_memberships_get_in` | Expected: pending (unpaid), suspended, cancelled and missing memberships are all denied | PASS |
| 3 | `test_profile_shows_access_status` | Expected: the profile shows Access Allowed with a Check In button, or the reason for denial | PASS |
| 4 | `test_status_change_takes_effect_immediately` | Expected: suspending blocks the next check-in and re-activating allows it again | PASS |
| 5 | `test_visit_shows_in_history` | Expected: the check-in shows on the member profile attendance history | PASS |

## Membership → Payment

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_amount_checks` | Expected: overpayment, zero and text amounts are refused and nothing is saved | PASS |
| 2 | `test_billing_uses_the_membership_fee` | Expected: the bill is the membership fee - discount + charges (1200 - 10% + 50 = 1,130.00) | PASS |
| 3 | `test_cancelled_membership_cannot_be_paid` | Expected: a cancelled membership cannot receive payments | PASS |
| 4 | `test_payment_records_the_correct_amount_due` | Expected: the saved payment carries the plan price, discount, charges and amount due | PASS |
| 5 | `test_unpaid_membership_appears_for_billing` | Expected: a new membership shows up on the cashier's billing list | PASS |

## Payment → Membership

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_final_payment_marks_it_paid` | Expected: paying the balance changes the status to paid | PASS |
| 2 | `test_first_payment_activates_the_membership` | Expected: a partial payment makes the membership active and the payment status partial | PASS |
| 3 | `test_future_start_stays_pending_until_start_date` | Expected: a paid membership starting later stays pending, then becomes active on its start date | PASS |
| 4 | `test_payment_status_shows_in_the_system` | Expected: the membership list and the member profile show the payment status and balance | PASS |
| 5 | `test_refused_payment_does_not_change_the_membership` | Expected: a rejected payment leaves the membership pending | PASS |

## Expiration → Attendance

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_daily_update_marks_expired_and_still_denies` | Expected: the daily update changes the status to expired and the member stays denied | PASS |
| 2 | `test_expiration_monitor_lists_the_expired_member` | Expected: the expiration monitor shows the expired member with the access result | PASS |
| 3 | `test_expired_member_is_denied` | Expected: a membership whose end date has passed is denied, even before the daily update runs | PASS |
| 4 | `test_last_day_is_still_allowed` | Expected: a membership ending today still lets the member in | PASS |
| 5 | `test_profile_shows_denied` | Expected: the member profile shows access denied for an expired membership | PASS |

## Renewal → Expiration

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_early_renewal_follows_the_current_period` | Expected: renewing early starts the day after the current end date; the old one keeps working until then | PASS |
| 2 | `test_lapsed_membership_renewal_gets_new_dates` | Expected: renewing a lapsed membership starts today and ends after the plan duration | PASS |
| 3 | `test_paid_renewal_takes_over_on_the_start_date` | Expected: when the old membership ends, the paid renewal becomes active with the new expiration date | PASS |
| 4 | `test_renewal_is_not_allowed_too_early` | Expected: a membership with many days left cannot be renewed yet | PASS |
| 5 | `test_unpaid_renewal_stays_pending` | Expected: a renewal that is not paid does not grant access | PASS |

## Transactions → Reports

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_check_in_appears_in_attendance_reports` | Expected: a check-in raises the attendance report visits and the dashboard check-ins today | PASS |
| 2 | `test_every_report_page_opens_for_the_report_officer` | Expected: all report pages and the dashboard load with current data | PASS |
| 3 | `test_new_member_appears_in_reports_and_dashboard` | Expected: the member report and dashboard count a newly registered member | PASS |
| 4 | `test_new_membership_appears_in_the_membership_report` | Expected: the membership report counts a new membership and its renewal separately | PASS |
| 5 | `test_payment_appears_in_revenue_and_dashboard` | Expected: a payment raises revenue, payment count and monthly revenue; the unpaid balance drops by the amount paid | PASS |
| 6 | `test_renewal_appears_in_reports` | Expected: a renewal raises the renewed count and the dashboard renewals figure | PASS |
| 7 | `test_status_changes_appear_in_reports` | Expected: activating raises and cancelling lowers the active memberships count | PASS |

## Problems found

None. Every test passed.

## Conclusion

All tests passed. The tested functions behave as specified.
