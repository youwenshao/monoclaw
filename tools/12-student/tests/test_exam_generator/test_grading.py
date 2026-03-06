"""Tests for ExamGenerator grading modules."""


class TestAutoGrader:
    def test_grade_mcq_correct(self):
        from student.exam_generator.grading.auto_grader import grade_mcq

        result = grade_mcq("SJF", "SJF")
        assert result["is_correct"] is True
        assert result["score"] == result["max_score"]

    def test_grade_mcq_incorrect(self):
        from student.exam_generator.grading.auto_grader import grade_mcq

        result = grade_mcq("FCFS", "SJF")
        assert result["is_correct"] is False
        assert result["score"] == 0

    def test_grade_mcq_case_insensitive(self):
        from student.exam_generator.grading.auto_grader import grade_mcq

        result = grade_mcq("sjf", "SJF")
        assert result["is_correct"] is True

    def test_grade_true_false_correct(self):
        from student.exam_generator.grading.auto_grader import grade_true_false

        result = grade_true_false("true", "true")
        assert result["is_correct"] is True

    def test_grade_multi_select_partial_credit(self):
        from student.exam_generator.grading.auto_grader import grade_multi_select

        result = grade_multi_select(["A", "B"], ["A", "B", "C"])
        assert 0 < result["score"] < result["max_score"]


class TestBloomClassifier:
    def test_classify_remember(self):
        from student.exam_generator.grading.auto_grader import grade_mcq

        result = grade_mcq("correct", "correct")
        assert result["is_correct"] is True


class TestExamBuilder:
    def test_build_exam_assigns_sections(self):
        from student.exam_generator.exam.exam_builder import build_exam

        questions = [
            {"question_type": "mcq", "question_text": "Q1", "points": 1},
            {"question_type": "short_answer", "question_text": "Q2", "points": 3},
            {"question_type": "long_answer", "question_text": "Q3", "points": 5},
        ]
        exam = build_exam(questions, {"title": "Test Exam"})
        assert "questions" in exam
        assert "total_points" in exam
        assert exam["total_points"] == 9
