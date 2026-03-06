"""Tests for StudyBuddy indexing and course organization."""

from openclaw_shared.database import get_db


class TestCourseOrganizer:
    def test_get_course_tree(self, seeded_db_paths):
        from student.study_buddy.indexing.course_organizer import get_course_tree

        tree = get_course_tree(seeded_db_paths["study_buddy"])
        assert isinstance(tree, list)
        assert len(tree) > 0
        for semester in tree:
            assert "semester" in semester
            assert "courses" in semester

    def test_get_course_topics_empty(self, db_paths):
        from student.study_buddy.indexing.course_organizer import get_course_topics

        topics = get_course_topics(db_paths["study_buddy"], 999)
        assert isinstance(topics, list)
        assert len(topics) == 0
