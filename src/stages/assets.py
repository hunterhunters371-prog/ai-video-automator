"""ASSETS: genera o recopila los recursos de cada escena.

Entrada: storyboard.json.
Salida:  archivos dentro de projects/<id>/assets/ (imágenes IA, gameplay,
         capturas, material del usuario, recursos del repo, stock, música,
         SFX). El agente decide qué recurso necesita cada escena.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class AssetsStage(BaseStage):
    stage = Stage.ASSETS

    def run(self, project: Project) -> dict:
        # TODO(M1): resolver assets stock/usuario/repo. Imagen IA: interfaz
        # definida en docs/ARQUITECTURA.md §6, implementación en fase posterior.
        raise NotImplementedError("M1: implementar recopilación de recursos")
