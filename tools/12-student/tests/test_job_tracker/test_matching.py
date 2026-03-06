"""Tests for JobTracker CV matching modules."""


class TestKeywordMatcher:
    def test_match_keywords_perfect_match(self):
        from student.job_tracker.matching.keyword_matcher import match_keywords

        result = match_keywords(
            ["python", "sql", "java"],
            ["python", "sql", "java"],
        )
        assert result["match_score"] >= 0.9
        assert len(result["unmatched_jd_skills"]) == 0

    def test_match_keywords_partial_match(self):
        from student.job_tracker.matching.keyword_matcher import match_keywords

        result = match_keywords(
            ["python", "sql"],
            ["python", "sql", "java", "docker"],
        )
        assert 0 < result["match_score"] < 1.0
        assert len(result["unmatched_jd_skills"]) > 0

    def test_match_keywords_no_match(self):
        from student.job_tracker.matching.keyword_matcher import match_keywords

        result = match_keywords(
            ["cooking", "painting"],
            ["python", "sql", "java"],
        )
        assert result["match_score"] < 0.5

    def test_match_keywords_empty_cv(self):
        from student.job_tracker.matching.keyword_matcher import match_keywords

        result = match_keywords([], ["python", "sql"])
        assert result["match_score"] == 0.0


class TestGapAnalyzer:
    def test_analyze_gaps(self):
        from student.job_tracker.matching.gap_analyzer import analyze_gaps

        cv_profile = {"skills": ["python", "sql"], "keywords": ["data analysis"]}
        job_listing = {
            "skills_required": '["python", "sql", "java", "docker"]',
            "requirements": '["BSc Computer Science", "3 years experience"]',
        }
        result = analyze_gaps(cv_profile, job_listing)
        assert isinstance(result, dict)
        assert "missing_skills" in result
