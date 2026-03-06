"""Tests for PermitTracker scrapers."""

from construction.permit_tracker.scrapers.parser import (
    extract_bd_reference,
    parse_status_label,
)


def test_extract_bd_reference_building_plan():
    assert extract_bd_reference("Reference: BP/2026/0042") == "BP/2026/0042"


def test_extract_bd_reference_minor_works():
    assert extract_bd_reference("MW/2026/0101 submitted") == "MW/2026/0101"


def test_extract_bd_reference_nwsc():
    ref = extract_bd_reference("NWSC/2026/0012")
    assert ref == "NWSC/2026/0012"


def test_extract_bd_reference_none():
    assert extract_bd_reference("No reference here") is None


def test_parse_status_label_normalizes():
    assert parse_status_label("Under Examination") == "Under Examination"
    assert parse_status_label("under examination") == "Under Examination"


def test_parse_status_label_amendments():
    result = parse_status_label("Amendments Required")
    assert "Amendments" in result or "Amendment" in result
