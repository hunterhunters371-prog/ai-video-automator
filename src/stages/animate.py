"""ANIMATE (M2): clips animados de personaje para las líneas de diálogo.

Modo carrusel: no-op. Modo historia: verifica que cada línea de diálogo tenga
su clip en `projects/<id>/clips/` (mismo nombre base que su audio de `voice/`,
con extensión de video). Si falta alguno: escribe `manifiesto_animacion.json`
+ las guías de prompts y PAUSA el proyecto (PipelinePaused). Si están todos,
completa la etapa y EDITING los monta.

Salida de emergencia: con `SIN_CLIPS=1` no pausa. EDITING ya cae a la imagen
fija de la escena cuando una línea no tiene clip, así que el episodio se monta
entero (voces, subtítulos, música) como borrador. Sirve para ver el resultado
sin gastar cuota y como plan B cuando el generador se agota a media tarea.

Imágenes de referencia: si el usuario deja una imagen en `projects/<id>/refs/`
con el nombre del personaje (`limon.png`, `fresa.jpg`), las guías cambian a
modo referencia — subir esa imagen al generador en vez de crear el personaje
desde texto. Es la forma más eficaz de que no cambie de cara entre clips ni
entre episodios.

Los clips llegan a mano (descarga del navegador + Upload), así que aquí se
comprueban de verdad con ffprobe: un archivo corrupto o sin pista de vídeo
debe detectarse al recibirlo, no tres etapas después en RENDERING.

Proveedor preferido en configs/pipeline.yml → animate.provider:
  meta  — Meta AI / Vibes (meta.ai): prompt "Imagina..." → imagen → Animate
          (+ lip sync). Gratis durante el rollout, con tope diario y posible
          marca de agua. Guía generada: prompts_meta.md
  flow  — Google Flow: Veo 3.1 Lite, 50 créditos/día, 10 por clip, sin marca
          de agua. Guía generada: prompts_flow.md
  colab — [pendiente] SadTalker sobre nuestro TTS (lip-sync exacto, gratis).

Ambas guías se escriben siempre: si un proveedor se queda sin cuota, se sigue
con el otro sin volver a correr nada. El audio maestro SIEMPRE es nuestro
edge-tts (RENDERING ignora el audio de los clips), así que cambiar de
proveedor no toca el montaje.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

from .. import config
from ..state import Project, Stage
from .base import BaseStage, PipelinePaused
from .script import NARRATOR

MIN_CLIP_BYTES = 100_000  # un mp4 válido de 4-8 s pesa mucho más que esto
MIN_CLIP_S = 0.5
CLIP_EXTS = (".mp4", ".mov", ".webm", ".mkv")
REF_EXTS = (".png", ".jpg", ".jpeg", ".webp")
GUIAS = {"meta": "prompts_meta.md", "flow": "prompts_flow.md"}


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
        refs_dir = project.path / "refs"
        refs_dir.mkdir(exist_ok=True)
        refs = {nombre: _find_ref(refs_dir, nombre) for nombre in personajes}

        manifiesto, faltantes = [], []
        for ln in dialogo:
            stem = Path(ln["archivo"]).stem
            clip = _find_clip(clips_dir, stem)
            p = personajes.get(ln["quien"], {})
            ref = refs.get(ln["quien"])
            item = {
                "clip": (str(clip.relative_to(project.path)) if clip
                         else f"clips/{stem}.mp4"),
                "audio": f"voice/{ln['archivo']}",
                "quien": ln["quien"],
                "descriptor": p.get("descriptor", ""),
                "personalidad": p.get("personalidad", ""),
                # la imagen maestra del personaje: la usará la etapa de Colab
                "referencia": (str(ref.relative_to(project.path)) if ref else None),
                "texto": ln["texto"],
                "emocion": ln.get("emocion") or "neutra",
                "escena": ln["escena"],
                "contexto_visual": contextos.get(ln["escena"], ""),
                "dur_s": ln["dur_s"],
                "listo": clip is not None,
            }
            manifiesto.append(item)
            if clip is None:
                faltantes.append(item)

        (project.path / "manifiesto_animacion.json").write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if faltantes:
            # Las dos guías, siempre: si un proveedor agota su cuota diaria se
            # sigue con el otro sin re-ejecutar nada.
            (project.path / "prompts_meta.md").write_text(
                _prompts_meta(project, script, faltantes, refs), encoding="utf-8"
            )
            (project.path / "prompts_flow.md").write_text(
                _prompts_flow(project, script, faltantes, refs), encoding="utf-8"
            )
            if os.environ.get("SIN_CLIPS"):
                # Borrador: EDITING usa la imagen fija de la escena en cada
                # línea sin clip. Mejor un episodio completo que un bloqueo.
                print(
                    f"  … SIN_CLIPS=1: {len(faltantes)} de {len(dialogo)} líneas "
                    f"sin clip usarán la imagen fija de su escena (borrador)",
                    flush=True,
                )
                return {
                    "clips": "manifiesto_animacion.json",
                    "sin_clips": len(faltantes),
                }
            prov = str((config.PIPELINE.get("animate") or {}).get("provider", "meta"))
            guia = GUIAS.get(prov, GUIAS["meta"])
            otra = GUIAS["flow"] if guia == GUIAS["meta"] else GUIAS["meta"]
            nombres = ", ".join(f["clip"] for f in faltantes)
            con_ref = [n for n, r in refs.items() if r]
            aviso_ref = (
                f" Usando como referencia: {', '.join(con_ref)}." if con_ref else
                " Consejo: si dejas una imagen del personaje en "
                f"projects/{project.project_id}/refs/ (limon.png, fresa.jpg) y "
                "reanudas, la guía se reescribe para partir de ella y el "
                "personaje deja de cambiar de cara."
            )
            raise PipelinePaused(
                f"faltan {len(faltantes)} clips de diálogo ({nombres}). "
                f"Guía paso a paso con los prompts listos para copiar: "
                f"projects/{project.project_id}/{guia} "
                f"(alternativa si se agota la cuota: {otra}).{aviso_ref} "
                f"Genera cada clip, descárgalo y súbelo a "
                f"projects/{project.project_id}/clips/ (menú ⋮ → Upload) con ese "
                f"nombre: las tildes y las mayúsculas dan igual, y vale .mp4, "
                f".mov, .webm o .mkv. Luego: "
                f"python -m src.main resume {project.project_id}\n"
                f"¿Prefieres ver el episodio ya, con imágenes fijas en lugar de "
                f"clips? SIN_CLIPS=1 python -m src.main resume "
                f"{project.project_id}"
            )
        return {"clips": "manifiesto_animacion.json"}


def _clave(nombre: str) -> str:
    """Clave de comparación de nombres: sin tildes, minúsculas, solo alfanumérico.

    Los nombres salen del personaje (`l002_limón`) y los teclea una persona al
    renombrar la descarga. macOS escribe las tildes descompuestas (NFD) y Linux
    compuestas (NFC): dos nombres idénticos a la vista no coinciden como texto.
    Comparando una versión neutra, `l002_limon.mp4`, `l002_limón.mp4` y
    `L002_LIMÓN.MP4` son el mismo clip.
    """
    base = unicodedata.normalize("NFKD", nombre)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", base.lower())


def _find_ref(refs_dir: Path, personaje: str) -> Path | None:
    """Imagen de referencia de un personaje, por nombre (tolerante con tildes)."""
    objetivo = _clave(personaje)
    for cand in sorted(refs_dir.iterdir()):
        if (cand.is_file() and cand.suffix.lower() in REF_EXTS
                and _clave(cand.stem) == objetivo):
            return cand
    return None


def _revisar(path: Path) -> str | None:
    """Motivo por el que el archivo NO sirve como clip, o None si está bien.

    Sin esto, una descarga a medias o un archivo que no es vídeo se cuela hasta
    RENDERING y revienta con un error de ffmpeg, después de todo el trabajo
    manual de generar y subir.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return None  # sin ffprobe no bloqueamos: ya avisa la etapa de render
    if r.returncode != 0:
        return "ffprobe no puede leerlo (¿descarga incompleta?)"
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return "ffprobe devolvió algo ilegible"
    if not (data.get("streams") or []):
        return "no tiene pista de vídeo"
    try:
        dur = float((data.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur < MIN_CLIP_S:
        return f"dura solo {dur:.1f}s"
    return None


def _find_clip(clips_dir: Path, stem: str) -> Path | None:
    """Clip de `stem` en cualquier extensión de vídeo, tolerante con el nombre."""
    objetivo = _clave(stem)
    rechazados: list[tuple[Path, str]] = []
    for cand in sorted(clips_dir.iterdir()):
        if not cand.is_file() or cand.suffix.lower() not in CLIP_EXTS:
            continue
        if _clave(cand.stem) != objetivo:
            continue
        if cand.stat().st_size < MIN_CLIP_BYTES:
            rechazados.append((cand, f"pesa solo {cand.stat().st_size // 1024} KB"))
            continue
        problema = _revisar(cand)
        if problema:
            rechazados.append((cand, problema))
            continue
        return cand
    for path, motivo in rechazados:
        print(f"  !! {path.name}: {motivo} — lo cuento como faltante", flush=True)
    return None


def _contextos_escena(project: Project, lines: list[dict]) -> dict[int, str]:
    """Prompt visual del storyboard por número de escena (para el prompt).

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


def _clip_len(default: int = 8) -> int:
    return int((config.PIPELINE.get("animate") or {}).get("clip_len_s", default))


def _bloque_referencia(pid: str, refs: dict) -> list[str]:
    """Explica la carpeta refs/ según si ya hay imágenes o no."""
    con = [n for n, r in refs.items() if r]
    if con:
        return [
            "## Imágenes de referencia detectadas",
            "",
            "Se usarán como origen de los clips (modo referencia):",
            "",
            *[f"- **{n}** → `refs/{refs[n].name}`" for n in con],
            "",
            "Descárgalas a tu equipo para poder adjuntarlas en el navegador:",
            f"menú ⋮ → **Download** → `projects/{pid}/refs/<archivo>`.",
            "",
        ]
    return [
        "## ¿Tienes una imagen del personaje?",
        "",
        "Un dibujo, una foto, un fotograma que te gustó de un intento anterior:",
        f"súbelo a `projects/{pid}/refs/` con el nombre del personaje",
        "(`limon.png`, `fresa.jpg` — sin tildes ni mayúsculas) y vuelve a lanzar",
        "`resume`. Esta guía se reescribe sola en **modo referencia**: en vez de",
        "inventar el personaje en cada intento, todos los clips parten de esa",
        "imagen. Es lo que más reduce que cambie de cara entre escenas.",
        "",
    ]


def _prompts_meta(project: Project, script: dict, faltantes: list[dict],
                  refs: dict) -> str:
    """Guía para Meta AI / Vibes (meta.ai): imagen → Animate → lip sync.

    Flujo y reglas según el Centro de ayuda oficial de Meta (ago-2026):
    - El prompt de imagen debe empezar por "Imagina" o "Crea una imagen" y ser
      detallado (escena + qué hay + estilo).
    - Se toca la imagen → Animate (+ prompt de animación opcional) → vibe.
    - Se puede animar una imagen SUBIDA y añadir lip sync para que hable.
    """
    pid = project.project_id
    seg = _clip_len()
    partes = [
        f"# Clips pendientes — {pid} · ruta META AI (meta.ai)",
        "",
        "## Cómo funciona (Centro de ayuda de Meta, ago-2026)",
        "",
        '1. Escribe un prompt que EMPIECE por "Imagina" → Meta AI genera varias',
        "   imágenes.",
        "2. Toca la imagen elegida → **Animate** (con prompt de animación) → vibe.",
        "3. Puedes añadir **lip sync** para que la imagen hable, y también animar",
        "   una imagen SUBIDA por ti.",
        "",
        "## Reglas de oro (para que no salga horrible)",
        "",
        "- **Una sola imagen por personaje**, reutilizada como origen de TODOS",
        "  sus clips (imagen→video, nunca texto→video): es lo único que evita que",
        "  el personaje cambie de cara entre escenas.",
        "- **Movimiento pequeño y lento** en el prompt de Animate: preserva el",
        "  parecido. Pedir acción grande deforma la cara.",
        "- Prompt detallado y con estilo explícito; Meta responde mal a lo vago.",
        "- Cuenta con ~5 generaciones por clip usable: descarta sin pena.",
        "- **Límites**: gratis durante el rollout, pero con tope diario y colas.",
        "  Si se corta, espera ~24 h o sigue con `prompts_flow.md` (Google Flow,",
        "  50 créditos/día). Meta ya anunció pruebas de suscripción de pago:",
        "  la barra libre puede cerrarse sin aviso.",
        "- **Marca de agua**: Vibes puede marcar el video. No recortes al montar",
        "  (perderías al personaje); si te molesta, usa la ruta Flow.",
        "- Lo que publiques en el feed de Vibes es público: NO lo publiques ahí",
        "  si el episodio es para tu canal. Solo genera y descarga.",
        "",
    ]
    partes += _bloque_referencia(pid, refs)
    partes += [
        "## Paso 1 — La imagen maestra de cada personaje (una vez, se reutiliza)",
        "",
    ]
    for p in script.get("personajes", []):
        ref = refs.get(p["nombre"])
        partes.append(f"### {p['nombre']}")
        if ref:
            partes += [
                f"Referencia: `refs/{ref.name}` — adjúntala en el chat de Meta AI",
                "y pide el restyle. Si el parecido te convence, esa es la imagen",
                "maestra; si no, salta este paso y anima la referencia tal cual.",
                "",
                "```",
                "Convierte esta imagen en un personaje de animación 3D estilo "
                "Pixar, en vertical y primer plano, con la cara completa visible "
                "y mirando a la cámara. Mantén exactamente la forma, los colores "
                "y los rasgos del original. Fondo simple y desenfocado, "
                "iluminación suave, colores vibrantes. Sin texto ni letras.",
                "```",
                "[no verificado: editar una imagen subida depende de tu región "
                "y versión de la app]",
                "",
            ]
        else:
            partes += [
                "```",
                f"Imagina un personaje de dibujos animados con cara expresiva: "
                f"{p.get('descriptor', '')}. Tiene ojos grandes y boca animada, "
                f"en primer plano vertical, mirando a la cámara con expresión "
                f"{p.get('personalidad') or 'expresiva'}. Fondo simple y "
                f"desenfocado. Estilo de animación 3D tipo Pixar, iluminación "
                f"cinematográfica suave, colores vibrantes. Sin texto ni letras "
                f"en la imagen.",
                "```",
                "Si sale realista o sin cara, insiste en *personaje de dibujos",
                "animados con ojos y boca*: es el fallo típico con frutas.",
                "",
            ]
        partes += [
            "Descárgala antes de animar: la reutilizas en cada clip de este",
            "personaje y en los próximos episodios.",
            "",
        ]
    partes += [
        f"## Paso 2 — Un clip por línea (Animate, ~{seg} s, vertical)",
        "",
        "Para cada clip: abre la imagen maestra del personaje (o súbela) →",
        "**Animate** → pega el prompt → genera → descarga.",
        "",
        "Sobre el **lip sync**: si tu versión permite subir un audio, usa el",
        "archivo de voz que ya generamos (indicado en cada clip) y la boca",
        "coincidirá exacto. Si solo permite escribir texto, pega el texto de la",
        "línea. [no verificado: depende de tu región y versión de la app]",
        "",
    ]
    for f in faltantes:
        contexto = (f" Alrededor: {f['contexto_visual']}."
                    if f.get("contexto_visual") else "")
        origen = (f"Imagen de origen: `{f['referencia']}`"
                  if f.get("referencia") else
                  f"Imagen de origen: la maestra de **{f['quien']}** (Paso 1)")
        partes += [
            f"### `{f['clip']}`",
            f"Personaje: **{f['quien']}** · línea de {f['dur_s']} s · "
            f"emoción: {f['emocion']}",
            origen,
            f"Audio para el lip sync: `{f['audio']}`",
            f"Texto de la línea: «{f['texto']}»",
            "",
            "```",
            f"El personaje habla a la cámara con emoción de {f['emocion']}: "
            f"mueve la boca como si dijera \"{f['texto']}\", parpadea y hace un "
            f"gesto exagerado de telenovela. Movimiento suave y lento, ligero "
            f"balanceo de cabeza y hombros, cámara fija.{contexto} Mantén el "
            f"mismo diseño y los mismos colores del personaje. Sin texto en "
            f"pantalla, sin subtítulos.",
            "```",
            "",
        ]
    partes += _paso_final(pid)
    return "\n".join(partes)


def _prompts_flow(project: Project, script: dict, faltantes: list[dict],
                  refs: dict) -> str:
    """Guía para Google Flow: ingrediente por personaje + prompt por clip."""
    pid = project.project_id
    seg = _clip_len()
    partes = [
        f"# Clips pendientes — {pid} · ruta GOOGLE FLOW",
        "",
        "Flow gratis = 50 créditos/día; cada clip Veo 3.1 Lite cuesta 10 → ~5",
        "clips al día, sin marca de agua. La voz la pone el pipeline (TTS",
        "propio): pide ACTUACIÓN y EMOCIÓN, no diálogo hablado. Si el clip sale",
        "con audio, el montaje lo ignora.",
        "",
    ]
    partes += _bloque_referencia(pid, refs)
    partes += [
        "## Paso 1 — Ingrediente de cada personaje (una sola vez)",
        "",
    ]
    for p in script.get("personajes", []):
        ref = refs.get(p["nombre"])
        partes.append(f"### Ingrediente: {p['nombre']}")
        if ref:
            partes += [
                f"Sube `refs/{ref.name}` directamente como **Ingredient**: Flow",
                "acepta imágenes propias y las usa como identidad del personaje.",
                "No hace falta generarla.",
                "",
            ]
        else:
            partes += [
                "Modo Image (Nano Banana) → pega esto → guárdala como ingrediente.",
                "",
                "```",
                f"3D animated cartoon character with an expressive face, big eyes "
                f"and animated mouth: {p.get('descriptor', '')}. Pixar style, "
                f"neutral background, facing camera, full face visible. "
                f"Vertical 9:16, cinematic lighting, vibrant colors, no text, "
                f"no watermark.",
                "```",
                "",
            ]
    partes += [
        f"## Paso 2 — Clips (Video → Ingredients → Veo 3.1 Lite → 9:16 → {seg} s)",
        "",
        "Selecciona el ingrediente del personaje, pega el prompt y descarga.",
        "",
    ]
    for f in faltantes:
        contexto = (f" Scene: {f['contexto_visual']}."
                    if f.get("contexto_visual") else "")
        partes += [
            f"### `{f['clip']}`",
            f"Personaje: **{f['quien']}** · línea de {f['dur_s']} s · "
            f"emoción: {f['emocion']}",
            f"Texto de la línea (referencia): «{f['texto']}»",
            "```",
            f"Vertical 9:16 3D animated shot, Pixar style. {f['descriptor']}. "
            f"The character acts an exaggerated telenovela reaction "
            f"({f['emocion']}): expressive eyes and mouth, subtle head and body "
            f"movement, as if saying \"{f['texto']}\".{contexto} Cinematic "
            f"lighting, vibrant colors, no on-screen text, no captions, "
            f"no watermark.",
            "```",
            "",
        ]
    partes += _paso_final(pid)
    return "\n".join(partes)


def _paso_final(pid: str) -> list[str]:
    return [
        "## Paso 3 — Subir y reanudar",
        "",
        "1. Renombra cada archivo como el título de su bloque, por ejemplo",
        "   `l002_limon.mp4`. **Las tildes y las mayúsculas dan igual**",
        "   (`l002_limón.MP4` también vale) y sirve .mp4, .mov, .webm o .mkv.",
        "   Lo único que importa es el `lNNN_personaje` del principio.",
        f"2. Menú ⋮ → **Upload** → súbelos a `projects/{pid}/clips/`.",
        f"3. `python -m src.main resume {pid}`",
        "",
        "No hace falta tenerlos todos de una vez: sube los que lleves, reanuda,",
        "y el pipeline volverá a pausar pidiendo solo los que falten.",
        "",
        "¿Prefieres ver el episodio ya, sin esperar a los clips? Con",
        f"`SIN_CLIPS=1 python -m src.main resume {pid}` se monta entero usando la",
        "imagen fija de cada escena en las líneas que aún no tienen clip.",
    ]
