"""Heuristic complexity inference for automatic model routing (Max bundle).

Maps the last user message to one of: simple, moderate, complex, code.
Used when model_id is omitted (Auto mode) to select fast/standard/think/coder route.
Pure function, no I/O; thresholds and triggers are tunable via constants.
"""

import re

# Word-count thresholds (tunable)
SIMPLE_MAX_WORDS = 14
COMPLEX_MIN_WORDS = 80

# Code: fenced block or code-like patterns
CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
CODE_PATTERNS = re.compile(
    r"\b(def\s|class\s|import\s|from\s+\w+\s+import|function\s|return\s|=>\s|\.py\b|\.js\b|\.ts\b|\.tsx\b|\.go\b|\.rs\b)",
    re.IGNORECASE,
)

# Complex: explanation/analysis triggers (lowercase for matching)
COMPLEX_TRIGGERS = (
    "explain", "analyze", "why does", "why do", "compare", "reasoning",
    "step by step", "in detail", "walk me through", "break down",
)


def infer_complexity(text: str) -> str:
    """Infer task complexity from user message for model routing.

    Returns one of: "code", "simple", "complex", "moderate".
    Order of checks: code -> simple -> complex -> moderate (default).
    """
    if not text or not text.strip():
        return "moderate"

    s = text.strip()
    words = s.split()

    # 1. Code: fenced block or code-like content
    if CODE_FENCE.search(s) or CODE_PATTERNS.search(s):
        return "code"

    # 2. Simple: short and no complex triggers
    if len(words) <= SIMPLE_MAX_WORDS:
        lower = s.lower()
        if not any(t in lower for t in COMPLEX_TRIGGERS):
            return "simple"

    # 3. Complex: long or explanation/analysis triggers
    if len(words) >= COMPLEX_MIN_WORDS:
        return "complex"
    lower = s.lower()
    if any(t in lower for t in COMPLEX_TRIGGERS):
        return "complex"

    # 4. Default
    return "moderate"
