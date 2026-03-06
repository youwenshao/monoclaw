"""Tests for database schema initialization and seeding."""

from openclaw_shared.database import get_db


class TestInitAllDatabases:
    def test_creates_all_db_files(self, db_paths):
        expected = {
            "study_buddy",
            "exam_generator",
            "thesis_formatter",
            "interview_prep",
            "job_tracker",
            "shared",
            "mona_events",
        }
        assert set(db_paths.keys()) == expected
        for name, path in db_paths.items():
            assert path.exists(), f"{name} db file missing at {path}"

    def test_study_buddy_schema(self, db_paths):
        with get_db(db_paths["study_buddy"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in ("courses", "documents", "chunks", "queries", "flashcards"):
            assert expected in tables, f"Missing table: {expected}"

    def test_exam_generator_schema(self, db_paths):
        with get_db(db_paths["exam_generator"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in (
            "exams",
            "exam_questions",
            "exam_attempts",
            "attempt_answers",
            "exam_discussions",
            "past_papers",
        ):
            assert expected in tables, f"Missing table: {expected}"

    def test_thesis_formatter_schema(self, db_paths):
        with get_db(db_paths["thesis_formatter"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in ("formatting_profiles", "thesis_projects", "validation_results", "sections"):
            assert expected in tables, f"Missing table: {expected}"

    def test_interview_prep_schema(self, db_paths):
        with get_db(db_paths["interview_prep"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in ("problems", "attempts", "progress", "mock_interviews", "study_plans"):
            assert expected in tables, f"Missing table: {expected}"

    def test_job_tracker_schema(self, db_paths):
        with get_db(db_paths["job_tracker"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for expected in (
            "job_listings",
            "cv_profiles",
            "applications",
            "interviews",
            "analytics_snapshots",
        ):
            assert expected in tables, f"Missing table: {expected}"

    def test_shared_schema(self, db_paths):
        with get_db(db_paths["shared"]) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "shared_students" in tables


class TestSeedAll:
    def test_seed_study_buddy(self, seeded_db_paths):
        with get_db(seeded_db_paths["study_buddy"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM flashcards").fetchone()[0] > 0

    def test_seed_exam_generator(self, seeded_db_paths):
        with get_db(seeded_db_paths["exam_generator"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM exam_questions").fetchone()[0] > 0

    def test_seed_thesis_formatter(self, seeded_db_paths):
        with get_db(seeded_db_paths["thesis_formatter"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM formatting_profiles").fetchone()[0] >= 6

    def test_seed_interview_prep(self, seeded_db_paths):
        with get_db(seeded_db_paths["interview_prep"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0] > 0

    def test_seed_job_tracker(self, seeded_db_paths):
        with get_db(seeded_db_paths["job_tracker"]) as conn:
            assert conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0] > 0
            assert conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0] > 0

    def test_seed_idempotent(self, seeded_db_paths):
        """Running seed_all twice should not duplicate data."""
        from student.seed_data import seed_all
        counts = seed_all(seeded_db_paths)
        assert all(v == 0 for v in counts.values())
