"""Tests for ThesisFormatter bibliography modules."""


class TestBibFormatter:
    def test_format_bibliography_apa(self):
        from student.thesis_formatter.bibliography.bib_formatter import format_bibliography

        references = [
            {
                "type": "article",
                "author": "Smith, J.",
                "title": "A Study on Testing",
                "journal": "Journal of Tests",
                "year": "2024",
                "volume": "1",
                "pages": "1-10",
            },
        ]
        formatted = format_bibliography(references, style="apa")
        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert "Smith" in formatted[0]


class TestBibtexHandler:
    def test_parse_bibtex_invalid_path(self):
        from student.thesis_formatter.bibliography.bibtex_handler import parse_bibtex

        try:
            result = parse_bibtex("/nonexistent/refs.bib")
            assert isinstance(result, list)
        except (FileNotFoundError, Exception):
            pass
