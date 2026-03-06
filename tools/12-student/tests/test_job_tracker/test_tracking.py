"""Tests for JobTracker pipeline and analytics."""

from openclaw_shared.database import get_db


class TestPipelineManager:
    def test_get_kanban_data(self, seeded_db_paths):
        from student.job_tracker.tracking.pipeline_manager import get_kanban_data

        kanban = get_kanban_data(seeded_db_paths["job_tracker"])
        assert isinstance(kanban, dict)

    def test_get_stage_counts(self, seeded_db_paths):
        from student.job_tracker.tracking.pipeline_manager import get_stage_counts

        counts = get_stage_counts(seeded_db_paths["job_tracker"])
        assert isinstance(counts, dict)
        total = sum(counts.values())
        assert total > 0

    def test_update_stage(self, seeded_db_paths):
        from student.job_tracker.tracking.pipeline_manager import update_stage

        db = seeded_db_paths["job_tracker"]
        with get_db(db) as conn:
            app = conn.execute("SELECT id, stage FROM applications LIMIT 1").fetchone()

        if app:
            update_stage(app[0], "applied", db)
            with get_db(db) as conn:
                updated = conn.execute(
                    "SELECT stage FROM applications WHERE id = ?", (app[0],)
                ).fetchone()
            assert updated[0] == "applied"


class TestAnalyticsEngine:
    def test_get_funnel_data(self, seeded_db_paths):
        from student.job_tracker.tracking.analytics_engine import get_funnel_data

        funnel = get_funnel_data(seeded_db_paths["job_tracker"])
        assert isinstance(funnel, dict)

    def test_get_response_rate(self, seeded_db_paths):
        from student.job_tracker.tracking.analytics_engine import get_response_rate

        rate = get_response_rate(seeded_db_paths["job_tracker"])
        assert isinstance(rate, float)
        assert 0 <= rate <= 1.0

    def test_create_snapshot(self, seeded_db_paths):
        from student.job_tracker.tracking.analytics_engine import create_snapshot

        db = seeded_db_paths["job_tracker"]
        create_snapshot(db)
        with get_db(db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM analytics_snapshots").fetchone()[0]
        assert count >= 1


class TestInterviewScheduler:
    def test_get_upcoming_interviews_empty(self, db_paths):
        from student.job_tracker.tracking.interview_scheduler import get_upcoming_interviews

        interviews = get_upcoming_interviews(db_paths["job_tracker"])
        assert isinstance(interviews, list)
        assert len(interviews) == 0
