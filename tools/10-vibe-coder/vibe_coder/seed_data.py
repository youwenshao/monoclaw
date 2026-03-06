"""Seed demo data for all Vibe Coder tools."""

from __future__ import annotations

import json
from pathlib import Path

from openclaw_shared.database import get_db


def seed_all(db_paths: dict[str, Path]) -> None:
    """Populate all databases with demonstration data."""
    _seed_code_qwen(db_paths["code_qwen"])
    _seed_docu_writer(db_paths["docu_writer"])
    _seed_git_assistant(db_paths["git_assistant"])
    _seed_hk_dev_kit(db_paths["hk_dev_kit"])


def _seed_code_qwen(db_path: Path) -> None:
    db = get_db(db_path)
    db.executemany(
        "INSERT OR IGNORE INTO conversations (id, session_id, feature, input_code, input_language, output_text, model_name, tokens_generated, latency_ms) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, "sess-001", "completion", "def fibonacci(n):\n    ", "python",
             "if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
             "Qwen2.5-Coder-7B", 42, 380),
            (2, "sess-001", "explanation", "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)", "python",
             "This is a recursive implementation of the Fibonacci sequence. It returns the nth Fibonacci number by summing the two preceding numbers. Base case: n <= 1 returns n directly.",
             "Qwen2.5-Coder-7B", 65, 1200),
            (3, "sess-002", "refactoring", "for i in range(len(items)):\n    if items[i].active:\n        result.append(items[i].name)", "python",
             "Consider using a list comprehension:\nresult = [item.name for item in items if item.active]",
             "Qwen2.5-Coder-7B", 38, 950),
            (4, "sess-003", "debugging", "def divide(a, b):\n    return a / b", "python",
             "Potential ZeroDivisionError: no check for b == 0. Add: if b == 0: raise ValueError('Division by zero')",
             "Qwen2.5-Coder-7B", 45, 780),
            (5, "sess-004", "chat", "How do I sort a dictionary by values in Python?", "python",
             "Use sorted() with a lambda key:\nsorted_dict = dict(sorted(my_dict.items(), key=lambda x: x[1]))",
             "Qwen2.5-Coder-7B", 52, 1100),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO completions_cache (id, prefix_hash, suffix_hash, language, completion, confidence, hit_count) VALUES (?,?,?,?,?,?,?)",
        [
            (1, "a1b2c3d4", "e5f6g7h8", "python", "return sorted(items, key=lambda x: x.name)", 0.92, 5),
            (2, "i9j0k1l2", "m3n4o5p6", "javascript", "const result = await fetch(url);", 0.88, 3),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO usage_stats (id, date, feature, request_count, avg_latency_ms, avg_tokens) VALUES (?,?,?,?,?,?)",
        [
            (1, "2026-03-05", "completion", 45, 420.5, 35),
            (2, "2026-03-05", "explanation", 12, 1150.0, 85),
            (3, "2026-03-05", "refactoring", 8, 980.0, 55),
            (4, "2026-03-05", "debugging", 6, 850.0, 48),
            (5, "2026-03-05", "chat", 22, 1050.0, 72),
        ],
    )
    db.commit()
    db.close()


