"""Python source parser using the ``ast`` module."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CodeElement:
    """A single documentable element extracted from source code."""

    element_type: str  # "function", "class", "method", "module"
    element_name: str
    signature: str
    has_docstring: bool
    docstring: str | None
    line_number: int
    file_path: str = ""
    parameters: list[str] = field(default_factory=list)
    return_annotation: str | None = None
    decorators: list[str] = field(default_factory=list)


class PythonParser:
    """Extract functions, classes, methods, and their signatures from Python files."""

    ENCODINGS = ("utf-8", "latin-1")

    def parse(self, file_path: str | Path) -> list[CodeElement]:
        file_path = Path(file_path)
        source = self._read_source(file_path)
        if source is None:
            return []

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return []

        elements: list[CodeElement] = []
        self._walk(tree, file_path, elements)
        return elements

    # ------------------------------------------------------------------

    def _read_source(self, path: Path) -> str | None:
        for enc in self.ENCODINGS:
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, OSError):
                continue
        return None

    def _walk(
        self,
        node: ast.AST,
        file_path: Path,
        elements: list[CodeElement],
        *,
        parent_class: str | None = None,
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                elem_type = "method" if parent_class else "function"
                name = f"{parent_class}.{child.name}" if parent_class else child.name
                elements.append(self._func_element(child, file_path, elem_type, name))

            elif isinstance(child, ast.ClassDef):
                docstring = ast.get_docstring(child)
                elements.append(
                    CodeElement(
                        element_type="class",
                        element_name=child.name,
                        signature=f"class {child.name}",
                        has_docstring=docstring is not None,
                        docstring=docstring,
                        line_number=child.lineno,
                        file_path=str(file_path),
                        decorators=[self._decorator_name(d) for d in child.decorator_list],
                    )
                )
                self._walk(child, file_path, elements, parent_class=child.name)
                continue  # children already processed

            self._walk(child, file_path, elements, parent_class=parent_class)

    def _func_element(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        elem_type: str,
        qualified_name: str,
    ) -> CodeElement:
        params = self._format_params(node.args)
        ret = self._format_annotation(node.returns) if node.returns else None
        sig_parts = [
            "async " if isinstance(node, ast.AsyncFunctionDef) else "",
            f"def {qualified_name}({', '.join(params)})",
        ]
        if ret:
            sig_parts.append(f" -> {ret}")
        signature = "".join(sig_parts)

        docstring = ast.get_docstring(node)
        return CodeElement(
            element_type=elem_type,
            element_name=qualified_name,
            signature=signature,
            has_docstring=docstring is not None,
            docstring=docstring,
            line_number=node.lineno,
            file_path=str(file_path),
            parameters=params,
            return_annotation=ret,
            decorators=[self._decorator_name(d) for d in node.decorator_list],
        )

    # ------------------------------------------------------------------
    # AST helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_params(args: ast.arguments) -> list[str]:
        params: list[str] = []
        defaults_offset = len(args.args) - len(args.defaults)

        for i, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue
            ann = PythonParser._format_annotation(arg.annotation) if arg.annotation else None
            part = f"{arg.arg}: {ann}" if ann else arg.arg
            di = i - defaults_offset
            if di >= 0 and args.defaults[di] is not None:
                part += f" = ..."
            params.append(part)

        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        for kw in args.kwonlyargs:
            ann = PythonParser._format_annotation(kw.annotation) if kw.annotation else None
            params.append(f"{kw.arg}: {ann}" if ann else kw.arg)
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")

        return params

    @staticmethod
    def _format_annotation(node: ast.expr | None) -> str:
        if node is None:
            return ""
        return ast.unparse(node)

    @staticmethod
    def _decorator_name(node: ast.expr) -> str:
        return ast.unparse(node)
