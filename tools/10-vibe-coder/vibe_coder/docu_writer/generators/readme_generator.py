"""Generate a README.md from project analysis results using LLM + Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectInfo

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


class ReadmeGenerator:
    """Produce a polished README.md for a project."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            keep_trailing_newline=True,
        )

    async def generate(self, project_info: ProjectInfo, llm) -> str:
        summary = await self._get_llm_summary(project_info, llm)
        install_instructions = await self._get_install_instructions(project_info, llm)
        usage_example = await self._get_usage_example(project_info, llm)

        template = self._env.get_template("readme.md.j2")
        return template.render(
            project_name=project_info.project_name,
            summary=summary,
            primary_language=project_info.primary_language,
            file_count=project_info.file_count,
            total_functions=project_info.total_functions,
            documented_functions=project_info.documented_functions,
            documentation_coverage=project_info.documentation_coverage,
            language_breakdown=project_info.language_breakdown,
            install_instructions=install_instructions,
            usage_example=usage_example,
            files=project_info.files,
        )

    async def _get_llm_summary(self, info: ProjectInfo, llm) -> str:
        file_listing = "\n".join(f"  - {f.path} ({f.language})" for f in info.files[:30])
        funcs = "\n".join(
            f"  - {e.element_name} ({e.element_type})"
            for e in info.code_elements[:20]
        )
        prompt = (
            f"Write a concise 2-3 sentence project summary for '{info.project_name}'.\n"
            f"Primary language: {info.primary_language}\n"
            f"Key files:\n{file_listing}\n"
            f"Key functions/classes:\n{funcs}\n"
            f"Respond with ONLY the summary text, no markdown headers."
        )
        return await llm.complete(prompt)

    async def _get_install_instructions(self, info: ProjectInfo, llm) -> str:
        prompt = (
            f"Write brief installation instructions for a {info.primary_language} project "
            f"named '{info.project_name}'. Include package manager commands as appropriate. "
            f"Use markdown code blocks. Keep it under 10 lines."
        )
        return await llm.complete(prompt)

    async def _get_usage_example(self, info: ProjectInfo, llm) -> str:
        top_funcs = [
            e for e in info.code_elements
            if e.element_type in ("function", "class")
        ][:5]
        sigs = "\n".join(f"  - {e.signature}" for e in top_funcs)
        prompt = (
            f"Write a short usage example for the {info.primary_language} project "
            f"'{info.project_name}' using these public APIs:\n{sigs}\n"
            f"Use a single markdown code block. Keep it under 15 lines."
        )
        return await llm.complete(prompt)
