"""Tests for InterviewPrep progress tracking."""

from openclaw_shared.database import get_db


class TestProgressTracker:
    def test_get_topic_progress_empty(self, db_paths):
        from student.interview_prep.tracking.progress_tracker import get_topic_progress

        progress = get_topic_progress(db_paths["interview_prep"])
        assert isinstance(progress, list)

    def test_get_streak_no_attempts(self, db_paths):
        from student.interview_prep.tracking.progress_tracker import get_streak

        streak = get_streak(db_paths["interview_prep"])
        assert streak == 0


class TestWeaknessAnalyzer:
    def test_analyze_empty(self, db_paths):
        from student.interview_prep.tracking.weakness_analyzer import analyze_weaknesses

        weaknesses = analyze_weaknesses(db_paths["interview_prep"])
        assert isinstance(weaknesses, list)
