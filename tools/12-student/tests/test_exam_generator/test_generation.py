"""Tests for ExamGenerator question generation."""


class TestBloomClassifier:
    def test_classify_bloom_level(self):
        from student.exam_generator.generation.bloom_classifier import classify_bloom_level

        level = classify_bloom_level("Define the term 'deadlock'.")
        assert level in ("remember", "understand", "apply", "analyze", "evaluate", "create")

    def test_distribute_questions(self):
        from student.exam_generator.generation.bloom_classifier import distribute_questions

        dist = distribute_questions(20, {"easy": 0.4, "medium": 0.4, "hard": 0.2})
        total = sum(dist.values())
        assert total == 20
        assert dist["easy"] == 8
        assert dist["hard"] == 4


class TestSubjectAdapter:
    def test_get_subject_prompt_comp(self):
        from student.exam_generator.generation.subject_adapter import get_subject_prompt

        prompt = get_subject_prompt("COMP3001")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_subject_prompt_econ(self):
        from student.exam_generator.generation.subject_adapter import get_subject_prompt

        prompt = get_subject_prompt("ECON2220")
        assert isinstance(prompt, str)

    def test_get_subject_prompt_unknown(self):
        from student.exam_generator.generation.subject_adapter import get_subject_prompt

        prompt = get_subject_prompt("XXXX1234")
        assert isinstance(prompt, str)
