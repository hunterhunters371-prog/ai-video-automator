"""SCRIPT: guion optimizado para contenido corto.

Entrada: research.md.
Salida:  script.json — 5 hooks (se selecciona el más fuerte), narración
         preparada para TTS, beats con duración máxima, CTA solo si aporta.
"""
from __future__ import annotations

import json

from .. import config, llm
from ..state import Project, Stage
from .base import BaseStage, StageError


class ScriptStage(BaseStage):
    stage = Stage.SCRIPT

    def run(self, project: Project) -> dict:
        out = project.path / "script.json"
        if out.exists():
            return {"script": "script.json"}  # idempotente

        template_name = project.data.get("template") or config.PIPELINE["defaults"]["template"]
        template = config.load_template(template_name)
        structure = "\n".join(
            f"- {beat['role']}: máx {beat['max_s']} s" for beat in template["structure"]
        )
        duration = project.data.get("duration_target_s") or 30
        research = (project.path / "research.md").read_text(encoding="utf-8")
        hook_options = config.PIPELINE["stages"]["script"].get("hook_options", 5)

        data = llm.complete_json(
            f"""Investigación:
{research}

Escribe el guion de un Short vertical de ~{duration} s en español.
Estructura de beats (respeta los máximos):
{structure}

Reglas:
- Genera {hook_options} hooks (1-3 s cada uno) y selecciona el más fuerte; justifica en una línea.
- Sin introducciones largas. Desarrollo rápido. Un elemento de sorpresa/curiosidad.
- CTA solo si aporta; si no, cierre limpio.
- Narración escrita para TTS natural: frases cortas, números en letra, siglas espaciadas.

Devuelve JSON exacto:
{{"hooks": ["..."], "selected_hook": 0, "hook_reason": "...",
 "narration": "texto completo de la narración",
 "beats": [{{"role": "hook", "text": "...", "max_s": 3}}],
 "cta_included": false}}""",
            system="Eres guionista de Shorts virales. Respondes solo JSON.",
        )

        hooks = data.get("hooks") or []
        if not hooks or not data.get("narration") or not data.get("beats"):
            raise StageError("script.json incompleto: faltan hooks, narration o beats")
        data["selected_hook"] = max(0, min(int(data.get("selected_hook", 0)), len(hooks) - 1))
        data["prompt_used"] = f"script/{template_name}/{duration}s"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"script": "script.json"}
