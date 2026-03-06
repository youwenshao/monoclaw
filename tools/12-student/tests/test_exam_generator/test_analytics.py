"""Tests for ExamGenerator analytics modules."""

from openclaw_shared.database import get_db


class TestPerformanceTracker:
    def test_get_performance_summary_empty(self, db_paths):
        from student.exam_generator.analytics.performance_tracker import get_performance_summary

        summary = get_performance_summary(db_paths["exam_generator"])
        assert isinstance(summary, dict)
        assert "total_attempts" in summary
        assert summary["total_attempts"] == 0


class TestWeaknessAnalyzer:
    def test_analyze_weaknesses_empty(self, db_paths):
        from student.exam_generator.analytics.weakness_analyzer import analyze_weaknesses

        weaknesses = analyze_weaknesses(db_paths["exam_generator"])
        assert isinstance(weaknesses, list)
