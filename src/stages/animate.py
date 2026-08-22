"""ANIMATE (M2): clips animados de personaje para las líneas de diálogo.

Modo carrusel: no-op. Modo historia: verifica que cada línea de diálogo tenga
su clip en `projects/<id>/clips/lNNN_<quien>.mp4` (mismo nombre que el audio
de `voice/`, extensión .mp4). Si falta alguno: escribe
`manifiesto_animacion.json` + `prompts_flow.md` (prompt detallado por clip) y
PAUSA el proyecto con instrucciones (PipelinePaused). Si están todos,
completa la etapa y EDITING los monta.

v1 los clips se generan a mano en Google Flow (Veo 3.1 Lite + Ingredients:
50 créditos gratis/día, 10 por clip ≈ 5 clips/día). v2: Colab + SadTalker
contra NUESTRO audio TTS (lip-sync exacto). La pista de voz nunca sale del
clip: el audio maestro es edge-tts y RENDERING ignora el audio de los videos
(concat a=0), así que cambiar de proveedor de clips no toca el montaje.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..state import Project, Stage
from .base import BaseStage, PipelinePaused
from .script import NARRATOR

MIN_CLIP_BYTES = 100_000  # un mp4 válido de 4-8 s pesa mucho más que esto


class AnimateStage(BaseStage):
    stage = Stage.ANIMATE

    def run(self, project: Project) -> dict:
        script = json.loads((project.path / "script.json").read_text(encoding="utf-8"))
        if script.get("mode") != "historia":
            return {}  # carrusel: nada que animar

        lines = json.loads(
            (project.path / "voice" / "lines.json").read_text(encoding="utf-8")
        )
        dialogo = [ln for ln in lines if ln["quien"] != NARRATOR]
        if not dialogo:
            return {}  # historia solo narrada

        personajes = {p["nombre"]: p for p in script.get("personajes", [])}
        contextos = _contextos_escena(project, lines)
        clips_dir = project.path / "clips"
        clips_dir.mkdir(exist_ok=True)

        manifiesto, faltantes = [], []
        for ln in dialogo:
            stem = Path(ln["archivo"]).stem
            clip = clips_dir / f"{stem}.mp4"
            p = personajes.get(ln["quien"], {})
            item = {
                "clip": f"clips/{stem}.mp4",
                "audio": f"voice/{ln['archivo']}",
                "quien": ln["quien"],
                "descriptor": p.get("descriptor", ""),
                "texto": ln["texto"],
                "emocion": ln.get("emocion") or "neutra",
                "escena": ln["escena"],
                "contexto_visual": contextos.get(ln["escena"], ""),
                "dur_s": ln["dur_s"],
                "listo": clip.exists() and clip.stat().st_size >= MIN_CLIP_BYTES,
            }
            manifiesto.append(item)
            if not item["listo"]:
                faltantes.append(item)

        (project.path / "manifiesto_animacion.json").write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if faltantes:
            (project.path / "prompts_flow.md").write_text(
                _prompts_flow(project, script, faltantes), encoding="utf-8"
            )
            nombres = ", ".join(f["clip"] for f in faltantes)
            raise PipelinePaused(
                f"faltan {len(faltantes)} clips de diálogo ({nombres}). "
                f"Guía con los prompts listos para copiar: "
                f"projects/{project.project_id}/prompts_flow.md — genera cada "
                f"clip en Flow (Video → Ingredients → Veo 3.1 Lite → 9:16), "
                f"descárgalo, súbelo a projects/{project.project_id}/clips/ "
                f"con el nombre EXACTO (menú ⋮ → Upload) y luego: "
                f"python -m src.main resume {project.project_id}"
            )
        return {"clips": "manifiesto_animacion.json"}


def _contextos_escena(project: Project, lines: list[dict]) -> dict[int, str]:
    """Prompt visual del storyboard por número de escena (para el prompt Flow).

    Los beats de modo historia son uno por escena y en orden; si el storyboard
    partió alguno, nos quedamos con el segmento más cercano.
    """
    board_file = project.path / "storyboard.json"
    if not board_file.exists():
        return {}
    segs = json.loads(board_file.read_text(encoding="utf-8")).get("segments", [])
    escenas = sorted({ln["escena"] for ln in lines})
    out: dict[int, str] = {}
    for n in escenas:
        pos = min(escenas.index(n), len(segs) - 1)
        if pos >= 0 and segs:
            out[n] = ((segs[pos].get("asset") or {}).get("prompt")
                      or segs[pos].get("on_screen_text") or "")
    return out


def _prompts_flow(project: Project, script: dict, faltantes: list[dict]) -> str:
    """Guía markdown: ingrediente por personaje + prompt detallado por clip."""
    pid = project.project_id
    partes = [
        f"# Clips pendientes — {pid}",
        "",
        "Flow gratis = 50 créditos/día; cada clip Veo 3.1 Lite cuesta 10 → ~5",
        "clips al día. La voz la pone el pipeline (TTS propio): pide ACTUACIÓN y",
        "EMOCIÓN, no diálogo hablado. Si el clip sale con audio, el montaje lo",
        "ignora (el master de audio es nuestro).",
        "",
        "## Paso 1 — Ingrediente de cada personaje (una sola vez)",
        "",
        "En Flow: modo Image (Nano Banana) → pega el descriptor → genera y",
        "guarda la imagen como ingrediente. Así el personaje se ve IGUAL en",
        "todos los clips (consistencia).",
        "",
    ]
    for p in script.get("personajes", []):
        partes += [
            f"### Ingrediente: {p['nombre']}",
            "```",
            f"3D animated character portrait, Pixar style, neutral background, "
            f"facing camera, full face visible: {p.get('descriptor', '')}. "
            f"Vertical 9:16, cinematic lighting, vibrant colors, no text, no watermark.",
            "```",
            "",
        ]
    partes += [
        "## Paso 2 — Clips (Video → Ingredients → Veo 3.1 Lite → 9:16 → 8 s)",
        "",
        "Selecciona el ingrediente del personaje, pega el prompt del clip,",
        "descarga el mp4 y RENÓMBRALO EXACTO como se indica. Sube cada archivo",
        f"a `projects/{pid}/clips/` (menú ⋮ → Upload en Cloud Shell) y corre:",
        f"`python -m src.main resume {pid}`",
        "",
    ]
    for f in faltantes:
        contexto = f" Scene: {f['contexto_visual']}." if f.get("contexto_visual") else ""
        partes += [
            f"### `{f['clip']}`",
            f"Personaje: **{f['quien']}** · línea de {f['dur_s']} s · emoción: {f['emocion']}",
            f"La línea que está diciendo (para tu referencia): «{f['texto']}»",
            "```",
            f"Vertical 9:16 3D animated shot, Pixar style. {f['descriptor']}. "
            f"The character acts an exaggerated telenovela reaction "
            f"({f['emocion']}): expressive eyes and mouth, subtle head and body "
            f"movement, as if saying \"{f['texto']}\".{contexto} Cinematic "
            f"lighting, vibrant colors, no on-screen text, no captions, no watermark.",
            "```",
            "",
        ]
    return "\n".join(partes)
