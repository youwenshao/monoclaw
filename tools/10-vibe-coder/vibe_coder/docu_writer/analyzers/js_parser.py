"""JavaScript / TypeScript parser using regex-based extraction.

Falls back to regex patterns since tree-sitter may not be available in all
environments.  Covers function declarations, arrow functions, class
declarations, and named exports.
"""

from __future__ import annotations

import re
from pathlib import Path

from vibe_coder.docu_writer.analyzers.python_parser import CodeElement

# ---------------------------------------------------------------------------
# Regex patterns for common JS/TS constructs
# ---------------------------------------------------------------------------

_FUNC_DECL = re.compile(
    r"^(?P<export>export\s+(?:default\s+)?)?(?P<async>async\s+)?"
    r"function\s+(?P<name>\w+)\s*(?:<[^>]*>)?\s*\((?P<params>[^)]*)\)"
    r"(?:\s*:\s*(?P<ret>[^\s{]+))?\s*\{",
    re.MULTILINE,
)

_ARROW_CONST = re.compile(
    r"^(?P<export>export\s+(?:default\s+)?)?(?:const|let|var)\s+(?P<name>\w+)"
    r"(?:\s*:\s*[^=]+?)?\s*=\s*(?P<async>async\s+)?"
    r"(?:\([^)]*\)|(?P<single_param>\w+))\s*(?::\s*(?P<ret>[^\s=>{]+))?\s*=>",
    re.MULTILINE,
)

_CLASS_DECL = re.compile(
    r"^(?P<export>export\s+(?:default\s+)?)?class\s+(?P<name>\w+)"
    r"(?:\s+extends\s+(?P<base>\w+))?"
    r"(?:\s+implements\s+(?P<ifaces>[^{]+))?\s*\{",
    re.MULTILINE,
)

_METHOD_DECL = re.compile(
    r"^\s+(?P<access>public|private|protected|static|readonly|\s)*"
    r"(?P<async>async\s+)?(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
    r"(?:\s*:\s*(?P<ret>[^\s{]+))?\s*\{",
    re.MULTILINE,
)

_JSDOC_BLOCK = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)


class JSParser:
    """Extract code elements from JavaScript and TypeScript files."""

    SUPPORTED_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}

    def parse(self, file_path: str | Path) -> list[CodeElement]:
        file_path = Path(file_path)
        if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        lines = source.split("\n")
        jsdoc_map = self._build_jsdoc_map(source, lines)
        elements: list[CodeElement] = []

        self._extract_functions(source, lines, file_path, jsdoc_map, elements)
        self._extract_arrows(source, lines, file_path, jsdoc_map, elements)
        self._extract_classes(source, lines, file_path, jsdoc_map, elements)
        self._extract_methods(source, lines, file_path, jsdoc_map, elements)

        elements.sort(key=lambda e: e.line_number)
        return elements

    # ------------------------------------------------------------------
    # Internal extractors
    # ------------------------------------------------------------------

    def _extract_functions(
        self,
        source: str,
        lines: list[str],
        fp: Path,
        jsdoc_map: dict[int, str],
        out: list[CodeElement],
    ) -> None:
        for m in _FUNC_DECL.finditer(source):
            lineno = source[: m.start()].count("\n") + 1
            doc = jsdoc_map.get(lineno)
            prefix = "async " if m.group("async") else ""
            sig = f"{prefix}function {m.group('name')}({m.group('params').strip()})"
            if m.group("ret"):
                sig += f": {m.group('ret')}"
            out.append(
                CodeElement(
                    element_type="function",
                    element_name=m.group("name"),
                    signature=sig,
                    has_docstring=doc is not None,
                    docstring=doc,
                    line_number=lineno,
                    file_path=str(fp),
                    parameters=[p.strip() for p in m.group("params").split(",") if p.strip()],
                    return_annotation=m.group("ret"),
                )
            )

    def _extract_arrows(
        self,
        source: str,
        lines: list[str],
        fp: Path,
        jsdoc_map: dict[int, str],
        out: list[CodeElement],
    ) -> None:
        for m in _ARROW_CONST.finditer(source):
            lineno = source[: m.start()].count("\n") + 1
            doc = jsdoc_map.get(lineno)
            prefix = "async " if m.group("async") else ""
            name = m.group("name")
            params_text = m.group("single_param") or ""
            sig = f"const {name} = {prefix}({params_text}) =>"
            if m.group("ret"):
                sig += f": {m.group('ret')}"
            out.append(
                CodeElement(
                    element_type="function",
                    element_name=name,
                    signature=sig,
                    has_docstring=doc is not None,
                    docstring=doc,
                    line_number=lineno,
                    file_path=str(fp),
                    return_annotation=m.group("ret"),
                )
            )

    def _extract_classes(
        self,
        source: str,
        lines: list[str],
        fp: Path,
        jsdoc_map: dict[int, str],
        out: list[CodeElement],
    ) -> None:
        for m in _CLASS_DECL.finditer(source):
            lineno = source[: m.start()].count("\n") + 1
            doc = jsdoc_map.get(lineno)
            sig = f"class {m.group('name')}"
            if m.group("base"):
                sig += f" extends {m.group('base')}"
            out.append(
                CodeElement(
                    element_type="class",
                    element_name=m.group("name"),
                    signature=sig,
                    has_docstring=doc is not None,
                    docstring=doc,
                    line_number=lineno,
                    file_path=str(fp),
                )
            )

    def _extract_methods(
        self,
        source: str,
        lines: list[str],
        fp: Path,
        jsdoc_map: dict[int, str],
        out: list[CodeElement],
    ) -> None:
        for m in _METHOD_DECL.finditer(source):
            name = m.group("name")
            if name in ("if", "for", "while", "switch", "catch"):
                continue
            lineno = source[: m.start()].count("\n") + 1
            doc = jsdoc_map.get(lineno)
            prefix = "async " if m.group("async") else ""
            sig = f"{prefix}{name}({m.group('params').strip()})"
            if m.group("ret"):
                sig += f": {m.group('ret')}"
            out.append(
                CodeElement(
                    element_type="method",
                    element_name=name,
                    signature=sig,
                    has_docstring=doc is not None,
                    docstring=doc,
                    line_number=lineno,
                    file_path=str(fp),
                    parameters=[p.strip() for p in m.group("params").split(",") if p.strip()],
                    return_annotation=m.group("ret"),
                )
            )

    # ------------------------------------------------------------------
    # JSDoc helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build_jsdoc_map(source: str, lines: list[str]) -> dict[int, str]:
        """Map line numbers to their preceding JSDoc comment text.

        Returns a dict mapping the line number *after* a JSDoc block to the
        cleaned doc text.
        """
        mapping: dict[int, str] = {}
        for m in _JSDOC_BLOCK.finditer(source):
            end_line = source[: m.end()].count("\n") + 1
            target_line = end_line + 1
            raw = m.group(1)
            cleaned = re.sub(r"^\s*\*\s?", "", raw, flags=re.MULTILINE).strip()
            mapping[target_line] = cleaned
        return mapping
