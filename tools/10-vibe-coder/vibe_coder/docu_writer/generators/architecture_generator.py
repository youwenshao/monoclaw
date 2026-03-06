"""Generate an architecture overview document from project analysis."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from vibe_coder.docu_writer.analyzers.python_parser import CodeElement
from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectInfo

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


class ArchitectureGenerator:
    """Produce a high-level architecture document for a project."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            keep_trailing_newline=True,
        )

    async def generate(
        self,
        project_info: ProjectInfo,
        code_elements: list[CodeElement],
        llm,
    ) -> str:
        directory_tree = self._build_tree(project_info)
        modules = self._identify_modules(code_elements)
        overview = await self._llm_overview(project_info, modules, llm)
        component_descriptions = await self._llm_components(modules, llm)

        template = self._env.get_template("architecture.md.j2")
        return template.render(
            project_name=project_info.project_name,
            overview=overview,
            directory_tree=directory_tree,
            modules=modules,
            component_descriptions=component_descriptions,
            primary_language=project_info.primary_language,
            file_count=project_info.file_count,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _build_tree(info: ProjectInfo) -> str:
        lines: list[str] = [f"{info.project_name}/"]
        dirs_seen: set[str] = set()
        for f in sorted(info.files, key=lambda x: x.path):
            parts = Path(f.path).parts
            for depth in range(len(parts) - 1):
                dir_path = "/".join(parts[: depth + 1])
                if dir_path not in dirs_seen:
                    dirs_seen.add(dir_path)
                    indent = "  " * (depth + 1)
                    lines.append(f"{indent}{parts[depth]}/")
            indent = "  " * len(parts)
            lines.append(f"{indent}{parts[-1]}")
        return "\n".join(lines)

    @staticmethod
    def _identify_modules(elements: list[CodeElement]) -> dict[str, list[CodeElement]]:
        modules: dict[str, list[CodeElement]] = {}
        for elem in elements:
            fp = elem.file_path
            top_dir = Path(fp).parts[0] if Path(fp).parts else "root"
            modules.setdefault(top_dir, []).append(elem)
        return dict(sorted(modules.items()))

    async def _llm_overview(
        self,
        info: ProjectInfo,
        modules: dict[str, list[CodeElement]],
        llm,
    ) -> str:
        module_summary = "\n".join(
            f"  - {name}: {len(elems)} elements"
            for name, elems in modules.items()
        )
        prompt = (
            f"Write a concise architecture overview (3-5 sentences) for '{info.project_name}'.\n"
            f"Primary language: {info.primary_language}, {info.file_count} files.\n"
            f"Modules:\n{module_summary}\n"
            f"Describe the high-level design, patterns, and how components interact."
        )
        return await llm.complete(prompt)

    async def _llm_components(
        self,
        modules: dict[str, list[CodeElement]],
        llm,
    ) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        for mod_name, elems in modules.items():
            elem_list = "\n".join(
                f"  - {e.element_type}: {e.element_name} — {e.signature}"
                for e in elems[:15]
            )
            prompt = (
                f"Describe the '{mod_name}' module in 2-3 sentences.\n"
                f"It contains:\n{elem_list}"
            )
            descriptions[mod_name] = await llm.complete(prompt)
        return descriptions
