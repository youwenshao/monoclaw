"""Tests for JobTracker parsing modules."""


class TestGenericParser:
    def test_parse_text_extracts_fields(self):
        from student.job_tracker.parsing.generic_parser import parse_text

        raw = """
        Software Engineer
        HSBC Technology
        Location: Central, Hong Kong
        Salary: HK$25,000 - HK$35,000 per month
        Requirements:
        - BSc Computer Science
        - Python and Java
        - 2 years experience
        Benefits: 13th month pay, medical insurance
        """
        result = parse_text(raw)
        assert isinstance(result, dict)
        assert "title" in result or "description_raw" in result


class TestJdStructurer:
    def test_detect_source_ctgoodjobs(self):
        from student.job_tracker.parsing.jd_structurer import detect_source

        assert detect_source("https://www.ctgoodjobs.hk/job/123") == "ctgoodjobs"

    def test_detect_source_jobsdb(self):
        from student.job_tracker.parsing.jd_structurer import detect_source

        assert detect_source("https://hk.jobsdb.com/job/456") == "jobsdb"

    def test_detect_source_linkedin(self):
        from student.job_tracker.parsing.jd_structurer import detect_source

        assert detect_source("https://www.linkedin.com/jobs/view/789") == "linkedin"

    def test_detect_source_unknown(self):
        from student.job_tracker.parsing.jd_structurer import detect_source

        assert detect_source("https://example.com/careers") == "other"
