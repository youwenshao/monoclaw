"""Generate detailed solution explanations with complexity analysis."""

from __future__ import annotations


async def explain_solution(problem: dict, student_code: str | None, llm) -> str:
    parts = [
        f"Problem: {problem.get('title', '')}",
        f"Description: {problem.get('description', '')}",
        f"Optimal time complexity: {problem.get('optimal_time_complexity', 'N/A')}",
        f"Optimal space complexity: {problem.get('optimal_space_complexity', 'N/A')}",
    ]

    if problem.get("solution_python"):
        parts.append(f"\nReference solution:\n{problem['solution_python']}")

    if student_code:
        parts.append(f"\nStudent's code:\n{student_code}")
        parts.append(
            "\nProvide a detailed walkthrough of the optimal solution, explain the approach, "
            "analyze the time and space complexity, and compare with the student's code if it differs."
        )
    else:
        parts.append(
            "\nProvide a detailed walkthrough of the optimal solution, explain the approach step by step, "
            "and analyze the time and space complexity."
        )

    prompt = "\n".join(parts)
    response = await llm.generate(prompt)
    return response if isinstance(response, str) else response.get("text", "Explanation not available")
