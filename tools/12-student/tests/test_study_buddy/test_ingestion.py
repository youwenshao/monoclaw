"""Tests for StudyBuddy document ingestion."""

import tempfile
from pathlib import Path

import pytest


class TestChunker:
    def test_chunk_text_splits_long_content(self):
        from student.study_buddy.ingestion.chunker import chunk_text

        pages = [
            {"page_number": 1, "text": "word " * 1000, "section_title": "Chapter 1"},
        ]
        chunks = chunk_text(pages, chunk_size=500)
        assert len(chunks) > 1
        for c in chunks:
            assert "chunk_index" in c
            assert "text" in c
            assert "page_number" in c

    def test_chunk_text_preserves_short_content(self):
        from student.study_buddy.ingestion.chunker import chunk_text

        pages = [
            {"page_number": 1, "text": "Short content.", "section_title": "Intro"},
        ]
        chunks = chunk_text(pages, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0]["text"].strip() == "Short content."

    def test_chunk_text_handles_empty_pages(self):
        from student.study_buddy.ingestion.chunker import chunk_text

        pages = [{"page_number": 1, "text": "", "section_title": ""}]
        chunks = chunk_text(pages, chunk_size=500)
        assert len(chunks) == 0 or chunks[0]["text"].strip() == ""


class TestPdfParser:
    def test_parse_pdf_invalid_path(self):
        from student.study_buddy.ingestion.pdf_parser import parse_pdf

        with pytest.raises(Exception):
            parse_pdf("/nonexistent/file.pdf")


class TestDocxParser:
    def test_parse_docx_invalid_path(self):
        from student.study_buddy.ingestion.docx_parser import parse_docx

        with pytest.raises(Exception):
            parse_docx("/nonexistent/file.docx")
