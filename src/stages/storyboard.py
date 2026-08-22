"""STORYBOARD: convierte el guion en segmentos temporales.

Entrada: script.json + plantilla.
Salida:  storyboard.json — por segmento: t ("MM:SS-MM:SS"), role, narration,
         on_screen_text, asset (type + prompt/src), animation, transition_in,
         sfx. Este JSON es la única fuente de verdad de la edición
         (formato: projects/_ejemplo/storyboard.json). Lleva `template` para
         que EDITING/ASSETS carguen la plantilla correcta.
"""
from __future__ import annotations

import json

from .. import config, llm
from ..state import Project, Stage
from .base import BaseStage, StageError


def parse_t(t) -> tuple[float, float]:
    """Acepta "MM:SS-MM:SS" o [inicio, fin] y devuelve segundos."""
    if isinstance(t, (list, tuple)):
        return float(t[0]), float(t[1])
    a, b = str(t).split("-")
    return _hms(a), _hms(b)


def _hms(s: str) -> float:
    parts = [float(p) for p in s.strip().split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]


class StoryboardStage(BaseStage):
    stage = Stage.STORYBOARD

    def run(self, project: Project) -> dict:
        out = project.path / "storyboard.json"
        if out.exists():
            return {"storyboard": "storyboard.json"}  # idempotente

        template_name = project.data.get("template") or config.PIPELINE["defaults"]["template"]
        template = config.load_template(template_name)
        script = json.loads((project.path / "script.json").read_text(encoding="utf-8"))
        duration = project.data.get("duration_target_s") or template.get("duration_target_s", 30)
        preferred = template.get("preferred_assets", [])
        transitions = template.get("transitions", {})
        sfx = template.get("sfx", [])

        data = llm.complete_json(
            f"""Guion:
{json.dumps(script, ensure_ascii=False)}

Convierte los beats en un storyboard de ~{duration} s para video vertical 9:16.
- Un segmento por beat (dos si el beat es denso). Ritmo: corte visual cada 2-4 s.
- "t" es "MM:SS-MM:SS"; sin huecos ni solapes; el primero empieza en 00:00.
- asset.type prioriza, en orden: {preferred}. asset.prompt describe la escena
  para buscarla o generarla (concreto: qué se ve, no adjetivos).
- animation: ken_burns_in | ken_burns_out | static.
- transition_in: uno de {transitions}. sfx: uno de {sfx} o null.
- on_screen_text: máx 5 palabras, keywords en MAYÚSCULAS.

Devuelve JSON: {{"segments": [{{"t": "00:00-00:03", "role": "hook",
 "narration": "...", "on_screen_text": "...",
 "asset": {{"type": "gameplay", "prompt": "..."}},
 "animation": "ken_burns_in", "transition_in": "zoom_punch",
 "sfx": "whoosh"}}]}}""",
            system="Eres editor de Shorts. Respondes solo JSON.",
        )

        segments = data.get("segments")
        if not segments:
            raise StageError("storyboard sin segmentos")
        _validate_times(segments, duration)
        data["template"] = template_name  # EDITING/ASSETS cargan ESTA plantilla
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"storyboard": "storyboard.json"}


def _validate_times(segments: list[dict], duration: int) -> None:
    t = 0.0
    for seg in segments:
        start, end = parse_t(seg["t"])
        if start > t + 0.5 or end <= start:
            raise StageError(
                f"storyboard: tiempos inválidos en segmento {seg.get('role')} ({seg['t']})"
            )
        t = end
    if t > duration + 3:
        raise StageError(f"storyboard: {t:.0f}s supera el objetivo de {duration}s")
