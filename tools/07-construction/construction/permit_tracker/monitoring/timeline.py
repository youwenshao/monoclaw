"""Expected timeline calculation for BD submissions.

Uses statutory processing periods from the Buildings Ordinance and
Practice Notes to estimate completion dates.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.monitoring.timeline")

DEFAULT_TIMELINES: dict[str, int] = {
    "GBP": 60,
    "foundation": 30,
    "superstructure": 60,
    "drainage": 45,
    "demolition": 30,
    "OP": 45,
    "minor_works": 42,
    "nwsc": 30,
    "other": 60,
}

MINOR_WORKS_TIMELINES: dict[str, int] = {
    "I": 42,
    "II": 28,
    "III": 14,
}


def calculate_expected_completion(
    submission_type: str,
    submitted_date: str,
    config: dict[str, Any] | None = None,
) -> str:
    """Calculate the expected completion date for a submission.

    Args:
        submission_type: The BD submission type (GBP, foundation, etc.).
        submitted_date: ISO date string of when the submission was filed.
        config: Optional config dict with custom timeline overrides under
                ``config["expected_timelines"]``.

    Returns:
        ISO date string of the expected completion date.
    """
    sub_date = date.fromisoformat(submitted_date[:10])

    custom_timelines = (config or {}).get("expected_timelines", {})
    days = custom_timelines.get(submission_type) or DEFAULT_TIMELINES.get(submission_type, 60)

    expected = sub_date + timedelta(days=int(days))
    return expected.isoformat()


def calculate_expected_completion_mw(
    mw_class: str,
    submitted_date: str,
) -> str:
    """Calculate expected completion for a minor works submission by class."""
    sub_date = date.fromisoformat(submitted_date[:10])
    days = MINOR_WORKS_TIMELINES.get(mw_class.upper().strip(), 42)
    return (sub_date + timedelta(days=days)).isoformat()


def is_overdue(submission: dict, config: dict[str, Any] | None = None) -> bool:
    """Check whether a submission has exceeded its expected processing time.

    A submission is considered overdue if:
    - It has a submitted_date
    - It is not in a terminal status
    - The current date exceeds the expected completion date
    """
    if submission.get("current_status") in (
        "Approved", "Consent Issued", "Rejected", "Withdrawn", "Completed", None
    ):
        return False

    submitted_date = submission.get("submitted_date")
    if not submitted_date:
        return False

    sub_type = submission.get("submission_type", "GBP")

    if sub_type == "minor_works" and submission.get("minor_works_class"):
        expected_str = calculate_expected_completion_mw(
            submission["minor_works_class"],
            str(submitted_date),
        )
    else:
        pt_config = (config or {}).get("permit_tracker", {}) if config else {}
        expected_str = calculate_expected_completion(sub_type, str(submitted_date), pt_config)

    expected = date.fromisoformat(expected_str)
    return date.today() > expected


def days_remaining(submission: dict, config: dict[str, Any] | None = None) -> int:
    """Calculate the number of days until expected completion.

    Returns a negative value if the submission is overdue.
    """
    submitted_date = submission.get("submitted_date")
    if not submitted_date:
        return 0

    sub_type = submission.get("submission_type", "GBP")

    if sub_type == "minor_works" and submission.get("minor_works_class"):
        expected_str = calculate_expected_completion_mw(
            submission["minor_works_class"],
            str(submitted_date),
        )
    else:
        pt_config = (config or {}).get("permit_tracker", {}) if config else {}
        expected_str = calculate_expected_completion(sub_type, str(submitted_date), pt_config)

    expected = date.fromisoformat(expected_str)
    return (expected - date.today()).days
