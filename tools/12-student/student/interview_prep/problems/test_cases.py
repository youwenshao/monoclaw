"""Run code against test cases in a sandboxed subprocess."""

from __future__ import annotations

from student.interview_prep.practice.code_runner import execute_code


def run_test_cases(
    code: str,
    language: str,
    test_cases: list[dict],
    timeout: int = 5,
) -> dict:
    results = []
    passed = 0

    for tc in test_cases:
        input_data = _format_input(tc.get("input", {}), language)
        expected = tc.get("expected")

        full_code = _wrap_code(code, tc.get("input", {}), language)
        execution = execute_code(full_code, language, timeout=timeout)

        actual_output = execution["stdout"].strip() if not execution["timed_out"] else None
        is_passed = False

        if actual_output is not None and not execution.get("stderr"):
            try:
                import json
                actual_parsed = json.loads(actual_output)
                is_passed = actual_parsed == expected
            except (json.JSONDecodeError, TypeError):
                is_passed = str(actual_output) == str(expected)

        if is_passed:
            passed += 1

        results.append({
            "input": tc.get("input"),
            "expected": expected,
            "actual": actual_output,
            "passed": is_passed,
            "error": execution.get("stderr", ""),
            "timed_out": execution.get("timed_out", False),
        })

    return {"passed": passed, "total": len(test_cases), "results": results}


def _format_input(input_data: dict, language: str) -> str:
    import json
    return json.dumps(input_data)


def _wrap_code(code: str, input_data: dict, language: str) -> str:
    import json

    if language == "python":
        args = ", ".join(f"{k}={json.dumps(v)}" for k, v in input_data.items())
        func_name = _extract_function_name(code, language)
        return f"{code}\n\nimport json\nprint(json.dumps({func_name}({args})))"

    if language == "javascript":
        args = ", ".join(json.dumps(v) for v in input_data.values())
        func_name = _extract_function_name(code, language)
        return f"{code}\n\nconsole.log(JSON.stringify({func_name}({args})));"

    return code


def _extract_function_name(code: str, language: str) -> str:
    import re
    if language == "python":
        match = re.search(r"def\s+(\w+)\s*\(", code)
    else:
        match = re.search(r"function\s+(\w+)\s*\(", code)
    return match.group(1) if match else "solution"
