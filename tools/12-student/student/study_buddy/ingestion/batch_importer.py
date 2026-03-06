"""Batch import documents from a folder into a course."""

from __future__ import annotations

from pathlib import Path

from openclaw_shared.database import get_db

from student.study_buddy.ingestion.chunker import chunk_text
from student.study_buddy.ingestion.docx_parser import parse_docx
from student.study_buddy.ingestion.pdf_parser import parse_pdf
from student.study_buddy.ingestion.pptx_parser import parse_pptx

PARSERS = {
    ".pdf": ("pdf", parse_pdf),
    ".pptx": ("pptx", parse_pptx),
    ".docx": ("docx", parse_docx),
}


def import_folder(folder_path: str, course_id: int, db_path: str | Path) -> list[int]:
    folder = Path(folder_path)
    if not folder.is_dir():
        return []

    doc_ids: list[int] = []

    for file in sorted(folder.iterdir()):
        ext = file.suffix.lower()
        if ext not in PARSERS:
            continue

        doc_type, parser_fn = PARSERS[ext]
        pages = parser_fn(str(file))
        chunks = chunk_text(pages)

        with get_db(db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO documents
                   (course_id, filename, file_path, doc_type, title, page_count, chunk_count, indexed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    course_id,
                    file.name,
                    str(file),
                    doc_type,
                    file.stem,
                    len(pages),
                    len(chunks),
                    False,
                ),
            )
            doc_id = cursor.lastrowid

            for chunk in chunks:
                conn.execute(
                    """INSERT INTO chunks
                       (document_id, chunk_index, text_content, page_number, section_title)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        doc_id,
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk["page_number"],
                        chunk["section_title"],
                    ),
                )

        doc_ids.append(doc_id)

    return doc_ids
