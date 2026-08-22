"""VOICE: narración TTS con texto preprocesado para sonar natural.

Dos modos según script.json:
  - carrusel: una sola voz (configs/voice.yml) → assets/voice.mp3.
  - historia (M2): una voz por personaje + narrador. Genera un mp3 por línea
    en voice/ + lines.json (offsets y duraciones: base del manifiesto de
    ANIMATE) y el voice.mp3 completo ensamblado con ffmpeg para que
    EDITING/RENDERING actuales sigan funcionando.

edge-tts habla por websocket con el servicio de Microsoft y ese socket puede
quedarse esperando indefinidamente (Cloud Shell, redes con proxy). Por eso
cada síntesis lleva timeout + reintentos, y escribe a un .part que solo se
renombra al .mp3 final si el audio es válido: un corte (Ctrl+C, caída de red)
nunca deja un mp3 a medias que el cache daría por bueno.

Salida: assets/voice.mp3 + duración real del audio (EDITING re-sincroniza
        los tiempos del storyboard con ella).
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path

import edge_tts

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError
from .script import NARRATOR

# Un mp3 de edge-tts ronda los 4 KB por segundo. Por debajo de esto el archivo
# está truncado o vacío, no es una línea corta.
MIN_AUDIO_BYTES = 1000
TIMEOUT_S = 60.0
INTENTOS = 3

_U20 = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
        "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
        "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
        "veinte"]
_VEINTI = ["veintiuno", "veintidós", "veintitrés", "veinticuatro",
           "veinticinco", "veintiséis", "veintisiete", "veintiocho",
           "veintinueve"]
_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
         70: "setenta", 80: "ochenta", 90: "noventa"}
_HUNDREDS = {1: "ciento", 5: "quinientos", 7: "setecientos", 9: "novecientos"}


class VoiceStage(BaseStage):
    stage = Stage.VOICE

    def run(self, project: Project) -> dict:
        out = project.path / "assets" / "voice.mp3"
        if out.exists() and project.data.get("voice_duration_s"):
            return {"voice": "assets/voice.mp3"}  # idempotente

        script = json.loads((project.path / "script.json").read_text(encoding="utf-8"))
        cfg = config.VOICE
        out.parent.mkdir(exist_ok=True)

        if script.get("mode") == "historia":
            return self._multi_voz(project, script, cfg, out)

        text = preprocess(script["narration"])
        _tts(text, cfg["voice"], cfg, out)
        duration = _duration(out)
        project.data["voice_duration_s"] = duration
        project.save()
        return {"voice": "assets/voice.mp3", "voice_duration_s": duration}

    def _multi_voz(self, project: Project, script: dict, cfg: dict, out: Path) -> dict:
        """Una pista por línea con la voz de su personaje + ensamblado."""
        voces = {NARRATOR: cfg["voice"]}
        for p in script["personajes"]:
            voces[p["nombre"]] = p["voz"]

        vdir = project.path / "voice"
        vdir.mkdir(exist_ok=True)
        _limpiar_restos(vdir)

        lineas = script["lineas"]
        total = len(lineas)
        print(f"  {total} líneas · una llamada TTS por línea (~2-5 s cada una)",
              flush=True)

        partes = []
        t = 0.0
        for i, ln in enumerate(lineas, 1):
            quien = ln["quien"]
            voz = voces.get(quien)
            if voz is None:  # el guion nombró a alguien fuera de personajes[]
                print(f"  !! sin voz asignada para {quien!r}: uso la del narrador",
                      flush=True)
                voz = voces[NARRATOR]
            parte = vdir / f"l{i:03d}_{_slug(quien)}.mp3"
            # cada archivo es idempotente: un corte o un retry solo repite lo que falta
            if _size(parte) >= MIN_AUDIO_BYTES:
                marca = "cache"
            else:
                parte.unlink(missing_ok=True)
                inicio = time.monotonic()
                _tts(preprocess(str(ln["texto"])), voz, cfg, parte)
                marca = f"{time.monotonic() - inicio:.1f}s"
            dur = _duration(parte)
            print(f"  · {i}/{total} {quien} · {dur:.1f}s ({marca})", flush=True)
            partes.append({
                "archivo": parte.name,
                "quien": quien,
                "texto": ln["texto"],
                "emocion": ln.get("emocion"),
                "escena": ln["escena"],
                "offset_s": round(t, 2),
                "dur_s": dur,
            })
            t += dur

        (vdir / "lines.json").write_text(
            json.dumps(partes, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # voice.mp3 único para EDITING/RENDERING actuales; re-encode para
        # uniformar parámetros entre voces.
        lista = vdir / "_concat.txt"
        lista.write_text(
            "".join(f"file '{p['archivo']}'\n" for p in partes), encoding="utf-8"
        )
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", "_concat.txt", "-c:a", "libmp3lame", "-q:a", "4", str(out)],
                capture_output=True, text=True, cwd=str(vdir),
            )
        except FileNotFoundError as exc:
            raise StageError(
                "ffmpeg no encontrado: instala FFmpeg (docs/SETUP.md §1)"
            ) from exc
        if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise StageError(f"ffmpeg concat de voces falló: {r.stderr.strip()[:200]}")

        duration = _duration(out)
        project.data["voice_duration_s"] = duration
        project.save()
        return {"voice": "assets/voice.mp3", "voice_duration_s": duration,
                "voice_lines": "voice/lines.json"}


def _limpiar_restos(vdir: Path) -> None:
    """Descarta lo que un corte anterior pudo dejar a medias.

    Las líneas se generan en orden, así que si no llegó a escribirse lines.json
    la única sospechosa es la última: las anteriores están completas. Las
    versiones antiguas escribían directamente sobre el .mp3, y un mp3 truncado
    puede pesar lo suficiente para colarse por el cache.
    """
    for resto in vdir.glob("*.part"):
        resto.unlink(missing_ok=True)
    if (vdir / "lines.json").exists():
        return
    previas = sorted(vdir.glob("l[0-9][0-9][0-9]_*.mp3"))
    if previas:
        print(f"  descarto {previas[-1].name}: pudo quedar a medias en el corte "
              "anterior", flush=True)
        previas[-1].unlink(missing_ok=True)


def _size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


async def _sintetizar(text: str, voice: str, cfg: dict, dest: Path,
                      timeout_s: float) -> None:
    await asyncio.wait_for(
        edge_tts.Communicate(
            text,
            voice=voice,
            rate=cfg.get("rate", "+0%"),
            pitch=cfg.get("pitch", "+0Hz"),
            volume=cfg.get("volume", "+0%"),
        ).save(str(dest)),
        timeout=timeout_s,
    )


def _tts(text: str, voice: str, cfg: dict, out: Path) -> None:
    """Sintetiza `text` con `voice` y deja el mp3 en `out` (escritura atómica).

    Sin timeout el websocket de edge-tts puede esperar para siempre y la etapa
    parece colgada. Cada intento escribe a un .part y solo se renombra al final
    si el audio pesa lo esperado.
    """
    timeout_s = float(cfg.get("timeout_s", TIMEOUT_S))
    intentos = max(1, int(cfg.get("retries", INTENTOS)))
    tmp = out.with_suffix(".part")
    fallo = ""
    for intento in range(1, intentos + 1):
        tmp.unlink(missing_ok=True)
        try:
            asyncio.run(_sintetizar(text, voice, cfg, tmp, timeout_s))
        except KeyboardInterrupt:
            tmp.unlink(missing_ok=True)  # nunca dejar audio a medias
            raise
        except asyncio.TimeoutError:
            fallo = f"sin respuesta en {timeout_s:.0f}s"
        except Exception as exc:
            fallo = f"{type(exc).__name__}: {exc}"
        else:
            if _size(tmp) >= MIN_AUDIO_BYTES:
                tmp.replace(out)
                return
            fallo = f"audio truncado ({_size(tmp)} bytes)"
        if intento < intentos:
            espera = 2 * intento
            print(f"    intento {intento}/{intentos} falló ({voice}): {fallo} "
                  f"— reintento en {espera}s", flush=True)
            time.sleep(espera)
    tmp.unlink(missing_ok=True)
    raise StageError(
        f"edge-tts falló {intentos} veces con {voice}: {fallo}. "
        "Revisa la conexión y reanuda: las líneas ya generadas no se repiten."
    )


def _slug(text: str) -> str:
    s = re.sub(r"[^\w-]+", "_", text.strip().lower())
    return s.strip("_") or "voz"


def preprocess(text: str) -> str:
    """Números en letra, siglas espaciadas, puntuación normalizada."""
    pre = config.VOICE.get("text_preprocessing", {})
    if pre.get("expand_acronyms"):
        text = re.sub(r"\b([A-ZÁÉÍÓÚÑ]{2,})\b",
                      lambda m: " ".join(m.group(1)), text)
    if pre.get("numbers_to_words"):
        text = re.sub(r"\d+", lambda m: num_es(int(m.group(0))), text)
    if pre.get("normalize_punctuation"):
        text = re.sub(r"\s+", " ", text).strip()
    return text


def num_es(n: int) -> str:
    """Enteros 0-999999 a palabras en español (para TTS)."""
    if n <= 20:
        return _U20[n]
    if n < 30:
        return _VEINTI[n - 21]
    if n < 100:
        t, r = n // 10 * 10, n % 10
        return f"{_TENS[t]} y {_U20[r]}" if r else _TENS[t]
    if n < 1000:
        h, r = n // 100, n % 100
        if h == 1 and r == 0:
            return "cien"
        name = _HUNDREDS.get(h) or f"{_U20[h]}cientos"
        return f"{name} {num_es(r)}" if r else name
    if n < 1000000:
        th, r = n // 1000, n % 1000
        name = "mil" if th == 1 else f"{num_es(th)} mil"
        return f"{name} {num_es(r)}" if r else name
    return str(n)


def _duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
    except FileNotFoundError as exc:
        raise StageError("ffprobe no encontrado: instala FFmpeg (docs/SETUP.md §1)") from exc
    return round(float(r.stdout.strip()), 2)
