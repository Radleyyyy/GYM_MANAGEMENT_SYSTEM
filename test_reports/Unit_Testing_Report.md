# Gym Management System - Unit Testing Report

- **Date:** November 27, 2026 10:37 AM
- **Environment:** Python 3.13.18 on Linux, SQLite (temporary test database)
- **Scope:** Each test checks one function on its own, using a temporary database.

## Summary

| Total tests | Passed | Failed | Errors | Pass rate | Time |
|---|---|---|---|---|---|
| 56 | 56 | 0 | 0 | 100% | 0.6 s |

## Results by area

| Area | Tests | Passed | Result |
|---|---|---|---|
| Member registration | 10 | 10 | PASS |
| Plan registration | 6 | 6 | PASS |
| Membership creation | 8 | 8 | PASS |
| Expiration calculation | 6 | 6 | PASS |
| Attendance recording | 7 | 7 | PASS |
| Payment calculation | 9 | 9 | PASS |
| Renewal processing | 5 | 5 | PASS |
| Report generation | 5 | 5 | PASS |

## Member registration

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_create_member_saves_the_data` | create_member stores every field and starts the member as active | PASS |
| 2 | `test_duplicate_email_and_phone_detected` | Duplicate email (any letter case) and phone number are rejected | PASS |
| 3 | `test_edit_may_keep_own_email` | A member can keep their own email and phone when editing | PASS |
| 4 | `test_get_missing_member` | Looking up a member that does not exist gives None | PASS |
| 5 | `test_invalid_values` | Bad email, phone, gender, course and birth dates are rejected | PASS |
| 6 | `test_member_number_is_generated` | Member numbers look like GYM-0001 and keep increasing | PASS |
| 7 | `test_required_fields` | Each missing required field is reported | PASS |
| 8 | `test_set_status` | set_status changes the member status | PASS |
| 9 | `test_update_member` | update_member changes the stored details | PASS |
| 10 | `test_valid_form_has_no_errors` | A complete, correct form passes validation | PASS |

## Plan registration

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_bad_values_rejected` | Bad code, duration, price, access type and status are rejected | PASS |
| 2 | `test_create_plan_saves_the_data` | create_plan stores the plan and rounds the price to 2 decimals | PASS |
| 3 | `test_duplicate_code_and_name_detected` | A plan code or name that already exists is rejected | PASS |
| 4 | `test_inactive_plan_not_offered` | Only active plans are offered for new memberships | PASS |
| 5 | `test_update_plan` | update_plan changes the stored details | PASS |
| 6 | `test_valid_plan_has_no_errors` | A complete, correct plan form passes validation | PASS |

## Membership creation

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_create_membership_saves_pending_with_plan_price` | create_membership saves a pending membership with the plan price and an expiration record | PASS |
| 2 | `test_duplicate_open_membership_rejected` | A member with an active or pending membership cannot get another | PASS |
| 3 | `test_invalid_plan_or_member` | Unknown, inactive or missing plan/member are rejected | PASS |
| 4 | `test_invalid_start_dates` | Past, too-far-ahead and impossible start dates are rejected | PASS |
| 5 | `test_registrable_members_exclude_open_memberships` | Members who already have an open membership are not offered | PASS |
| 6 | `test_status_change_rules` | Only allowed status changes are accepted | PASS |
| 7 | `test_valid_membership_calculates_end_date` | A valid request gives the plan price period: start + plan months | PASS |
| 8 | `test_wrong_end_date_refused` | create_membership refuses an end date that does not match the plan | PASS |

## Expiration calculation

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_add_months` | add_months handles month ends, leap years and year changes | PASS |
| 2 | `test_counts_cover_every_filter` | counts returns one number for each filter | PASS |
| 3 | `test_filter_conditions` | Each expiration filter builds the right date condition | PASS |
| 4 | `test_filters_pick_the_right_memberships` | today / 7 days / 30 days / expired filters select by end date | PASS |
| 5 | `test_status_update_marks_expired_and_activates_paid` | The daily update expires lapsed memberships and activates paid pending ones | PASS |
| 6 | `test_total_outstanding` | total_outstanding adds up the balances that are not fully paid | PASS |

## Attendance recording

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_access_rules` | validate_checkin allows only active, paid, unexpired, not-inside members | PASS |
| 2 | `test_check_in_creates_an_open_visit` | create_checkin saves an open visit and the member counts as inside | PASS |
| 3 | `test_check_out_records_time_and_duration` | checkout saves the time out and the length of the visit | PASS |
| 4 | `test_check_out_twice_or_unknown` | A visit can only be checked out once; unknown visits are refused | PASS |
| 5 | `test_daily_statistics` | get_daily_stats counts visits, members and the average duration of a day | PASS |
| 6 | `test_formatting` | Dates, times and durations are shown in a friendly format | PASS |
| 7 | `test_history_filters_by_date` | get_history returns a member's visits, newest first, within the dates asked | PASS |

## Payment calculation

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_bad_bill_inputs` | Impossible discounts and bad numbers are refused | PASS |
| 2 | `test_bill_total` | Total = plan price - discount + additional charges | PASS |
| 3 | `test_first_payment_applies_discount` | The first payment uses the discounted bill as the amount due | PASS |
| 4 | `test_partial_then_full_payment` | Payments reduce the balance until the membership is paid | PASS |
| 5 | `test_payment_activates_pending_membership` | The first payment turns a pending membership active | PASS |
| 6 | `test_payment_amount_checks` | validate_payment returns the balance and the payment status | PASS |
| 7 | `test_payment_refused_cases` | Overpayment, bad method, cancelled and unknown memberships are refused | PASS |
| 8 | `test_percent_discount_and_rounding` | A percent discount is worked out and rounded to centavos | PASS |
| 9 | `test_summary_before_any_payment` | An unpaid membership shows 'unpaid' and the full fee as the balance | PASS |

## Renewal processing

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_eligibility_rules` | get_context says who may renew and why not | PASS |
| 2 | `test_period_after_current_membership` | A renewal starts the day after the current membership ends | PASS |
| 3 | `test_period_for_lapsed_membership` | A lapsed membership renews from today | PASS |
| 4 | `test_save_renewal` | save_renewal stores a pending renewal with its expiration record | PASS |
| 5 | `test_save_renewal_expires_lapsed_membership` | Renewing a lapsed membership marks the old one expired | PASS |

## Report generation

| # | Test case | What it checks | Result |
|---|---|---|---|
| 1 | `test_attendance_report` | The attendance report totals visits, members, durations and peak hours | PASS |
| 2 | `test_helpers` | Report helpers: default range, date check and age | PASS |
| 3 | `test_member_report` | The member report counts members by status, gender, age and registration date | PASS |
| 4 | `test_membership_report` | The membership report separates new memberships from renewals | PASS |
| 5 | `test_revenue_report` | The revenue report adds up payments by date, method and renewals | PASS |

## Problems found

None. Every test passed.

## Conclusion

All tests passed. The tested functions behave as specified.
