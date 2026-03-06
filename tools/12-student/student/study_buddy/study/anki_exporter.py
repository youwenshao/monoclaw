"""Export flashcards as Anki .apkg deck using genanki."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import genanki

from openclaw_shared.database import get_db


def _stable_id(name: str) -> int:
    h = hashlib.md5(name.encode()).hexdigest()  # noqa: S324
    return int(h[:8], 16)


STUDY_BUDDY_MODEL = genanki.Model(
    _stable_id("StudyBuddy-Flashcard-Model"),
    "StudyBuddy Flashcard",
    fields=[
        {"name": "Question"},
        {"name": "Answer"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Question}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Answer}}',
        },
    ],
)


def export_deck(course_id: int, db_path: str | Path) -> bytes:
    with get_db(db_path) as conn:
        course = conn.execute(
            "SELECT course_code, course_name FROM courses WHERE id = ?",
            (course_id,),
        ).fetchone()
        flashcards = [dict(r) for r in conn.execute(
            "SELECT question, answer FROM flashcards WHERE course_id = ?",
            (course_id,),
        ).fetchall()]

    course_name = f"{course[0]} - {course[1]}" if course else f"Course {course_id}"
    deck = genanki.Deck(_stable_id(course_name), course_name)

    for card in flashcards:
        note = genanki.Note(
            model=STUDY_BUDDY_MODEL,
            fields=[card["question"], card["answer"]],
        )
        deck.add_note(note)

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".apkg", delete=False) as tmp:
        genanki.Package(deck).write_to_file(tmp.name)
        return Path(tmp.name).read_bytes()
