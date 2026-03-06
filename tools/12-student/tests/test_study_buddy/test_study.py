"""Tests for StudyBuddy study tools (flashcards, Anki export)."""

from openclaw_shared.database import get_db


class TestAnkiExporter:
    def test_export_deck_with_flashcards(self, seeded_db_paths):
        from student.study_buddy.study.anki_exporter import export_deck

        db = seeded_db_paths["study_buddy"]
        with get_db(db) as conn:
            course = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()

        if course:
            data = export_deck(course[0], db)
            assert isinstance(data, bytes)
            assert len(data) > 0

    def test_export_deck_empty_course(self, db_paths):
        from student.study_buddy.study.anki_exporter import export_deck

        data = export_deck(999, db_paths["study_buddy"])
        assert isinstance(data, bytes)
