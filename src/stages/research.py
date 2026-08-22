"""RESEARCH: investiga la idea y selecciona el formato.

Entrada: idea del proyecto.
Salida:  research.md (fuentes + datos clave), plantilla y duración elegidas.
"""
from __future__ import annotations

from .. import config, llm, websearch
from ..state import Project, Stage
from .base import BaseStage, StageError


def _load_templates() -> dict:
    """Carga todas las plantillas. Una rota se reporta y se salta:
    el pipeline no puede morir por una plantilla que ni siquiera se eligió."""
    templates = {}
    for name in config.list_templates():
        try:
            templates[name] = config.load_template(name)
        except Exception as exc:
            print(f"[research] plantilla {name!r} ignorada (YAML inválido): {exc}")
    if not templates:
        raise StageError("ninguna plantilla válida en templates/")
    return templates


class ResearchStage(BaseStage):
    stage = Stage.RESEARCH

    def run(self, project: Project) -> dict:
        out = project.path / "research.md"
        if out.exists() and project.data.get("template"):
            return {"research": "research.md"}  # idempotente

        idea = project.data["idea"]["text"]
        results = websearch.search(idea, max_results=5)

        templates = _load_templates()
        options = "\n".join(
            f"- {name}: {tpl.get('description', '')} "
            f"(duración objetivo {tpl.get('duration_target_s', 30)} s)"
            for name, tpl in templates.items()
        )
        sources_plain = "\n".join(
            f"{r['title']} — {r['url']} — {r['snippet']}" for r in results
        ) or "(sin resultados web; usa tu conocimiento y márcalo como no verificado)"

        choice = llm.complete_json(
            f"""Idea para video corto: {idea}

Fuentes encontradas:
{sources_plain}

Plantillas disponibles:
{options}

Elige plantilla y duración objetivo (15/30/45/60) según la densidad de información.
Extrae 3-5 datos clave que el guion debe incluir (con cifras y fechas si hay).
Devuelve JSON: {{"template": "...", "duration_s": 30,
 "key_facts": ["...", "..."], "angle": "enfoque del video en una línea"}}""",
            system="Eres el director de un canal de Shorts. Respondes solo JSON.",
        )

        template = choice.get("template")
        if template not in templates:
            template = config.PIPELINE["defaults"]["template"]
        duration = int(choice.get("duration_s") or 30)

        project.data["template"] = project.data.get("template") or template
        project.data["duration_target_s"] = project.data.get("duration_target_s") or duration
        project.data["key_facts"] = choice.get("key_facts", [])
        project.data["angle"] = choice.get("angle", "")

        lines = [f"# Research — {idea}\n"]
        lines.append(f"\n## Enfoque\n{choice.get('angle', '')}\n")
        lines.append("\n## Datos clave\n")
        lines += [f"- {fact}" for fact in choice.get("key_facts", [])]
        lines.append("\n## Fuentes\n")
        if results:
            lines += [f"- [{r['title']}]({r['url']}) — {r['snippet']}" for r in results]
        else:
            lines.append("(sin resultados web — datos marcados como no verificados)")
        out.write_text("\n".join(lines), encoding="utf-8")
        project.save()
        return {"research": "research.md"}
