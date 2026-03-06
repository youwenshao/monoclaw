"""Load and query coding problems from the database."""

from __future__ import annotations

import json
import random
from pathlib import Path

from openclaw_shared.database import get_db


def get_problems(
    db_path: str | Path,
    topic: str | None = None,
    difficulty: str | None = None,
) -> list[dict]:
    clauses = []
    params: list = []
    if topic:
        clauses.append("topic = ?")
        params.append(topic)
    if difficulty:
        clauses.append("difficulty = ?")
        params.append(difficulty)

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_db(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM problems{where} ORDER BY id", params).fetchall()
    return [_deserialize(dict(r)) for r in rows]


def get_problem(db_path: str | Path, problem_id: int) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if not row:
        return {}
    return _deserialize(dict(row))


def get_random_problems(
    db_path: str | Path,
    count: int,
    difficulty: str | None = None,
) -> list[dict]:
    clause = " WHERE difficulty = ?" if difficulty else ""
    params = [difficulty] if difficulty else []
    with get_db(db_path) as conn:
        rows = conn.execute(f"SELECT * FROM problems{clause}", params).fetchall()
    problems = [_deserialize(dict(r)) for r in rows]
    if len(problems) <= count:
        return problems
    return random.sample(problems, count)


def _deserialize(row: dict) -> dict:
    for field in ("hints", "test_cases"):
        val = row.get(field)
        if isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row
