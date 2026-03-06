"""Tests for SafetyForm inspections."""

from construction.safety_form.inspections.checklist_engine import (
    get_default_checklist,
    get_checklist_for_site_type,
    calculate_inspection_score,
)


def test_default_checklist_has_categories():
    items = get_default_checklist()
    assert len(items) > 0
    categories = {item["category"] for item in items}
    assert "housekeeping" in categories
    assert "ppe" in categories
    assert "scaffolding" in categories


def test_default_checklist_items_have_description():
    items = get_default_checklist()
    for item in items:
        assert "category" in item
        assert "description" in item
        assert len(item["description"]) > 0


def test_site_type_checklist_building():
    items = get_checklist_for_site_type("building")
    assert len(items) > 0


def test_site_type_checklist_civil():
    items = get_checklist_for_site_type("civil")
    assert len(items) > 0


def test_inspection_score_all_pass():
    items = [{"status": "pass"} for _ in range(10)]
    score = calculate_inspection_score(items)
    assert score == 100.0


def test_inspection_score_mixed():
    items = [
        {"status": "pass"}, {"status": "pass"}, {"status": "pass"},
        {"status": "fail"}, {"status": "na"},
    ]
    score = calculate_inspection_score(items)
    assert 0 < score < 100


def test_inspection_score_all_fail():
    items = [{"status": "fail"} for _ in range(5)]
    score = calculate_inspection_score(items)
    assert score == 0.0
