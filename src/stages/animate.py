"""ANIMATE (M2): clips animados de personaje para las lineas de dialogo.

Modo carrusel: no-op. Modo historia: cada linea de dialogo necesita su clip en
`projects/<id>/clips/`, con el mismo nombre base que su audio de `voice/`.

RUTA AUTOMATICA (22 ago 2026) -- `animate.provider: wan`
Wan es el motor de video de Alibaba (el mismo sitio del que sale Qwen, que es
su LLM). Model Studio regala 50 s de video por modelo durante 90 dias en la
region Singapur: un episodio de 6 clips x 8 s = 48 s entra entero en la cuota
gratis, y despues cuesta ~1,80 $ en 1080P. Es la unica via verificada que es a
la vez gratis para empezar, automatica y con calidad de formato.

El bucle es: imagen maestra del personaje -> un clip por linea de dialogo
(imagen -> video, nunca texto -> video) -> descarga a clips/. Si un personaje
no tiene imagen en `refs/`, se le genera una y se guarda ahi: a partir de ese
momento TODOS sus clips parten del mismo archivo, que es lo unico que impide
que cambie de cara entre escenas y entre episodios.

RUTAS MANUALES (plan B, siguen funcionando)
  meta  -- Meta AI / Vibes: prompt "Imagina..." -> imagen -> Animate.
  flow  -- Google Flow: Veo 3.1 Lite, 50 creditos/dia, 10 por clip.
Sus guias (prompts_meta.md, prompts_flow.md) se escriben SIEMPRE que falte
algun clip, tambien en modo wan: si se agota la cuota o cae la API, se sigue a
mano sin volver a ejecutar nada.

Salida de emergencia: con `SIN_CLIPS=1` no se genera ni se pausa. EDITING cae
a la imagen fija de la escena en las lineas sin clip, asi que el episodio se
monta entero como borrador.

Llegue como llegue el clip (API o navegador), aqui se comprueba de verdad con
ffprobe: un archivo corrupto o sin pista de video se detecta al recibirlo, no
tres etapas despues en RENDERING.

El audio maestro SIEMPRE es nuestro edge-tts (RENDERING ignora el audio de los
clips), asi que cambiar de proveedor no toca el montaje.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path

from .. import config, wan
from ..state import Project, Stage
from .base import BaseStage, PipelinePaused
from .script import NARRATOR

MIN_CLIP_BYTES = 100_000  # un mp4 valido de 4-8 s pesa mucho mas que esto
MIN_CLIP_S = 0.5
CLIP_EXTS = (".mp4", ".mov", ".webm", ".mkv")
REF_EXTS = (".png", ".jpg", ".jpeg", ".webp")
GUIAS = {"meta": "prompts_meta.md", "flow": "prompts_flow.md"}

# Lo que Wan NO debe hacer. Los subtitulos los pone RENDERING y la marca de
# agua arruina el canal.
NEGATIVO = (
    "on-screen text, subtitles, captions, letters, watermark, logo, "
    "extra fingers, deformed hands, distorted face, character identity change, "
    "different character, duplicated character, split screen, camera cut, "
    "low quality, blurry, grainy, jpeg artifacts, static frozen image"
)
# Glosario es -> en. FLUX y Wan estan entrenados con texto en ingles: el mismo
# personaje descrito en espanol sale bastante peor. No es una traduccion, es
# el vocabulario del genero (frutas, comida, colores y ropa).
GLOSARIO = {
    "limon": "lemon", "limones": "lemons", "fresa": "strawberry",
    "fresas": "strawberries", "banana": "banana", "platano": "banana",
    "sandia": "watermelon", "naranja": "orange", "manzana": "apple",
    "uva": "grape", "uvas": "grapes", "pina": "pineapple", "tomate": "tomato",
    "brocoli": "broccoli", "cereza": "cherry", "kiwi": "kiwi",
    "mango": "mango", "pera": "pear", "melon": "melon", "melocoton": "peach",
    "durazno": "peach", "aguacate": "avocado", "zanahoria": "carrot",
    "yogur": "yogurt cup", "leche": "milk carton", "huevo": "egg",
    "queso": "cheese", "pan": "bread loaf", "cebolla": "onion",
    "lechuga": "lettuce", "papa": "potato", "patata": "potato",
    "maiz": "corn cob", "coco": "coconut", "frambuesa": "raspberry",
    "arandano": "blueberry", "granada": "pomegranate", "higo": "fig",
    "amarillo": "yellow", "amarilla": "yellow", "rojo": "red", "roja": "red",
    "verde": "green", "azul": "blue", "naranjado": "orange colored",
    "morado": "purple", "rosa": "pink", "rosado": "pink", "blanco": "white",
    "negro": "black", "marron": "brown", "dorado": "golden",
    "celoso": "jealous", "celosa": "jealous", "triste": "sad",
    "enfadado": "angry", "enojado": "angry", "feliz": "happy",
    "alegre": "cheerful", "asustado": "scared", "sorprendido": "surprised",
    "orgulloso": "proud", "timido": "shy", "coqueta": "flirty",
    "coqueto": "flirty", "dramatico": "dramatic", "dramatica": "dramatic",
    "elegante": "elegant", "presumido": "vain", "presumida": "vain",
    "gafas": "glasses", "sombrero": "hat", "gorra": "cap", "bufanda": "scarf",
    "vestido": "dress", "chaqueta": "jacket", "camisa": "shirt",
    "corbata": "tie", "zapatos": "shoes", "bolso": "handbag",
    "cocina": "kitchen", "nevera": "fridge", "mercado": "market",
    "gimnasio": "gym", "escuela": "school", "boda": "wedding",
    "hospital": "hospital", "playa": "beach", "fiesta": "party",
}
EMOCIONES = {
    "celos": "jealous", "celosa": "jealous", "celoso": "jealous",
    "tristeza": "heartbroken", "triste": "heartbroken", "llanto": "crying",
    "enfado": "furious", "enojo": "furious", "ira": "furious",
    "rabia": "furious", "sorpresa": "shocked", "asombro": "shocked",
    "miedo": "scared", "alegria": "joyful", "felicidad": "joyful",
    "amor": "lovestruck", "burla": "mocking", "desprecio": "disdainful",
    "verguenza": "embarrassed", "culpa": "guilty", "suplica": "pleading",
    "neutra": "intense", "neutral": "intense",
}


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

        manifiesto, faltantes, refs = self._manifiesto(
            project, dialogo, personajes, contextos, clips_dir, refs_dir
        )

        prov = str((config.PIPELINE.get("animate") or {}).get("provider", "wan"))
        fallos: list[str] = []
        if faltantes and prov == "wan" and not os.environ.get("SIN_CLIPS"):
            fallos = self._generar(project, faltantes, personajes, refs_dir)
            # Puede haber clips e imagenes maestras nuevas: se recuenta todo.
            manifiesto, faltantes, refs = self._manifiesto(
                project, dialogo, personajes, contextos, clips_dir, refs_dir
            )

        (project.path / "manifiesto_animacion.json").write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if not faltantes:
            print(f"    {len(manifiesto)} clips de dialogo listos", flush=True)
            return {"clips": "manifiesto_animacion.json"}

        # Las dos guias manuales, siempre: si la API falla o se agota la cuota
        # se sigue a mano sin re-ejecutar nada.
        (project.path / "prompts_meta.md").write_text(
            _prompts_meta(project, script, faltantes, refs), encoding="utf-8"
        )
        (project.path / "prompts_flow.md").write_text(
            _prompts_flow(project, script, faltantes, refs), encoding="utf-8"
        )
        if os.environ.get("SIN_CLIPS"):
            # Borrador: EDITING usa la imagen fija de la escena en cada linea
            # sin clip. Mejor un episodio completo que un bloqueo.
            print(
                f"  ... SIN_CLIPS=1: {len(faltantes)} de {len(dialogo)} lineas "
                f"sin clip usaran la imagen fija de su escena (borrador)",
                flush=True,
            )
            return {"clips": "manifiesto_animacion.json", "sin_clips": len(faltantes)}
        raise PipelinePaused(_mensaje_pausa(project, faltantes, refs, prov, fallos))

    # -- manifiesto ---------------------------------------------------------
    def _manifiesto(self, project: Project, dialogo: list[dict],
                    personajes: dict, contextos: dict, clips_dir: Path,
                    refs_dir: Path) -> tuple[list[dict], list[dict], dict]:
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
                # imagen maestra del personaje: el origen de todos sus clips
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
        return manifiesto, faltantes, refs

    # -- generacion automatica (Wan) ---------------------------------------
    def _generar(self, project: Project, faltantes: list[dict],
                 personajes: dict, refs_dir: Path) -> list[str]:
        """Genera los clips que faltan. Devuelve los motivos de lo que falle."""
        cfg = (config.PIPELINE.get("animate") or {}).get("wan") or {}
        modelo = str(cfg.get("modelo", "wan2.6-i2v-flash"))
        resolucion = wan.resolucion_valida(modelo, str(cfg.get("resolucion", "1080P")))
        tope_clips = int(cfg.get("max_clips_por_run", 0) or 0)
        tope_seg = float(cfg.get("max_segundos_por_run", 0) or 0)
        intervalo = int(cfg.get("sondeo_s", 15))
        timeout_tarea = int(cfg.get("timeout_tarea_s", 900))
        fallos: list[str] = []

        if not config.DASHSCOPE_API_KEY:
            motivo = ("DASHSCOPE_API_KEY vacia: no se puede generar nada por API "
                      "(alta y clave en docs/wan-alibaba.md)")
            print(f"  [!] {motivo}", flush=True)
            return [motivo]

        total_s = sum(wan.duracion_real(modelo, f["dur_s"]) for f in faltantes)
        precio = wan.precio_s(modelo, resolucion)
        coste = (f" ~ {total_s * precio:.2f} $ si ya gastaste la cuota gratis"
                 if precio else "")
        print(f"    Wan {modelo} {resolucion}: {len(faltantes)} clips, "
              f"{total_s:.0f}s en total{coste}", flush=True)
        print("    (cuota gratis de estreno: 50 s por modelo, 90 dias)", flush=True)

        gastado = 0.0
        for i, f in enumerate(faltantes, 1):
            if tope_clips and i > tope_clips:
                fallos.append(f"parado en {tope_clips} clips por "
                              "animate.wan.max_clips_por_run")
                break
            segundos = wan.duracion_real(modelo, f["dur_s"])
            if tope_seg and gastado + segundos > tope_seg:
                fallos.append(f"parado en {gastado:.0f}s por "
                              "animate.wan.max_segundos_por_run")
                break
            quien = f["quien"]
            try:
                ref = self._maestra(project, quien, personajes.get(quien, {}), refs_dir)
            except Exception as exc:  # noqa: BLE001 - queremos el motivo, no el traceback
                motivo = f"{quien}: sin imagen maestra ({type(exc).__name__}: {exc})"
                print(f"  [!] {motivo}", flush=True)
                fallos.append(motivo)
                continue
            if ref is None:
                motivo = (f"{quien}: no se pudo crear la imagen maestra "
                          f"(revisa los avisos de arriba o deja una en "
                          f"refs/{_clave(quien)}.png)")
                print(f"  [!] {motivo}", flush=True)
                fallos.append(motivo)
                continue
            dest = project.path / f["clip"]
            print(f"    -> {i}/{len(faltantes)} {dest.name} · {quien} · "
                  f"{segundos:.0f}s · {f['emocion']} (1-5 min)", flush=True)
            try:
                wan.generar(
                    modelo=modelo,
                    prompt=_prompt_clip(f),
                    imagen=ref,
                    dest=dest,
                    resolucion=resolucion,
                    segundos=segundos,
                    negativo=NEGATIVO,
                    prompt_extend=bool(cfg.get("prompt_extend", True)),
                    intervalo_s=intervalo,
                    timeout_tarea_s=timeout_tarea,
                )
            except wan.WanError as exc:
                motivo = f"{dest.name}: {exc}"
                print(f"  [!] {motivo}", flush=True)
                fallos.append(motivo)
                continue
            except Exception as exc:  # noqa: BLE001
                motivo = f"{dest.name}: {type(exc).__name__}: {str(exc)[:200]}"
                print(f"  [!] {motivo}", flush=True)
                fallos.append(motivo)
                continue
            gastado += segundos
            print(f"       ok · {dest.stat().st_size // 1024} KB · "
                  f"{gastado:.0f}s consumidos en esta tanda", flush=True)
        return fallos

    def _maestra(self, project: Project, nombre: str, p: dict,
                 refs_dir: Path) -> Path | None:
        """Imagen maestra del personaje: la de refs/ o una nueva generada.

        Se guarda en refs/ a proposito: el siguiente episodio la reutiliza y el
        personaje mantiene la cara. Es el equivalente barato al "ingrediente"
        de Flow.
        """
        ya = _find_ref(refs_dir, nombre)
        if ya:
            return ya
        from .assets import AssetsStage  # import local: evita ciclo de imports

        print(f"    generando imagen maestra de {nombre} ...", flush=True)
        etapa = AssetsStage()
        ruta = etapa._ai_image(_prompt_personaje(nombre, p), refs_dir / _clave(nombre))
        if ruta:
            print(f"       {ruta.relative_to(project.path)}", flush=True)
        return ruta


def _clave(nombre: str) -> str:
    """Clave de comparacion de nombres: sin tildes, minusculas, alfanumerico.

    Los nombres salen del personaje (`l002_limon`) y los teclea una persona al
    renombrar la descarga. macOS escribe las tildes descompuestas (NFD) y Linux
    compuestas (NFC): dos nombres identicos a la vista no coinciden como texto.
    Comparando una version neutra, `l002_limon.mp4`, `l002_limón.mp4` y
    `L002_LIMÓN.MP4` son el mismo clip.
    """
    base = unicodedata.normalize("NFKD", nombre)
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", base.lower())


def _traducir(texto: str) -> str:
    """Pasa por el glosario las palabras del descriptor. Ver GLOSARIO."""
    def _rep(m: re.Match) -> str:
        palabra = m.group(0)
        trad = GLOSARIO.get(_clave(palabra))
        if not trad:
            return palabra
        return trad[:1].upper() + trad[1:] if palabra[:1].isupper() else trad

    return re.sub(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", _rep, texto or "")


def _emocion_en(emocion: str) -> str:
    return EMOCIONES.get(_clave(emocion), _traducir(emocion) or "intense")


def _prompt_personaje(nombre: str, p: dict) -> str:
    """Prompt de la imagen maestra: personaje ANTROPOMORFICO, no fruta con ojos.

    Los canales del formato no dibujan una fruta con cara pegada: dibujan un
    personaje con cuerpo humano, brazos, piernas y ropa cuya cabeza es la
    fruta. Era la diferencia mas grande entre sus videos y nuestros intentos.
    """
    desc = _traducir(p.get("descriptor") or nombre)
    rasgo = _traducir(p.get("personalidad") or "")
    extra = f" Personality shown in the pose: {rasgo}." if rasgo else ""
    return (
        f"3D animated cartoon character, Pixar style: anthropomorphic {desc}. "
        "The head is the fruit itself, with huge expressive cartoon eyes, "
        "eyebrows and a big animated mouth; the body is human-like with arms, "
        "legs, hands and colorful clothes. Dramatic soap-opera facial "
        f"expression.{extra} Standing, facing the camera, full face and upper "
        "body visible, centered composition. Soft cinematic lighting, vibrant "
        "saturated colors, clean softly blurred background, high detail, "
        "glossy render. Vertical 9:16 portrait. No text, no letters, "
        "no watermark."
    )


def _prompt_clip(f: dict) -> str:
    """Prompt de animacion de una linea: un solo plano, boca en movimiento.

    En ingles a proposito: la doc de Wan solo garantiza chino e ingles. El
    texto de la linea NO se manda -- el clip es mudo y la voz la pone VOICE;
    lo unico que importa es que la boca se mueva con la emocion correcta.
    """
    emo = _emocion_en(f.get("emocion", ""))
    ctx = _traducir(f.get("contexto_visual") or "")
    escena = f" Background: {ctx}." if ctx else ""
    return (
        "3D Pixar-style animated shot, vertical 9:16. The character from the "
        f"image talks to the camera with an exaggerated {emo} telenovela "
        "performance: the mouth moves continuously as if speaking, eyebrows "
        "and eyes very expressive, blinking, small head tilts and hand "
        "gestures. Keep exactly the same character design, colors, outfit and "
        f"proportions as the input image.{escena} One single continuous shot, "
        "slow subtle camera push-in, soft cinematic lighting, vibrant colors."
    )


def _find_ref(refs_dir: Path, personaje: str) -> Path | None:
    """Imagen de referencia de un personaje, por nombre (tolerante con tildes)."""
    objetivo = _clave(personaje)
    for cand in sorted(refs_dir.iterdir()):
        if (cand.is_file() and cand.suffix.lower() in REF_EXTS
                and _clave(cand.stem) == objetivo):
            return cand
    return None


def _revisar(path: Path) -> str | None:
    """Motivo por el que el archivo NO sirve como clip, o None si esta bien.

    Sin esto, una descarga a medias o un archivo que no es video se cuela hasta
    RENDERING y revienta con un error de ffmpeg, despues de todo el trabajo.
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
        return "ffprobe devolvio algo ilegible"
    if not (data.get("streams") or []):
        return "no tiene pista de video"
    try:
        dur = float((data.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        dur = 0.0
    if dur < MIN_CLIP_S:
        return f"dura solo {dur:.1f}s"
    return None


def _find_clip(clips_dir: Path, stem: str) -> Path | None:
    """Clip de `stem` en cualquier extension de video, tolerante con el nombre."""
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
    """Prompt visual del storyboard por numero de escena (para el prompt).

    Los beats de modo historia son uno por escena y en orden; si el storyboard
    partio alguno, nos quedamos con el segmento mas cercano.
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


def _mensaje_pausa(project: Project, faltantes: list[dict], refs: dict,
                   prov: str, fallos: list[str]) -> str:
    pid = project.project_id
    guia = GUIAS.get(prov, GUIAS["meta"])
    otra = GUIAS["flow"] if guia == GUIAS["meta"] else GUIAS["meta"]
    nombres = ", ".join(f["clip"] for f in faltantes)
    if prov == "wan":
        detalle = (" Motivos: " + " | ".join(fallos[:4])) if fallos else ""
        return (
            f"faltan {len(faltantes)} clips de dialogo ({nombres}) y la "
            f"generacion automatica con Wan no los completo.{detalle}\n"
            f"Opciones:\n"
            f"  1) Arregla el motivo y reanuda: "
            f"python -m src.main resume {pid}\n"
            f"  2) Hazlos a mano con las guias ya escritas: "
            f"projects/{pid}/{GUIAS['meta']} o projects/{pid}/{GUIAS['flow']}, "
            f"sube los mp4 a projects/{pid}/clips/ y reanuda.\n"
            f"  3) Mira el episodio ya, con imagenes fijas: "
            f"SIN_CLIPS=1 python -m src.main resume {pid}"
        )
    con_ref = [n for n, r in refs.items() if r]
    aviso_ref = (
        f" Usando como referencia: {', '.join(con_ref)}." if con_ref else
        " Consejo: si dejas una imagen del personaje en "
        f"projects/{pid}/refs/ (limon.png, fresa.jpg) y reanudas, la guia se "
        "reescribe para partir de ella y el personaje deja de cambiar de cara."
    )
    return (
        f"faltan {len(faltantes)} clips de dialogo ({nombres}). "
        f"Guia paso a paso con los prompts listos para copiar: "
        f"projects/{pid}/{guia} "
        f"(alternativa si se agota la cuota: {otra}).{aviso_ref} "
        f"Genera cada clip, descargalo y subelo a projects/{pid}/clips/ "
        f"(menu ⋮ → Upload) con ese nombre: las tildes y las mayusculas dan "
        f"igual, y vale .mp4, .mov, .webm o .mkv. Luego: "
        f"python -m src.main resume {pid}\n"
        f"¿Prefieres ver el episodio ya, con imagenes fijas en lugar de clips? "
        f"SIN_CLIPS=1 python -m src.main resume {pid}"
    )


def _bloque_referencia(pid: str, refs: dict) -> list[str]:
    """Explica la carpeta refs/ segun si ya hay imagenes o no."""
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
        "> Plan B manual. La ruta automática es `animate.provider: wan`",
        "> (docs/wan-alibaba.md): genera estos mismos clips por API.",
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
                f"Imagina un personaje de dibujos animados con cuerpo humano y "
                f"cara muy expresiva: {p.get('descriptor', '')}. La cabeza es la "
                f"fruta, con ojos grandes, cejas y boca animada; tiene brazos, "
                f"piernas y ropa de colores. Está de pie en primer plano "
                f"vertical, mirando a la cámara con expresión "
                f"{p.get('personalidad') or 'dramática de telenovela'}. Fondo "
                f"simple y desenfocado. Estilo de animación 3D tipo Pixar, "
                f"iluminación cinematográfica suave, colores vibrantes. Sin "
                f"texto ni letras en la imagen.",
                "```",
                "Si sale una fruta con una cara pegada, insiste en *cuerpo",
                "humano, brazos, piernas y ropa*: es el fallo típico del formato.",
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
        "> Plan B manual. La ruta automática es `animate.provider: wan`",
        "> (docs/wan-alibaba.md): genera estos mismos clips por API.",
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
                f"3D animated cartoon character, Pixar style: anthropomorphic "
                f"{p.get('descriptor', '')}. The head is the fruit, with huge "
                f"expressive eyes and animated mouth; human-like body with arms, "
                f"legs and colorful clothes. Standing, facing camera, full face "
                f"visible, neutral blurred background. Vertical 9:16, cinematic "
                f"lighting, vibrant colors, no text, no watermark.",
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
