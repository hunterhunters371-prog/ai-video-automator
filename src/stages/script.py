"""SCRIPT: guion optimizado para contenido corto.

Entrada: research.md.
Salida:  script.json — 5 hooks (se selecciona el más fuerte), narración
         preparada para TTS, beats con duración máxima, CTA solo si aporta.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class ScriptStage(BaseStage):
    stage = Stage.SCRIPT

    def run(self, project: Project) -> dict:
        # TODO(M1): LLM genera hook(1-3s) → desarrollo rápido → dato principal
        # → sorpresa/curiosidad → cierre. Sin introducciones largas.
        raise NotImplementedError("M1: implementar generación de guion y hooks")
