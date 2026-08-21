"""QC: control de calidad con loop de corrección.

Entrada: renders/<id>.mp4.
Salida:  qc_report.json → COMPLETED, o corrección del plan y re-render.

Checks técnicos v1: existe, tiene audio, duración ±1.5s, resolución/fps,
pantallas negras (blackdetect), congelados (freezedetect), volumen (loudnorm),
subtítulos dentro de safe zones, assets disponibles.
Si falla: corregir → volver a renderizar → volver a validar (máx. 3 loops).
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class QCStage(BaseStage):
    stage = Stage.QC
    max_retries = 1

    def run(self, project: Project) -> dict:
        # TODO(M1): ffprobe/ffmpeg checks → qc_report.json.
        # TODO(M2): loop de corrección asistido por LLM.
        # Futuro (v2): QC semántico — VLM compara narración vs imagen.
        raise NotImplementedError("M1: implementar control de calidad")
