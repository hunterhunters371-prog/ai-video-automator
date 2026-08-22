"""SCRIPT: guion optimizado para contenido corto.

Dos modos según la plantilla (`mode:` en template.yml):
  - carrusel (por defecto): hooks + narración + beats.
  - historia (frutinovelas, M2): personajes con descriptor visual FIJO y voz
    edge-tts asignada + líneas de narrador/diálogo. Además rellena `narration`
    y `beats` para que STORYBOARD y el EDITING actual sigan funcionando
    mientras llega ANIMATE (docs/M2-frutinovelas.md).

Entrada: research.md.
Salida:  script.json.
"""
from __future__ import annotations

import json

from .. import config, llm
from ..state import Project, Stage
from .base import BaseStage, StageError

NARRATOR = "narrador"

# Reparto edge-tts por defecto cuando configs/voice.yml no define
# `character_voices`. El narrador usa la voz principal de voice.yml.
DEFAULT_CHARACTER_VOICES = [
    "es-CO-SalomeNeural",
    "es-MX-JorgeNeural",
    "es-ES-ElviraNeural",
    "es-MX-DaliaNeural",
]


class ScriptStage(BaseStage):
    stage = Stage.SCRIPT

    def run(self, project: Project) -> dict:
        out = project.path / "script.json"
        if out.exists():
            return {"script": "script.json"}  # idempotente

        template_name = project.data.get("template") or config.PIPELINE["defaults"]["template"]
        template = config.load_template(template_name)
        duration = (
            project.data.get("duration_target_s")
            or template.get("duration_target_s", 30)
        )
        research = (project.path / "research.md").read_text(encoding="utf-8")

        if template.get("mode") == "historia":
            data = _historia(research, template, template_name, duration)
        else:
            data = _carrusel(research, template, template_name, duration)

        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"script": "script.json"}


def _carrusel(research: str, template: dict, template_name: str, duration: int) -> dict:
    """Hooks + narración + beats (modo original)."""
    structure = "\n".join(
        f"- {beat['role']}: máx {beat['max_s']} s" for beat in template["structure"]
    )
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
    data["mode"] = "carrusel"
    data["prompt_used"] = f"script/{template_name}/{duration}s"
    return data


def _historia(research: str, template: dict, template_name: str, duration: int) -> dict:
    """Mini historia con narrador + personajes que hablan (frutinovela, M2)."""
    structure = "\n".join(
        f"- {beat['role']}: máx {beat['max_s']} s" for beat in template.get("structure", [])
    )
    max_chars = int(template.get("characters_max", 2))
    pool = config.VOICE.get("character_voices") or DEFAULT_CHARACTER_VOICES

    data = llm.complete_json(
        f"""Investigación:
{research}

Escribe una MINI HISTORIA vertical de ~{duration} s en español, estilo
frutinovela: personajes antropomórficos (frutas, verduras u objetos con cara y
sentimientos exagerados) en un micro drama con planteamiento, conflicto y
remate. Guía de ritmo (orientativa):
{structure}

Reglas:
- Máximo {max_chars} personajes. El NARRADOR conduce la trama entre escenas.
- Cada personaje lleva un "descriptor" visual FIJO y concreto (especie, color,
  cara, elemento distintivo): se repetirá palabra por palabra al generar sus
  imágenes, así que redáctalo bien una sola vez.
- "lineas" mezcla narración y diálogo. Cada línea: "quien" ("narrador" o el
  nombre EXACTO del personaje), "texto" (corto, hablable, números en letra),
  "emocion" (una palabra), "escena" (entero desde 1).
- Réplicas rápidas, drama exagerado, remate claro. Sin CTA.

Devuelve JSON exacto:
{{"titulo": "...",
 "personajes": [{{"nombre": "...", "especie": "...", "descriptor": "..."}}],
 "lineas": [{{"quien": "narrador", "texto": "...", "emocion": "...", "escena": 1}}]}}""",
        system="Eres guionista de frutinovelas virales. Respondes solo JSON.",
    )

    personajes = data.get("personajes") or []
    lineas = data.get("lineas") or []
    if not personajes or not lineas:
        raise StageError("script historia incompleto: faltan personajes o lineas")
    if len(personajes) > max_chars:
        raise StageError(f"script con {len(personajes)} personajes (máx {max_chars})")

    nombres = []
    for i, p in enumerate(personajes):
        nombre = str(p.get("nombre") or "").strip()
        if not nombre:
            raise StageError("personaje sin nombre")
        if not p.get("descriptor"):
            raise StageError(f"personaje {nombre} sin descriptor fijo")
        p["nombre"] = nombre
        p["voz"] = p.get("voz") or pool[i % len(pool)]
        nombres.append(nombre)

    for ln in lineas:
        quien = _resolve_quien(str(ln.get("quien") or ""), nombres)
        if quien is None:
            raise StageError(f"línea con quien desconocido: {ln.get('quien')!r}")
        ln["quien"] = quien
        if not str(ln.get("texto") or "").strip():
            raise StageError("línea sin texto")
        ln["escena"] = int(ln.get("escena") or 1)

    # Compatibilidad con STORYBOARD/EDITING actuales mientras llega ANIMATE:
    # narration = todo el texto en orden; beats = una entrada por escena.
    data["mode"] = "historia"
    data["narration"] = " ".join(str(ln["texto"]).strip() for ln in lineas)
    escenas = sorted({ln["escena"] for ln in lineas})
    per_escena = max(3, duration // max(1, len(escenas)))
    data["beats"] = [
        {
            "role": f"escena_{n}",
            "text": " ".join(
                str(ln["texto"]).strip() for ln in lineas if ln["escena"] == n
            ),
            "max_s": per_escena,
        }
        for n in escenas
    ]
    data["prompt_used"] = f"script/{template_name}/{duration}s/historia"
    return data


def _resolve_quien(raw: str, nombres: list[str]) -> str | None:
    """'narrador' (cualquier capitalización) o nombre de personaje sin importar
    mayúsculas. Devuelve la forma canónica o None."""
    q = raw.strip()
    if q.lower() == NARRATOR:
        return NARRATOR
    for n in nombres:
        if n.lower() == q.lower():
            return n
    return None
