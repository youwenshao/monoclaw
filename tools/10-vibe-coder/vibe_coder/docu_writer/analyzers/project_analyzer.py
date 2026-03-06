"""Walk a project directory tree and collect high-level metrics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from vibe_coder.docu_writer.analyzers.python_parser import CodeElement, PythonParser
from vibe_coder.docu_writer.analyzers.js_parser import JSParser

IGNORED_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "egg-info",
}

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".dart": "dart",
}


@dataclass
class FileInfo:
    path: str
    language: str
    size_bytes: int


@dataclass
class ProjectInfo:
    project_path: str
    project_name: str
    primary_language: str
    file_count: int
    total_functions: int
    documented_functions: int
    documentation_coverage: float
    language_breakdown: dict[str, int] = field(default_factory=dict)
    files: list[FileInfo] = field(default_factory=list)
    code_elements: list[CodeElement] = field(default_factory=list)


class ProjectAnalyzer:
    """Recursively analyze a project directory for documentation metrics."""

    def __init__(self) -> None:
        self._py_parser = PythonParser()
        self._js_parser = JSParser()

    def analyze(self, project_path: str | Path) -> ProjectInfo:
        root = Path(project_path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Project path does not exist: {root}")

        files: list[FileInfo] = []
        lang_counter: Counter[str] = Counter()
        all_elements: list[CodeElement] = []

        for file_path in self._walk(root):
            ext = file_path.suffix.lower()
            lang = LANGUAGE_MAP.get(ext)
            if lang is None:
                continue

            files.append(
                FileInfo(
                    path=str(file_path.relative_to(root)),
                    language=lang,
                    size_bytes=file_path.stat().st_size,
                )
            )
            lang_counter[lang] += 1

            elements = self._parse_file(file_path, lang)
            all_elements.extend(elements)

        primary = lang_counter.most_common(1)[0][0] if lang_counter else "unknown"
        total_funcs = sum(
            1 for e in all_elements if e.element_type in ("function", "method")
        )
        documented = sum(
            1 for e in all_elements
            if e.element_type in ("function", "method") and e.has_docstring
        )
        coverage = documented / total_funcs if total_funcs else 0.0

        return ProjectInfo(
            project_path=str(root),
            project_name=root.name,
            primary_language=primary,
            file_count=len(files),
            total_functions=total_funcs,
            documented_functions=documented,
            documentation_coverage=round(coverage, 4),
            language_breakdown=dict(lang_counter),
            files=files,
            code_elements=all_elements,
        )

    # ------------------------------------------------------------------

    def _walk(self, root: Path):
        """Yield source files, skipping ignored directories."""
        for entry in sorted(root.iterdir()):
            if entry.name.startswith(".") and entry.is_dir():
                continue
            if entry.is_dir():
                if entry.name in IGNORED_DIRS:
                    continue
                yield from self._walk(entry)
            elif entry.is_file() and entry.suffix.lower() in LANGUAGE_MAP:
                yield entry

    def _parse_file(self, path: Path, lang: str) -> list[CodeElement]:
        if lang == "python":
            return self._py_parser.parse(path)
        if lang in ("javascript", "typescript"):
            return self._js_parser.parse(path)
        return []
