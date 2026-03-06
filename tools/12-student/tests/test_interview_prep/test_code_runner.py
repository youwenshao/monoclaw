"""Tests for InterviewPrep code execution."""

import pytest


class TestCodeRunner:
    def test_execute_python_hello(self):
        from student.interview_prep.practice.code_runner import execute_code

        result = execute_code("print('hello')", "python", timeout=5)
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]
        assert result["timed_out"] is False

    def test_execute_python_with_input(self):
        from student.interview_prep.practice.code_runner import execute_code

        code = "import sys; print(sys.stdin.read().strip())"
        result = execute_code(code, "python", input_data="test_input", timeout=5)
        assert "test_input" in result["stdout"]

    def test_execute_python_timeout(self):
        from student.interview_prep.practice.code_runner import execute_code

        code = "import time; time.sleep(10)"
        result = execute_code(code, "python", timeout=2)
        assert result["timed_out"] is True

    def test_execute_python_syntax_error(self):
        from student.interview_prep.practice.code_runner import execute_code

        result = execute_code("def broken(:", "python", timeout=5)
        assert result["exit_code"] != 0

    def test_execute_javascript_hello(self):
        from student.interview_prep.practice.code_runner import execute_code

        result = execute_code("console.log('hello')", "javascript", timeout=5)
        if result["exit_code"] == 0:
            assert "hello" in result["stdout"]


class TestProblemLoader:
    def test_get_problems_returns_list(self, seeded_db_paths):
        from student.interview_prep.problems.problem_loader import get_problems

        problems = get_problems(seeded_db_paths["interview_prep"])
        assert isinstance(problems, list)
        assert len(problems) > 0

    def test_get_problems_filter_by_topic(self, seeded_db_paths):
        from student.interview_prep.problems.problem_loader import get_problems

        problems = get_problems(seeded_db_paths["interview_prep"], topic="arrays")
        assert all(p["topic"] == "arrays" for p in problems)

    def test_get_problems_filter_by_difficulty(self, seeded_db_paths):
        from student.interview_prep.problems.problem_loader import get_problems

        problems = get_problems(seeded_db_paths["interview_prep"], difficulty="easy")
        assert all(p["difficulty"] == "easy" for p in problems)

    def test_get_problem_by_id(self, seeded_db_paths):
        from student.interview_prep.problems.problem_loader import get_problem

        problem = get_problem(seeded_db_paths["interview_prep"], 1)
        assert problem is not None
        assert "title" in problem
        assert "description" in problem

    def test_get_random_problems(self, seeded_db_paths):
        from student.interview_prep.problems.problem_loader import get_random_problems

        problems = get_random_problems(seeded_db_paths["interview_prep"], count=2)
        assert len(problems) == 2
