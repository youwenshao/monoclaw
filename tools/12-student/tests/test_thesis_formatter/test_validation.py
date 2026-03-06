"""Tests for ThesisFormatter validation modules."""

import json


class TestReportGenerator:
    def test_generate_report(self):
        from student.thesis_formatter.validation.report_generator import generate_report

        checks = [
            {"check_type": "margin", "passed": True, "message": "OK", "severity": "error"},
            {"check_type": "font", "passed": False, "message": "Wrong font", "severity": "error"},
            {"check_type": "spacing", "passed": True, "message": "OK", "severity": "warning"},
        ]
        report = generate_report(checks)
        assert report["total"] == 3
        assert report["passed"] == 2
        assert report["failed"] == 1
        assert report["errors"] >= 1


class TestCompletenessChecker:
    def test_check_completeness_empty_profile(self):
        from student.thesis_formatter.validation.completeness_checker import check_completeness

        profile = {
            "required_sections": json.dumps(["cover", "title", "toc", "chapter", "bibliography"]),
        }
        results = check_completeness("/nonexistent/file.docx", profile)
        assert isinstance(results, list)


class TestProfilesExist:
    def test_university_profiles_loadable(self):
        from student.thesis_formatter.formatting.styles_manager import get_style_config

        for uni in ["HKU", "CUHK", "HKUST", "PolyU", "CityU"]:
            config = get_style_config(uni)
            assert isinstance(config, dict)
            assert "university" in config or "font_name" in config
