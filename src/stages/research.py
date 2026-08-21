"""RESEARCH: investiga la idea y selecciona el formato.

Entrada: idea del proyecto.
Salida:  research.md (fuentes + datos clave), plantilla y duración elegidas.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class ResearchStage(BaseStage):
    stage = Stage.RESEARCH

    def run(self, project: Project) -> dict:
        # TODO(M1): búsqueda web → research.md con fuentes; LLM elige plantilla
        # (templates/<n>/template.yml) y duración objetivo según la densidad
        # de información y los límites de configs/platforms.yml.
        raise NotImplementedError("M1: implementar investigación y selección de formato")
