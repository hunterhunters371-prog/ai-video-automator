"""RENDERING: construye el video final vertical 9:16 con FFmpeg.

Entrada: edit_plan.json.
Salida:  renders/<id>.mp4 (1080x1920, fps de plantilla) + thumbnails/<id>.png.

Notas M1:
- Cortes duros entre segmentos (concat). Transiciones xfade quedan para M2.
- Imágenes con ken_burns vía zoompan (d=1, zoom por frame de salida).
- Ducking de música con sidechaincompress (sidechain = voz).
- SFX: el plan los lista; se mezclan cuando exista la biblioteca assets/sfx/.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError

ZOOM_IN = {"ken_burns_in", "zoom_punch", "zoom_lento"}
ZOOM_OUT = {"ken_burns_out", "zoom_out"}


class RenderingStage(BaseStage):
    stage = Stage.RENDERING
    timeout_s = 900

    def run(self, project: Project) -> dict:
        plan = json.loads((project.path / "edit_plan.json").read_text(encoding="utf-8"))
        out = config.ROOT / "renders" / f"{project.project_id}.mp4"
        thumb = config.ROOT / "thumbnails" / f"{project.project_id}.png"
        artifacts = {"render": f"../../renders/{project.project_id}.mp4",
                     "thumbnail": f"../../thumbnails/{project.project_id}.png"}
        if out.exists() and out.stat().st_size > 0:
            return artifacts  # idempotente
        out.parent.mkdir(exist_ok=True)
        thumb.parent.mkdir(exist_ok=True)

        fps = plan.get("fps", 30)
        w, h = plan.get("resolution", [1080, 1920])
        dur = float(plan["duration_s"])
        segs = plan["segments"]

        args = ["ffmpeg", "-y"]
        for seg in segs:
            length = seg["t"][1] - seg["t"][0]
            if seg["kind"] == "image":
                args += ["-loop", "1", "-framerate", str(fps),
                         "-t", f"{length:.2f}", "-i", seg["source"]]
            else:
                args += ["-i", seg["source"]]
        voice_idx = len(segs)
        args += ["-i", plan["audio"]["voice"]]
        music_idx = None
        if plan["audio"].get("music"):
            music_idx = len(segs) + 1
            args += ["-stream_loop", "-1", "-i", plan["audio"]["music"]]

        filters: list[str] = []
        for i, seg in enumerate(segs):
            length = seg["t"][1] - seg["t"][0]
            chain = f"[{i}:v]"
            if seg["kind"] == "video":
                chain += (f"loop=-1:size=2147483647,trim=0:{length:.2f},"
                          f"setpts=PTS-STARTPTS,"
                          f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                          f"crop={w}:{h},fps={fps},")
            elif seg.get("animation") in ZOOM_IN | ZOOM_OUT:
                zoom = ("min(1+0.0015*on,1.35)" if seg["animation"] in ZOOM_IN
                        else "max(1.35-0.0015*on,1.0)")
                chain += (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
                          f"crop={w * 2}:{h * 2},"
                          f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':"
                          f"y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
                          f"trim=0:{length:.2f},setpts=PTS-STARTPTS,")
            else:
                chain += (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                          f"crop={w}:{h},fps={fps},")
            filters.append(chain + f"setsar=1[v{i}]")

        concat = "".join(f"[v{i}]" for i in range(len(segs)))
        filters.append(
            f"{concat}concat=n={len(segs)}:v=1:a=0,"
            f"fade=t=in:st=0:d=0.3,"
            f"fade=t=out:st={max(dur - 0.4, 0):.2f}:d=0.4[vc]"
        )
        # fps final explícito: concat hereda el rate del 1er segmento y zoompan
        # puede ignorar su propio fps → sin esto la salida sale a 25 fps.
        filters.append(f"[vc]ass={plan['captions']['ass']},fps={fps}[vout]")

        filters.append(f"[{voice_idx}:a]aresample=44100[voz]")
        if music_idx is not None:
            vol = plan["audio"].get("music_volume", 0.15)
            filters.append(
                f"[{music_idx}:a]atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,volume={vol}[mus]"
            )
            if plan["audio"].get("ducking", True):
                filters.append(
                    "[mus][voz]sidechaincompress=threshold=0.03:ratio=6:"
                    "attack=15:release=400:makeup=1[aout]"
                )
            else:
                filters.append("[voz][mus]amix=inputs=2:duration=first[aout]")
        else:
            filters.append("[voz]anull[aout]")

        cmd = args + [
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
            "-t", f"{dur:.2f}", str(out),
        ]
        _run(cmd, project.path)
        _run(["ffmpeg", "-y", "-ss", f"{max(dur * 0.15, 0.5):.2f}", "-i", str(out),
              "-frames:v", "1", str(thumb)], project.path)
        return artifacts


def _run(cmd: list[str], cwd: Path) -> None:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise StageError("ffmpeg no encontrado: instálalo (docs/SETUP.md §1)") from exc
    if proc.returncode != 0:
        raise StageError(f"ffmpeg exit {proc.returncode}: {proc.stderr[-400:]}")