def _seed_docu_writer(db_path: Path) -> None:
    db = get_db(db_path)
    db.executemany(
        "INSERT OR IGNORE INTO projects (id, project_path, project_name, primary_language, last_analyzed, file_count, total_functions, documented_functions, documentation_coverage) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, "/Users/demo/myproject", "myproject", "python", "2026-03-05T10:00:00", 24, 87, 52, 0.598),
            (2, "/Users/demo/frontend-app", "frontend-app", "typescript", "2026-03-04T14:30:00", 56, 134, 98, 0.731),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO generated_docs (id, project_id, doc_type, content, output_path, generation_params) VALUES (?,?,?,?,?,?)",
        [
            (1, 1, "readme", "# myproject\n\nA Python utility library for data processing.\n\n## Installation\n\n```bash\npip install -e .\n```\n",
             "/Users/demo/myproject/README.md", json.dumps({"model": "Qwen2.5-Coder-7B", "temperature": 0.3})),
            (2, 1, "api_reference", "# API Reference\n\n## Functions\n\n### `process_data(input_path, output_path)`\n\nProcess raw data files.\n",
             "/Users/demo/myproject/docs/api.md", json.dumps({"model": "Qwen2.5-Coder-7B", "temperature": 0.2})),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO code_elements (id, project_id, file_path, element_type, element_name, signature, has_docstring, line_number) VALUES (?,?,?,?,?,?,?,?)",
        [
            (1, 1, "src/processor.py", "function", "process_data", "def process_data(input_path: str, output_path: str) -> bool", True, 15),
            (2, 1, "src/processor.py", "function", "validate_input", "def validate_input(data: dict) -> bool", False, 45),
            (3, 1, "src/utils.py", "class", "DataLoader", "class DataLoader", True, 8),
        ],
    )
    db.commit()
    db.close()


def _seed_git_assistant(db_path: Path) -> None:
    db = get_db(db_path)
    db.executemany(
        "INSERT OR IGNORE INTO repositories (id, repo_path, github_remote, github_owner, github_repo, default_branch) VALUES (?,?,?,?,?,?)",
        [
            (1, "/Users/demo/myproject", "https://github.com/demo/myproject.git", "demo", "myproject", "main"),
            (2, "/Users/demo/frontend-app", "https://github.com/demo/frontend-app.git", "demo", "frontend-app", "main"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO pr_generations (id, repo_id, branch_name, base_branch, diff_summary, generated_title, generated_body, files_changed, insertions, deletions, suggested_reviewers) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 1, "feature/auth", "main",
             "Added JWT authentication middleware and user session management",
             "feat: add JWT authentication middleware",
             "## Summary\nAdds JWT-based authentication with session management.\n\n## Changes\n- New auth middleware in `src/auth.py`\n- Session store using Redis\n- Login/logout endpoints\n\n## Test Plan\n- [ ] Unit tests for token generation\n- [ ] Integration test for login flow",
             5, 245, 12, json.dumps(["alice@example.com", "bob@example.com"])),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO release_notes (id, repo_id, from_tag, to_tag, version, notes_content, commit_count, features, fixes, breaking) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 1, "v1.0.0", "v1.1.0", "1.1.0",
             "# Release v1.1.0\n\n## Features\n- JWT authentication\n- User session management\n\n## Bug Fixes\n- Fixed race condition in data processor\n\n## Breaking Changes\n- None",
             15, json.dumps(["JWT authentication", "User session management"]),
             json.dumps(["Fixed race condition in data processor"]),
             json.dumps([])),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO code_ownership (id, repo_id, file_path, author_email, commit_count, lines_owned, last_commit, ownership_score) VALUES (?,?,?,?,?,?,?,?)",
        [
            (1, 1, "src/auth.py", "alice@example.com", 12, 180, "2026-03-04T16:00:00", 0.85),
            (2, 1, "src/processor.py", "bob@example.com", 8, 220, "2026-03-03T11:00:00", 0.72),
            (3, 1, "src/utils.py", "alice@example.com", 5, 95, "2026-02-28T09:00:00", 0.55),
        ],
    )
    db.commit()
    db.close()


def _seed_hk_dev_kit(db_path: Path) -> None:
    db = get_db(db_path)
    db.executemany(
        "INSERT OR IGNORE INTO projects (id, project_name, integrations, created_path) VALUES (?,?,?,?)",
        [
            (1, "hk-payment-demo", json.dumps(["fps", "octopus"]), "/Users/demo/hk-payment-demo"),
            (2, "weather-dashboard", json.dumps(["govhk_weather"]), "/Users/demo/weather-dashboard"),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO snippets (id, title, description, code, language, category, tags, usage_count) VALUES (?,?,?,?,?,?,?,?)",
        [
            (1, "HKID Validation", "Validate Hong Kong Identity Card number with check digit",
             'def validate_hkid(hkid: str) -> bool:\n    """Validate HKID check digit."""\n    hkid = hkid.upper().replace("(", "").replace(")", "")\n    if len(hkid) == 9:\n        prefix = [ord(c) - 55 for c in hkid[:2]]\n        digits = [int(c) for c in hkid[2:8]]\n        check = hkid[8]\n    elif len(hkid) == 8:\n        prefix = [36, ord(hkid[0]) - 55]\n        digits = [int(c) for c in hkid[1:7]]\n        check = hkid[7]\n    else:\n        return False\n    weights = [9, 8, 7, 6, 5, 4, 3, 2]\n    total = sum(p * w for p, w in zip(prefix + digits, weights))\n    remainder = total % 11\n    expected = "0" if remainder == 0 else "A" if remainder == 1 else str(11 - remainder)\n    return check == expected',
             "python", "validation", json.dumps(["hkid", "identity", "validation", "hong-kong"]), 24),
            (2, "HK Phone Formatter", "Format and validate Hong Kong phone numbers",
             'def format_hk_phone(phone: str) -> str:\n    """Format HK phone number with country code."""\n    digits = "".join(c for c in phone if c.isdigit())\n    if digits.startswith("852"):\n        digits = digits[3:]\n    if len(digits) != 8:\n        raise ValueError("HK phone numbers must be 8 digits")\n    if digits[0] not in "5679":\n        raise ValueError("HK mobile numbers start with 5, 6, 7, or 9")\n    return f"+852 {digits[:4]} {digits[4:]}"',
             "python", "formatting", json.dumps(["phone", "hk", "formatting", "mobile"]), 18),
            (3, "FPS QR Code Generation", "Generate HKMA-standard FPS QR code for payments",
             'import qrcode\n\ndef generate_fps_qr(proxy_id: str, amount: float, currency: str = "HKD") -> bytes:\n    """Generate FPS EMV QR code."""\n    payload = f"0002010102110226000000{proxy_id}5204000053033445802HK5407{amount:.2f}6304"\n    qr = qrcode.make(payload)\n    from io import BytesIO\n    buf = BytesIO()\n    qr.save(buf, format="PNG")\n    return buf.getvalue()',
             "python", "payment", json.dumps(["fps", "qr", "payment", "hkma"]), 15),
            (4, "GovHK Weather API", "Fetch current weather from HK Observatory",
             'import httpx\n\nasync def get_hk_weather() -> dict:\n    """Fetch current weather from HK Observatory API."""\n    url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"\n    params = {"dataType": "rhrread", "lang": "en"}\n    async with httpx.AsyncClient() as client:\n        resp = await client.get(url, params=params)\n        resp.raise_for_status()\n        return resp.json()',
             "python", "api", json.dumps(["weather", "govhk", "observatory", "api"]), 12),
            (5, "HK Address Parser", "Parse Hong Kong addresses into structured components",
             'import re\n\ndef parse_hk_address(address: str) -> dict:\n    """Parse HK address into components."""\n    result = {"territory": "", "district": "", "building": "", "floor": "", "unit": ""}\n    floor_match = re.search(r"(\\d+)[/F]|Floor\\s*(\\d+)", address, re.IGNORECASE)\n    if floor_match:\n        result["floor"] = floor_match.group(1) or floor_match.group(2)\n    unit_match = re.search(r"Unit\\s*([A-Z0-9]+)", address, re.IGNORECASE)\n    if unit_match:\n        result["unit"] = unit_match.group(1)\n    return result',
             "python", "utility", json.dumps(["address", "parser", "hk", "formatting"]), 8),
        ],
    )
    db.executemany(
        "INSERT OR IGNORE INTO api_configs (id, service_name, base_url, auth_type, active) VALUES (?,?,?,?,?)",
        [
            (1, "govhk_weather", "https://data.weather.gov.hk/weatherAPI/opendata/", "none", True),
            (2, "govhk_transport", "https://data.gov.hk/api/3/", "none", True),
            (3, "fps", "https://api.fps.hkma.gov.hk/", "bearer", False),
            (4, "octopus", "https://api.octopus.com.hk/merchant/", "api_key", False),
        ],
    )
    db.commit()
    db.close()
