"""Tests for SafetyForm reporting."""

from construction.safety_form.reporting.toolbox_talk import get_talk_templates


def test_talk_templates_english():
    templates = get_talk_templates("en")
    assert len(templates) > 0
    for t in templates:
        assert "topic" in t
        assert len(t["topic"]) > 0


def test_talk_templates_chinese():
    templates = get_talk_templates("zh")
    assert len(templates) > 0


def test_talk_templates_have_content():
    templates = get_talk_templates("en")
    for t in templates:
        assert "topic" in t
