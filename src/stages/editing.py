"""EDITING: subtítulos por palabra (whisper) + edit_plan.json sincronizado.

Entrada: storyboard.json + voice.mp3 + assets_map.json.
Salida:  subtitles.ass/.srt (grupos de 2-4 palabras, keywords resaltadas,
         posición en safe zones) y edit_plan.json re-sincronizado con la
         duración real del audio.
Prioridad: ritmo y retención — corte visual cada 2-4 s.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError
from .storyboard import parse_t

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},72,{primary},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


class EditingStage(BaseStage):
    stage = Stage.EDITING

    def run(self, project: Project) -> dict:
        plan_path = project.path / "edit_plan.json"
        if plan_path.exists():
            return {"edit_plan": "edit_plan.json", "subtitles": "subtitles.ass"}

        board = json.loads((project.path / "storyboard.json").read_text(encoding="utf-8"))
        amap = json.loads((project.path / "assets_map.json").read_text(encoding="utf-8"))
        template = config.load_template(board.get("template") or "roblox")
        voice = project.path / "assets" / "voice.mp3"
        if not voice.exists():
            raise StageError("falta assets/voice.mp3 (etapa VOICE)")
        duration = float(project.data.get("voice_duration_s") or 0)
        if duration <= 0:
            raise StageError("falta voice_duration_s en project.json")

        times = _resync(board["segments"], duration)
        words = _transcribe(voice, project.data.get("language", "es"))
        keywords = _keywords(board["segments"])
        ass_text, srt_text = _subtitles(words, keywords, template)
        (project.path / "subtitles.ass").write_text(ass_text, encoding="utf-8")
        (project.path / "subtitles.srt").write_text(srt_text, encoding="utf-8")
        subdir = config.ROOT / "subtitles"
        subdir.mkdir(exist_ok=True)
        shutil.copy2(project.path / "subtitles.ass", subdir / f"{project.project_id}.ass")
        shutil.copy2(project.path / "subtitles.srt", subdir / f"{project.project_id}.srt")

        zones = config.PLATFORMS["safe_zones"]
        margin_v = int((zones["captions_bottom_min"] + zones["captions_bottom_max"]) / 2 * 1920)
        plan = {
            "fps": template.get("fps", 30),
            "resolution": template.get("resolution", [1080, 1920]),
            "duration_s": duration,
            "segments": [
                {
                    "index": i,
                    "source": amap[f"seg{i:02d}"]["path"],
                    "kind": amap[f"seg{i:02d}"]["kind"],
                    "t": [s, e],
                    "animation": seg.get("animation", "static"),
                    "transition_in": seg.get("transition_in", "cut"),
                    "sfx": seg.get("sfx"),
                }
                for i, (seg, (s, e)) in enumerate(zip(board["segments"], times))
            ],
            "audio": {
                "voice": "assets/voice.mp3",
                "music": amap.get("music", {}).get("path"),
                "music_volume": template.get("music", {}).get("volume", 0.15),
                "ducking": template.get("music", {}).get("ducking", True),
            },
            "captions": {"ass": "subtitles.ass", "srt": "subtitles.srt",
                         "margin_v": margin_v},
            "template": board.get("template"),
        }
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"edit_plan": "edit_plan.json", "subtitles": "subtitles.ass"}


def _resync(segments: list[dict], duration: float) -> list[tuple[float, float]]:
    """Re-sincroniza tiempos del storyboard con la duración real del audio."""
    times = [parse_t(seg["t"]) for seg in segments]
    total = times[-1][1] or 1
    scale = duration / total
    out = [(round(s * scale, 2), round(e * scale, 2)) for s, e in times]
    out[-1] = (out[-1][0], round(duration, 2))
    return out


def _transcribe(voice: Path, language: str) -> list[dict]:
    from faster_whisper import WhisperModel  # carga pesada: solo aquí
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(voice), language=language, word_timestamps=True)
    words = []
    for seg in segs:
        for w in seg.words or []:
            words.append({"w": w.word.strip(),
                          "t0": round(w.start, 2), "t1": round(w.end, 2)})
    if not words:
        raise StageError("whisper no produjo palabras al transcribir voice.mp3")
    return words


def _keywords(segments: list[dict]) -> set[str]:
    """Keywords = tokens en MAYÚSCULAS de los textos en pantalla."""
    kws = set()
    for seg in segments:
        for tok in re.findall(r"[A-ZÁÉÍÓÚÑ]{4,}", seg.get("on_screen_text") or ""):
            kws.add(tok.lower())
    return kws


def _ass_color(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _group(words: list[dict], lo: int, hi: int, max_chars: int) -> list[list[dict]]:
    groups, cur, chars = [], [], 0
    for w in words:
        cur.append(w)
        chars += len(w["w"]) + 1
        if (len(cur) >= hi) or (chars > max_chars and len(cur) >= lo) or (
                len(cur) >= lo and w["w"][-1:] in ".,!?"):
            groups.append(cur)
            cur, chars = [], 0
    if cur:
        groups.append(cur)
    return groups


def _highlight(text: str, keywords: set[str], highlight: str, primary: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0)
        if w.lower() in keywords:
            return "{\\1c" + highlight + "&}" + w + "{\\1c" + primary + "&}"
        return w
    return re.sub(r"\w+", repl, text)


def _ass_ts(t: float) -> str:
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _subtitles(words: list[dict], keywords: set[str], template: dict) -> tuple[str, str]:
    cap = template.get("captions", {})
    lo, hi = cap.get("words_per_group", [2, 4])
    max_chars = cap.get("max_chars_per_line", 22)
    highlight_on = cap.get("highlight_keywords", True)
    style = template.get("style", {})
    colors = style.get("colors", {})
    primary = _ass_color(colors.get("primary", "#FFFFFF"))
    highlight = _ass_color(colors.get("highlight", "#FFD400"))
    zones = config.PLATFORMS["safe_zones"]
    margin_v = int((zones["captions_bottom_min"] + zones["captions_bottom_max"]) / 2 * 1920)

    ass = ASS_HEADER.format(font=style.get("font", "Arial"),
                            primary=primary, margin_v=margin_v)
    srt_blocks = []
    for i, grp in enumerate(_group(words, lo, hi, max_chars), 1):
        t0, t1 = grp[0]["t0"], grp[-1]["t1"]
        text = " ".join(w["w"] for w in grp)
        text_ass = _highlight(text, keywords, highlight, primary) if highlight_on else text
        ass += f"Dialogue: 0,{_ass_ts(t0)},{_ass_ts(t1)},Default,,0,0,0,,{text_ass}\n"
        srt_blocks.append(f"{i}\n{_srt_ts(t0)} --> {_srt_ts(t1)}\n{text}\n")
    return ass, "\n".join(srt_blocks)
