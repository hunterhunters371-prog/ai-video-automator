"""VOICE: narración TTS con texto preprocesado para sonar natural.

Entrada: script.json (narración) + configs/voice.yml.
Salida:  assets/voice.mp3 + duración real del audio (EDITING re-sincroniza
         los tiempos del storyboard con ella).
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError

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
        text = preprocess(script["narration"])
        cfg = config.VOICE
        out.parent.mkdir(exist_ok=True)
        try:
            asyncio.run(
                edge_tts.Communicate(
                    text,
                    voice=cfg["voice"],
                    rate=cfg.get("rate", "+0%"),
                    pitch=cfg.get("pitch", "+0Hz"),
                    volume=cfg.get("volume", "+0%"),
                ).save(str(out))
            )
        except Exception as exc:
            raise StageError(f"edge-tts falló: {exc}") from exc
        if not out.exists() or out.stat().st_size == 0:
            raise StageError("edge-tts no produjo audio")

        duration = _duration(out)
        project.data["voice_duration_s"] = duration
        project.save()
        return {"voice": "assets/voice.mp3", "voice_duration_s": duration}


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
