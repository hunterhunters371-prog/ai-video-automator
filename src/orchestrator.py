"""Orquestador: ejecuta el pipeline con checkpoints, reintentos y reanudación.

Responsabilidades:
  - Crear proyectos y asignar IDs (video-0001, video-0002, ...).
  - Ejecutar etapas en orden guardando checkpoint tras cada una.
  - Reanudar desde el último estado completado (`resume`).
  - Registrar errores sin destruir el trabajo realizado.
"""
from __future__ import annotations

from pathlib import Path

from .state import PIPELINE_ORDER, Project, Stage
from .stages.assets import AssetsStage
from .stages.editing import EditingStage
from .stages.qc import QCStage
from .stages.rendering import RenderingStage
from .stages.research import ResearchStage
from .stages.script import ScriptStage
from .stages.storyboard import StoryboardStage
from .stages.voice import VoiceStage

STAGE_REGISTRY = {
    Stage.RESEARCH: ResearchStage,
    Stage.SCRIPT: ScriptStage,
    Stage.STORYBOARD: StoryboardStage,
    Stage.ASSETS: AssetsStage,
    Stage.VOICE: VoiceStage,
    Stage.EDITING: EditingStage,
    Stage.RENDERING: RenderingStage,
    Stage.QC: QCStage,
}


class Orchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_repo_root(cls) -> "Orchestrator":
        return cls(Path(__file__).resolve().parent.parent)

    # -- comandos públicos -------------------------------------------------
    def create_and_run(
        self, idea: str, template: str | None = None, duration: int | None = None
    ) -> Project:
        project_id = self._next_id()
        project = Project.create(
            self.root, project_id, idea, template=template, duration=duration
        )
        project.mark_completed(Stage.IDEA)
        self._run_pipeline(project)
        return project

    def resume(self, project_id: str) -> Project:
        """RESUME VIDEO #NNN → continúa desde el primer estado no completado."""
        project = Project.load(self.root, project_id)
        self._run_pipeline(project)
        return project

    def status(self, project_id: str | None = None) -> None:
        # TODO(M1): tabla con estado, progreso, errores y duración por proyecto.
        raise NotImplementedError("M1: panel de estado por consola")

    def batch(self, source: str, count: int = 10) -> None:
        # TODO(M3): matriz de diversidad (subtema × ángulo × plantilla × duración)
        # + deduplicación por similitud + proyectos independientes por idea.
        raise NotImplementedError("M3: producción por lotes")

    def process_inbox(self) -> None:
        # TODO(M3): leer ideas/inbox/*.json, crear proyectos y mover a
        # ideas/processed/. Contrato definido en docs/ARQUITECTURA.md §3.2.
        raise NotImplementedError("M3: integración con el agente de tendencias")

    # -- núcleo -------------------------------------------------------------
    def _run_pipeline(self, project: Project) -> None:
        """Ejecuta desde el primer estado pendiente. Checkpoint tras cada etapa."""
        while True:
            stage = project.next_stage()
            if stage is None:
                project.data["state"] = Stage.COMPLETED.value
                project.save()
                return
            runner = STAGE_REGISTRY.get(stage)
            if runner is None:  # IDEA se marca al crear el proyecto
                project.mark_completed(stage)
                continue
            try:
                artifacts = runner().run_with_retry(project)
            except Exception as exc:  # registrar y conservar TODO el trabajo
                project.mark_failed(stage, str(exc))
                raise
            project.mark_completed(stage, artifacts)

    def _next_id(self) -> str:
        projects = self.root / "projects"
        existing = sorted(p.name for p in projects.glob("video-*"))
        n = int(existing[-1].split("-")[1]) + 1 if existing else 1
        return f"video-{n:04d}"
