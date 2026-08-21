"""Interfaz común de todas las etapas del pipeline.

Contrato de cada etapa:
  1. Lee los artefactos que necesita del proyecto (idempotente: si su artefacto
     ya existe y es válido, no repite trabajo).
  2. Ejecuta con timeout y reintentos (`run_with_retry`).
  3. Devuelve los artefactos generados (rutas relativas a `projects/<id>/`).
"""
from __future__ import annotations

import time

from ..state import Project, Stage


class StageError(Exception):
    """Error de etapa: se registra en project.json y el proyecto pasa a FAILED."""


class BaseStage:
    stage: Stage
    timeout_s: int = 300
    max_retries: int = 2
    backoff_s: float = 5.0

    def run(self, project: Project) -> dict:
        raise NotImplementedError

    def run_with_retry(self, project: Project) -> dict:
        # `attempts` se persiste: una interrupción no reinicia el conteo.
        start = project.data["attempts"].get(self.stage.value, 0)
        for i in range(start, start + self.max_retries + 1):
            project.data["attempts"][self.stage.value] = i
            project.save()
            try:
                # TODO(M1): timeout real (subprocess/signal según plataforma)
                return self.run(project)
            except Exception:
                if i >= start + self.max_retries:
                    raise
                time.sleep(self.backoff_s * (2 ** (i - start)))
        raise StageError(f"{self.stage.value}: agotados los reintentos")
