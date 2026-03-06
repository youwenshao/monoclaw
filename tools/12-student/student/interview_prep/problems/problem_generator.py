"""Generate variations of existing coding problems using an LLM."""

from __future__ import annotations


async def generate_variation(problem: dict, llm) -> dict:
    prompt = (
        f"Create a variation of this coding problem. Keep the same topic ({problem.get('topic', 'general')}) "
        f"and difficulty ({problem.get('difficulty', 'medium')}), but change the scenario and constraints.\n\n"
        f"Original problem:\nTitle: {problem.get('title', '')}\n"
        f"Description: {problem.get('description', '')}\n\n"
        f"Return a JSON object with keys: title, description, difficulty, topic, subtopic, "
        f"example_input, example_output, constraints, hints (list of 3 strings), "
        f"test_cases (list of dicts with input and expected keys)."
    )

    response = await llm.generate(prompt)
    text = response if isinstance(response, str) else response.get("text", "")

    import json
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {
            "title": f"Variation of {problem.get('title', 'Unknown')}",
            "description": text,
            "difficulty": problem.get("difficulty", "medium"),
            "topic": problem.get("topic", "general"),
            "subtopic": problem.get("subtopic", ""),
        }
