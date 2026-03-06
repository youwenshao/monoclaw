"""Course hierarchy and topic organization."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import get_db


def get_course_tree(db_path: str | Path) -> list[dict]:
    with get_db(db_path) as conn:
        courses = [dict(r) for r in conn.execute(
            "SELECT * FROM courses ORDER BY semester DESC, course_code"
        ).fetchall()]

        tree: dict[str, list[dict]] = {}
        for course in courses:
            semester = course.get("semester") or "Unknown"
            doc_count = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE course_id = ?",
                (course["id"],),
            ).fetchone()[0]
            course["document_count"] = doc_count
            tree.setdefault(semester, []).append(course)

    return [
        {"semester": sem, "courses": crs}
        for sem, crs in tree.items()
    ]


def get_course_topics(db_path: str | Path, course_id: int) -> list[str]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT c.section_title
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               WHERE d.course_id = ? AND c.section_title != ''
               ORDER BY c.section_title""",
            (course_id,),
        ).fetchall()
    return [r[0] for r in rows]
