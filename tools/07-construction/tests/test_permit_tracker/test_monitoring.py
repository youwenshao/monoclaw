"""Tests for PermitTracker monitoring."""

from datetime import date, timedelta

from construction.permit_tracker.monitoring.timeline import (
    calculate_expected_completion,
    is_overdue,
    days_remaining,
)


def _make_config(timelines=None):
    class C:
        extra = {
            "permit_tracker": {
                "expected_timelines": timelines or {
                    "GBP": 60, "foundation": 45, "drainage": 30,
                    "minor_works_I": 42, "minor_works_II": 28, "minor_works_III": 14,
                }
            }
        }
    return C()


def test_calculate_expected_completion_gbp():
    submitted = (date.today() - timedelta(days=10)).isoformat()
    result = calculate_expected_completion("GBP", submitted, _make_config())
    assert result is not None


def test_is_overdue_true():
    sub = {
        "submission_type": "GBP",
        "submitted_date": (date.today() - timedelta(days=90)).isoformat(),
        "current_status": "Under Examination",
    }
    assert is_overdue(sub, _make_config()) is True


def test_is_overdue_false():
    sub = {
        "submission_type": "GBP",
        "submitted_date": (date.today() - timedelta(days=10)).isoformat(),
        "current_status": "Under Examination",
    }
    assert is_overdue(sub, _make_config()) is False


def test_is_overdue_completed_not_counted():
    sub = {
        "submission_type": "GBP",
        "submitted_date": (date.today() - timedelta(days=90)).isoformat(),
        "current_status": "Approved",
    }
    assert is_overdue(sub, _make_config()) is False


def test_days_remaining_positive():
    sub = {
        "submission_type": "GBP",
        "submitted_date": (date.today() - timedelta(days=10)).isoformat(),
        "current_status": "Under Examination",
    }
    remaining = days_remaining(sub, _make_config())
    assert remaining == 50
