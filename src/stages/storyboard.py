"""STORYBOARD: convierte el guion en segmentos temporales.

Entrada: script.json + plantilla.
Salida:  storyboard.json — por segmento: duración, narración, texto en
         pantalla, asset (tipo+prompt/ruta), animación, transición, SFX.
         Este JSON es la única fuente de verdad de la edición.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class StoryboardStage(BaseStage):
    stage = Stage.STORYBOARD

    def run(self, project: Project) -> dict:
        # TODO(M1): LLM → storyboard.json (ver projects/_ejemplo/storyboard.json)
        raise NotImplementedError("M1: implementar storyboard automático")
