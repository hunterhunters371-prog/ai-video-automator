"""EDITING: plan de edición + subtítulos.

Entrada: storyboard.json + voice.mp3 + assets.
Salida:  edit_plan.json (filtergraph FFmpeg: cortes, zoom/pan, transiciones,
         música con ducking, SFX en beats, cambios visuales en palabras clave)
         y subtitles.ass/.srt (whisper → tiempos por palabra, grupos de 2-4
         palabras, keywords resaltadas, posición en safe zones).
Prioridad: ritmo y retención — corte visual cada 2-4 s, nunca imágenes
estáticas en secuencia.
"""
from __future__ import annotations

from ..state import Project, Stage
from .base import BaseStage


class EditingStage(BaseStage):
    stage = Stage.EDITING

    def run(self, project: Project) -> dict:
        # TODO(M1/M2): faster-whisper → ASS; generar edit_plan.json desde el
        # storyboard re-sincronizado con la duración real del audio.
        raise NotImplementedError("M1: implementar plan de edición y subtítulos")
