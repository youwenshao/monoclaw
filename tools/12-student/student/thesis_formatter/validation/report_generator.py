"""Summarize validation check results into a report."""

from __future__ import annotations


def generate_report(checks: list[dict]) -> dict:
    total = len(checks)
    passed = sum(1 for c in checks if c.get("passed"))
    failed = total - passed

    errors = [c for c in checks if not c.get("passed") and c.get("severity") == "error"]
    warnings = [c for c in checks if not c.get("passed") and c.get("severity") == "warning"]

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": len(errors),
        "warnings": len(warnings),
        "details": checks,
    }
