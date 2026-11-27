"""Makes a testing report (Markdown) from a test module.

Run from the project folder:
    python -m tests.report unit          ->  test_reports/Unit_Testing_Report.md
    python -m tests.report integration   ->  test_reports/Integration_Testing_Report.md   (Lab 40)
    python -m tests.report e2e           ->  test_reports/End_to_End_Testing_Report.md    (Lab 41)
"""
import importlib
import inspect
import os
import platform
import sys
import time
import unittest
from datetime import datetime

import tests  # noqa: F401  (switches the app to a temporary database before anything else loads)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "test_reports")

SUITES = {
    "unit": ("Unit Testing Report", "tests.test_unit", "Unit_Testing_Report.md",
             "Each test checks one function on its own, using a temporary database."),
    "integration": ("Integration Testing Report", "tests.test_integration", "Integration_Testing_Report.md",
                    "Each test checks that two modules work correctly together."),
    "e2e": ("End-to-End System Testing Report", "tests.test_e2e", "End_to_End_Testing_Report.md",
            "One complete gym transaction, step by step, through the real pages."),
}


class Collector(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = []          # (area, name, description, outcome, detail, order)
        self._start = {}

    def startTest(self, test):
        super().startTest(test)
        self._start[test] = time.perf_counter()

    def _add(self, test, outcome, detail=""):
        area = (type(test).__doc__ or type(test).__name__).strip().splitlines()[0]
        method = getattr(test, test._testMethodName)
        description = ((method.__doc__ or "").strip().splitlines() or [test._testMethodName])[0]
        order = inspect.getsourcelines(type(test))[1]     # keep the areas in the order they are written
        self.rows.append((area, test._testMethodName, description, outcome, detail, order))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._add(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._add(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._add(test, "ERROR", self._exc_info_to_string(err, test))


def build_report(title, intro, rows, seconds):
    total = len(rows)
    passed = sum(r[3] == "PASS" for r in rows)
    failed = sum(r[3] == "FAIL" for r in rows)
    errors = sum(r[3] == "ERROR" for r in rows)
    lines = [f"# Gym Management System - {title}", "",
             f"- **Date:** {datetime.now():%B %d, %Y %I:%M %p}",
             f"- **Environment:** Python {platform.python_version()} on {platform.system()}, SQLite (temporary test database)",
             f"- **Scope:** {intro}", "",
             "## Summary", "",
             "| Total tests | Passed | Failed | Errors | Pass rate | Time |", "|---|---|---|---|---|---|",
             f"| {total} | {passed} | {failed} | {errors} | {passed * 100 / total:.0f}% | {seconds:.1f} s |" if total
             else "| 0 | 0 | 0 | 0 | - | - |", ""]
    areas = {}
    for row in rows:
        areas.setdefault(row[0], []).append(row)
    lines += ["## Results by area", "", "| Area | Tests | Passed | Result |", "|---|---|---|---|"]
    for area, items in areas.items():
        ok = sum(i[3] == "PASS" for i in items)
        lines.append(f"| {area} | {len(items)} | {ok} | {'PASS' if ok == len(items) else 'FAIL'} |")
    lines.append("")
    for area, items in areas.items():
        lines += [f"## {area}", "", "| # | Test case | What it checks | Result |", "|---|---|---|---|"]
        for number, (_, name, description, outcome, *_rest) in enumerate(items, 1):
            lines.append(f"| {number} | `{name}` | {description} | {outcome} |")
        lines.append("")
    problems = [r for r in rows if r[3] != "PASS"]
    lines += ["## Problems found", ""]
    if not problems:
        lines.append("None. Every test passed.")
    for area, name, description, outcome, detail, _order in problems:
        lines += [f"### {area}: `{name}` ({outcome})", "", "```", detail.strip(), "```", ""]
    lines += ["", "## Conclusion", "",
              "All tests passed. The tested functions behave as specified." if not problems
              else f"{len(problems)} test(s) need attention before this stage can be signed off."]
    return "\n".join(lines) + "\n"


def main(argv):
    key = argv[1] if len(argv) > 1 else "unit"
    if key not in SUITES:
        print("Choose one of:", ", ".join(SUITES))
        return 2
    title, module, filename, intro = SUITES[key]
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(module))
    except ModuleNotFoundError:
        print(f"{module} does not exist yet.")
        return 2
    result = Collector()
    started = time.perf_counter()
    suite.run(result)
    seconds = time.perf_counter() - started
    result.rows.sort(key=lambda r: (r[5], r[1]))
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_report(title, intro, result.rows, seconds))
    passed = sum(r[3] == "PASS" for r in result.rows)
    print(f"{title}: {passed}/{len(result.rows)} passed. Saved to {os.path.relpath(path, ROOT)}")
    return 0 if passed == len(result.rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
