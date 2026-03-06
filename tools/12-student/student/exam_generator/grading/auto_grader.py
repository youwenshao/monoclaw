"""Automatic grading for objective question types."""

from __future__ import annotations


def grade_mcq(student_answer: str, correct_answer: str) -> dict:
    is_correct = student_answer.strip().lower() == correct_answer.strip().lower()
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "max_score": 1.0,
        "feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is: {correct_answer}",
    }


def grade_true_false(student_answer: str, correct_answer: str) -> dict:
    student_norm = student_answer.strip().lower()
    correct_norm = correct_answer.strip().lower()

    true_variants = {"true", "t", "yes", "1"}
    false_variants = {"false", "f", "no", "0"}

    student_bool = student_norm in true_variants
    correct_bool = correct_norm in true_variants

    if student_norm not in true_variants and student_norm not in false_variants:
        return {"is_correct": False, "score": 0.0, "max_score": 1.0, "feedback": "Invalid answer format."}

    is_correct = student_bool == correct_bool
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "max_score": 1.0,
        "feedback": "Correct!" if is_correct else f"Incorrect. The answer is: {correct_answer}",
    }


def grade_multi_select(student_answers: list, correct_answers: list) -> dict:
    student_set = {str(a).strip().lower() for a in student_answers}
    correct_set = {str(a).strip().lower() for a in correct_answers}

    if not correct_set:
        return {"is_correct": False, "score": 0.0, "max_score": 1.0, "feedback": "No correct answers defined."}

    correct_selected = student_set & correct_set
    incorrect_selected = student_set - correct_set

    partial_score = len(correct_selected) / len(correct_set)
    penalty = len(incorrect_selected) * (0.5 / len(correct_set))
    score = max(0.0, partial_score - penalty)

    is_correct = student_set == correct_set

    if is_correct:
        feedback = "All correct!"
    else:
        parts = []
        missing = correct_set - student_set
        extra = student_set - correct_set
        if missing:
            parts.append(f"Missing: {', '.join(sorted(missing))}")
        if extra:
            parts.append(f"Incorrect selections: {', '.join(sorted(extra))}")
        feedback = " | ".join(parts)

    return {
        "is_correct": is_correct,
        "score": round(score, 2),
        "max_score": 1.0,
        "feedback": feedback,
    }
