"""Tests for ClientPortal status tracking and FAQ."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from immigration.client_portal.status.tracker import (
    VALID_STATUSES,
    get_next_steps,
    get_status_display,
)
from immigration.client_portal.status.timeline import estimate_completion
from immigration.client_portal.appointments.booking import get_available_slots


class TestStatusTracker:
    """Status tracking tests per prompt criteria."""

    def test_valid_statuses_complete(self):
        """All 9 standard ImmD statuses should be defined."""
        expected = {
            "documents_gathering",
            "application_submitted",
            "acknowledgement_received",
            "additional_documents_requested",
            "under_processing",
            "approval_in_principle",
            "visa_label_issued",
            "entry_made",
            "hkid_applied",
        }
        assert expected.issubset(set(VALID_STATUSES))

    def test_status_display_english(self):
        label = get_status_display("under_processing", "en")
        assert isinstance(label, str)
        assert len(label) > 0

    def test_status_display_chinese(self):
        label = get_status_display("under_processing", "zh")
        assert isinstance(label, str)
        assert len(label) > 0

    def test_next_steps_returns_text(self):
        steps = get_next_steps("application_submitted", "GEP", "en")
        assert isinstance(steps, str)
        assert len(steps) > 0


class TestTimeline:
    """Processing time estimation tests."""

    def test_gep_estimate(self):
        from datetime import date, timedelta
        submitted = (date.today() - timedelta(days=14)).isoformat()
        config_times = {"GEP": {"min": 4, "max": 6}}
        result = estimate_completion("GEP", submitted, config_times, [])
        assert "estimated_min_date" in result
        assert "estimated_max_date" in result

    def test_qmas_longer_estimate(self):
        from datetime import date
        submitted = date.today().isoformat()
        config_times = {"QMAS": {"min": 36, "max": 48}}
        result = estimate_completion("QMAS", submitted, config_times, [])
        assert result["estimated_max_date"] > result["estimated_min_date"]


class TestAppointments:
    """Appointment booking tests per prompt criteria."""

    def test_weekday_slots_generated(self):
        from datetime import date
        # Find next Monday
        d = date.today()
        while d.weekday() != 0:
            from datetime import timedelta
            d += timedelta(days=1)
        slots = get_available_slots(d, "09:00-18:00", "09:00-13:00", [])
        assert len(slots) > 0

    def test_sunday_no_slots(self):
        from datetime import date, timedelta
        d = date.today()
        while d.weekday() != 6:
            d += timedelta(days=1)
        slots = get_available_slots(d, "09:00-18:00", "09:00-13:00", [])
        assert len(slots) == 0

    def test_public_holiday_excluded(self):
        from datetime import date, timedelta
        d = date.today()
        while d.weekday() != 0:
            d += timedelta(days=1)
        slots = get_available_slots(d, "09:00-18:00", "09:00-13:00", [d.isoformat()])
        assert len(slots) == 0
