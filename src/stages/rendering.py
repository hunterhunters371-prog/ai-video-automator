"""RENDERING: construye el video final vertical 9:16.

Entrada: edit_plan.json.
Salida:  renders/<id>.mp4 (1080x1920, fps de plantilla) + thumbnails/<id>.png.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class RenderingStage(BaseStage):
    stage = Stage.RENDERING
    timeout_s = 900

    def run(self, project: Project) -> dict:
        # TODO(M1): ejecutar FFmpeg con el edit_plan; exportar miniatura.
        raise NotImplementedError("M1: implementar render con FFmpeg")
