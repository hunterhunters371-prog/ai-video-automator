"""QC: control de calidad técnico v1 (determinista) con reporte.

Entrada: renders/<id>.mp4.
Salida:  qc_report.json → COMPLETED, o FAILED con diagnóstico.

Checks: existe, tamaño > 0, duración ±tolerancia, resolución/fps, streams de
audio y video, pantallas negras (blackdetect), congelados (freezedetect),
subtítulos dentro de safe zones, assets referenciados existen.
M2: loop de corrección asistido por LLM (corregir → re-render → re-validar).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError


class QCStage(BaseStage):
    stage = Stage.QC
    max_retries = 1

    def run(self, project: Project) -> dict:
        render = config.ROOT / "renders" / f"{project.project_id}.mp4"
        checks: list[dict] = []
        qc_cfg = config.PIPELINE["qc"]
        plats = config.PLATFORMS

        ok = render.exists() and render.stat().st_size > 0
        checks.append({"name": "exists", "ok": ok})
        if not ok:
            return self._report(project, checks)

        probe = self._ffprobe(render)
        dur = float(probe.get("format", {}).get("duration", 0) or 0)
        target = float(project.data.get("voice_duration_s")
                       or project.data.get("duration_target_s") or 30)
        tol = qc_cfg.get("duration_tolerance_s", 1.5)
        checks.append({"name": "duration", "ok": abs(dur - target) <= tol,
                       "detail": f"{dur:.2f}s vs {target:.2f}s"})

        vstreams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
        astreams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
        checks.append({"name": "has_audio", "ok": bool(astreams)})
        if vstreams:
            w, h = vstreams[0].get("width"), vstreams[0].get("height")
            want = plats["youtube_shorts"]["resolution"]
            checks.append({"name": "resolution", "ok": [w, h] == want,
                           "detail": f"{w}x{h}"})
            num, _, den = vstreams[0].get("r_frame_rate", "0/1").partition("/")
            fps = float(num) / float(den or 1)
            checks.append({"name": "fps",
                           "ok": round(fps) in plats["youtube_shorts"]["fps"],
                           "detail": f"{fps:.2f}"})
        else:
            checks.append({"name": "resolution", "ok": False,
                           "detail": "sin stream de video"})

        checks.append(self._detect(render, "black",
                                   qc_cfg.get("black_detect_threshold_s", 0.4)))
        checks.append(self._detect(render, "freeze",
                                   qc_cfg.get("freeze_detect_threshold_s", 2.0)))
        checks.append(self._captions_zone(project, plats))
        checks.append(self._assets_exist(project))
        return self._report(project, checks)

    # -- checks ------------------------------------------------------------
    def _ffprobe(self, path: Path) -> dict:
        try:
            proc = subprocess.run(
                ["ffprobe", "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)],
                capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            raise StageError("ffprobe no encontrado: instala FFmpeg (docs/SETUP.md §1)") from exc
        if proc.returncode != 0:
            raise StageError(f"ffprobe exit {proc.returncode}: {proc.stderr[-300:]}")
        return json.loads(proc.stdout)

    def _detect(self, render: Path, kind: str, threshold: float) -> dict:
        filt = (f"blackdetect=d={threshold}:pix_th=0.10" if kind == "black"
                else f"freezedetect=n=0.003:d={threshold}")
        proc = subprocess.run(
            ["ffmpeg", "-i", str(render), "-vf", filt, "-an", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        hits = re.findall(rf"{kind}_start:([0-9.]+)", proc.stderr)
        return {"name": f"{kind}_frames", "ok": not hits,
                "detail": f"{len(hits)} tramos" if hits else ""}

    def _captions_zone(self, project: Project, plats: dict) -> dict:
        ass = project.path / "subtitles.ass"
        zones = plats["safe_zones"]
        if not ass.exists():
            return {"name": "captions_safe_zone", "ok": False,
                    "detail": "falta subtitles.ass"}
        for line in ass.read_text(encoding="utf-8").splitlines():
            if line.startswith("Style: Default"):
                margin_v = int(line.split(",")[21])
                lo = zones["captions_bottom_min"] * 1920
                hi = zones["captions_bottom_max"] * 1920
                return {"name": "captions_safe_zone", "ok": lo <= margin_v <= hi,
                        "detail": f"MarginV={margin_v} (banda {lo:.0f}-{hi:.0f})"}
        return {"name": "captions_safe_zone", "ok": False,
                "detail": "sin estilo Default"}

    def _assets_exist(self, project: Project) -> dict:
        amap_path = project.path / "assets_map.json"
        if not amap_path.exists():
            return {"name": "assets_exist", "ok": False,
                    "detail": "falta assets_map.json"}
        amap = json.loads(amap_path.read_text(encoding="utf-8"))
        missing = [v["path"] for k, v in amap.items()
                   if k.startswith("seg")
                   and not (project.path / v["path"]).exists()]
        return {"name": "assets_exist", "ok": not missing,
                "detail": ", ".join(missing)}

    # -- reporte -------------------------------------------------------------
    def _report(self, project: Project, checks: list[dict]) -> dict:
        passed = all(c["ok"] for c in checks)
        report = {"passed": passed, "checks": checks, "loop": 0,
                  "fix_applied": None}
        (project.path / "qc_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if not passed:
            failed = ", ".join(c["name"] for c in checks if not c["ok"])
            raise StageError(f"QC falló: {failed} — ver qc_report.json")
        return {"qc_report": "qc_report.json"}
