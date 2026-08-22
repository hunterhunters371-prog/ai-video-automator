"""Orquestador: ejecuta el pipeline con checkpoints, reintentos y reanudación.

Responsabilidades:
  - Crear proyectos y asignar IDs (video-0001, video-0002, ...).
  - Ejecutar etapas en orden guardando checkpoint tras cada una.
  - Reanudar desde el último estado completado (`resume`).
  - Registrar errores sin destruir el trabajo realizado.
  - Log por proyecto en logs/<id>.log y progreso visible en consola.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
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

# Etapas que tardan y no imprimen nada por su cuenta: se avisa antes de entrar
# para que un silencio largo no parezca un cuelgue.
STAGE_HINTS = {
    Stage.EDITING: "la 1ª vez baja el modelo whisper (~150 MB): son minutos, es normal",
    Stage.ASSETS: "descarga/genera un recurso por escena",
    Stage.RENDERING: "ffmpeg montando el video final",
}


class Orchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_repo_root(cls) -> "Orchestrator":
        return cls(Path(__file__).resolve().parent.parent)

    # -- comandos públicos --------------------------------------------------
    def create_and_run(
        self, idea: str, template: str | None = None, duration: int | None = None
    ) -> Project:
        project_id = self._next_id()
        project = Project.create(
            self.root, project_id, idea, template=template, duration=duration
        )
        project.mark_completed(Stage.IDEA)
        self._log(project, f"IDEA: {idea!r}")
        print(f"proyecto {project_id} creado · idea: {idea}", flush=True)
        self._run_pipeline(project)
        return project

    def resume(self, project_id: str) -> Project:
        """RESUME VIDEO #NNN → continúa desde el primer estado no completado."""
        project = Project.load(self.root, project_id)
        pendiente = project.next_stage()
        self._log(project, f"resume desde {pendiente}")
        if pendiente is None:
            print(f"{project_id} ya estaba COMPLETED: no hay nada que reanudar.",
                  flush=True)
        else:
            print(f"reanudando {project_id} desde {pendiente.value}", flush=True)
        self._run_pipeline(project)
        return project

    def status(self, project_id: str | None = None) -> None:
        if project_id:
            data = Project.load(self.root, project_id).data
            print(f"{data['id']} · {data['state']} · "
                  f"{len(data['completed'])}/{len(PIPELINE_ORDER)} etapas")
            print(f"idea: {data['idea']['text']}")
            for key, val in data["artifacts"].items():
                print(f"  ✓ {key}: {val}")
            for err in data["errors"]:
                print(f"  ✗ {err['stage']}: {err['error'][:120]}")
            if data["errors"] and data["state"] == Stage.COMPLETED.value:
                print("  (los ✗ son intentos anteriores ya superados: el estado "
                      "actual es COMPLETED)")
            return
        rows = []
        for pj in sorted((self.root / "projects").glob("video-*/project.json")):
            rows.append(json.loads(pj.read_text(encoding="utf-8")))
        if not rows:
            print('Sin proyectos. Crea uno: python -m src.main new "<idea>"')
            return
        for data in rows:
            bar = " ".join(
                ("✓" if st.value in data["completed"] else "·") for st in PIPELINE_ORDER
            )
            print(f"{data['id']}  {data['state']:<10} {bar}  "
                  f"{data['idea']['text'][:38]}")

    def batch(self, source: str, count: int = 10) -> None:
        # TODO(M3): matriz de diversidad (subtema × ángulo × plantilla × duración)
        # + deduplicación por similitud + proyectos independientes por idea.
        raise NotImplementedError("M3: producción por lotes")

    def process_inbox(self) -> None:
        # TODO(M3): leer ideas/inbox/*.json, crear proyectos y mover a
        # ideas/processed/. Contrato definido en docs/ARQUITECTURA.md §3.2.
        raise NotImplementedError("M3: integración con el agente de tendencias")

    # -- núcleo ---------------------------------------------------------------
    def _run_pipeline(self, project: Project) -> None:
        """Ejecuta desde el primer estado pendiente. Checkpoint tras cada etapa."""
        while True:
            stage = project.next_stage()
            if stage is None:
                project.data["state"] = Stage.COMPLETED.value
                project.save()
                self._log(project, "COMPLETED")
                render = self.root / "renders" / f"{project.project_id}.mp4"
                sufijo = f" → {render}" if render.exists() else ""
                print(f"COMPLETED {project.project_id}{sufijo}", flush=True)
                return
            runner = STAGE_REGISTRY.get(stage)
            if runner is None:  # IDEA se marca al crear el proyecto
                project.mark_completed(stage)
                continue
            self._log(project, f"> {stage.value}")
            pista = STAGE_HINTS.get(stage)
            print(f"> {stage.value}" + (f"  ({pista})" if pista else ""), flush=True)
            inicio = time.monotonic()
            try:
                artifacts = runner().run_with_retry(project)
            except Exception as exc:  # registrar y conservar TODO el trabajo
                project.mark_failed(stage, str(exc))
                self._log(project, f"x {stage.value}: {exc}")
                print(f"x {stage.value} falló tras {time.monotonic() - inicio:.1f}s: "
                      f"{exc}", flush=True)
                print(f"  el trabajo previo se conserva: "
                      f"python -m src.main resume {project.project_id}", flush=True)
                raise
            project.mark_completed(stage, artifacts)
            self._log(project, f"ok {stage.value}")
            print(f"  ok {stage.value} ({time.monotonic() - inicio:.1f}s)", flush=True)

    def _log(self, project: Project, msg: str) -> None:
        logs = self.root / "logs"
        logs.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(logs / f"{project.project_id}.log", "a", encoding="utf-8") as fh:
            fh.write(f"{ts} {msg}\n")

    def _next_id(self) -> str:
        projects = self.root / "projects"
        existing = sorted(p.name for p in projects.glob("video-*"))
        n = int(existing[-1].split("-")[1]) + 1 if existing else 1
        return f"video-{n:04d}"
