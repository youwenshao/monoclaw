"""Generate API reference documentation from extracted code elements."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from vibe_coder.docu_writer.analyzers.python_parser import CodeElement

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


class ApiDocGenerator:
    """Produce an API reference document describing all public code elements."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            keep_trailing_newline=True,
        )

    async def generate(
        self,
        code_elements: list[CodeElement],
        project_name: str,
        llm,
    ) -> str:
        modules = self._group_by_file(code_elements)
        enriched = await self._enrich_descriptions(code_elements, llm)

        template = self._env.get_template("api_doc.md.j2")
        return template.render(
            project_name=project_name,
            modules=modules,
            enriched=enriched,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _group_by_file(elements: list[CodeElement]) -> dict[str, list[CodeElement]]:
        groups: dict[str, list[CodeElement]] = {}
        for elem in elements:
            key = elem.file_path or "unknown"
            groups.setdefault(key, []).append(elem)
        return dict(sorted(groups.items()))

    async def _enrich_descriptions(
        self,
        elements: list[CodeElement],
        llm,
    ) -> dict[str, str]:
        """Ask the LLM for a one-line description of undocumented elements."""
        undocumented = [e for e in elements if not e.has_docstring]
        if not undocumented:
            return {}

        batch = "\n".join(
            f"- {e.element_type} `{e.element_name}`: `{e.signature}`"
            for e in undocumented[:40]
        )
        prompt = (
            "For each code element below, write a concise one-line description.\n"
            "Format: element_name: description\n\n"
            f"{batch}\n\n"
            "Respond with one line per element, nothing else."
        )
        raw = await llm.complete(prompt)

        mapping: dict[str, str] = {}
        for line in raw.strip().splitlines():
            if ":" in line:
                name, _, desc = line.partition(":")
                mapping[name.strip().strip("`")] = desc.strip()
        return mapping
