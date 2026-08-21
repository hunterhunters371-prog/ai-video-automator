"""VOICE: narración TTS con texto preprocesado para sonar natural.

Entrada: script.json (narración) + configs/voice.yml.
Salida:  assets/voice.mp3 + duración real del audio (EDITING re-sincroniza
         los tiempos del storyboard con ella).
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class VoiceStage(BaseStage):
    stage = Stage.VOICE

    def run(self, project: Project) -> dict:
        # TODO(M1): edge-tts (idioma, voz, velocidad, tono, pausas configurables).
        # Preprocesado: números en letra, siglas espaciadas, pausas naturales.
        raise NotImplementedError("M1: implementar síntesis de voz")
