"""Generate docstrings for undocumented functions and methods."""

from __future__ import annotations

from dataclasses import dataclass

from vibe_coder.docu_writer.analyzers.python_parser import CodeElement


@dataclass
class GeneratedDocstring:
    file_path: str
    element_name: str
    line_number: int
    original_signature: str
    docstring: str
    style: str = "google"


class DocstringGenerator:
    """Produce docstrings for code elements that lack documentation."""

    BATCH_SIZE = 10

    async def generate(
        self,
        code_elements: list[CodeElement],
        llm,
        *,
        style: str = "google",
    ) -> list[GeneratedDocstring]:
        undocumented = [
            e for e in code_elements
            if e.element_type in ("function", "method") and not e.has_docstring
        ]
        if not undocumented:
            return []

        results: list[GeneratedDocstring] = []
        for batch_start in range(0, len(undocumented), self.BATCH_SIZE):
            batch = undocumented[batch_start : batch_start + self.BATCH_SIZE]
            generated = await self._generate_batch(batch, llm, style)
            results.extend(generated)

        return results

    async def _generate_batch(
        self,
        elements: list[CodeElement],
        llm,
        style: str,
    ) -> list[GeneratedDocstring]:
        listing = "\n\n".join(
            f"### {i+1}. `{e.element_name}` in `{e.file_path}` (line {e.line_number})\n"
            f"Signature: `{e.signature}`\n"
            f"Parameters: {', '.join(e.parameters) if e.parameters else 'none'}\n"
            f"Returns: {e.return_annotation or 'unknown'}"
            for i, e in enumerate(elements)
        )
        prompt = (
            f"Generate {style}-style docstrings for each function below.\n"
            f"Format your response as numbered items matching the input.\n"
            f"Each docstring should include a summary line, Args (if any), and Returns.\n"
            f"Wrap each docstring in triple quotes.\n\n"
            f"{listing}"
        )
        raw = await llm.complete(prompt)
        return self._parse_response(raw, elements, style)

    @staticmethod
    def _parse_response(
        raw: str,
        elements: list[CodeElement],
        style: str,
    ) -> list[GeneratedDocstring]:
        results: list[GeneratedDocstring] = []
        blocks = raw.split('"""')

        docstrings: list[str] = []
        for i in range(1, len(blocks), 2):
            docstrings.append(blocks[i].strip())

        for elem, doc in zip(elements, docstrings):
            results.append(
                GeneratedDocstring(
                    file_path=elem.file_path,
                    element_name=elem.element_name,
                    line_number=elem.line_number,
                    original_signature=elem.signature,
                    docstring=doc,
                    style=style,
                )
            )
        return results
