"""Lab 31: Role-Based Access Control.

ROLE_ACCESS maps each role to the modules (blueprints) it may open.
"full" = every action, "read" = view pages only (GET), no changes.
"""
from flask import url_for

ALL_MODULES = ("main", "members", "plans", "courses", "memberships", "renewals",
               "attendance", "billing", "payments", "expiration",
               "notifications", "reports")

ROLE_ACCESS = {
    "Administrator": {m: "full" for m in ALL_MODULES},
    "Gym Manager": {m: "full" for m in ALL_MODULES},
    "Receptionist": {
        "members": "full", "memberships": "full", "renewals": "full",
        "attendance": "full", "plans": "read", "courses": "read",
    },
    "Cashier": {"billing": "full", "payments": "full"},
    "Trainer": {"members": "read", "attendance": "full"},
    "Report Officer": {"main": "read", "reports": "read"},
}

ROLE_HOME = {
    "Receptionist": "members.list_members",
    "Cashier": "payments.list_payments",
    "Trainer": "members.list_members",
}


# Form pages that only change data: read-only roles may not open them either
WRITE_PAGES = {
    "members.register", "members.edit", "plans.register", "plans.edit",
    "courses.add", "courses.edit", "memberships.register",
}


def can(role, module, method="GET", endpoint=None):
    level = ROLE_ACCESS.get(role, {}).get(module)
    if level == "full":
        return True
    return level == "read" and method in ("GET", "HEAD") and endpoint not in WRITE_PAGES


def home_url(role):
    return url_for(ROLE_HOME.get(role, "main.dashboard"))
