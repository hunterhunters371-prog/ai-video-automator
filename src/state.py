"""Máquina de estados persistente de cada proyecto de video.

El estado vive en `projects/<id>/project.json` (dentro de GitHub). Después de
cada etapa se guarda un checkpoint: una interrupción o un fallo NUNCA hace
repetir trabajo ya completado.

Estados:
    IDEA → RESEARCH → SCRIPT → STORYBOARD → ASSETS → VOICE
         → EDITING → RENDERING → QC → COMPLETED
                                    ↘ FAILED (reanudable con `resume`)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Stage(str, Enum):
    IDEA = "IDEA"
    RESEARCH = "RESEARCH"
    SCRIPT = "SCRIPT"
    STORYBOARD = "STORYBOARD"
    ASSETS = "ASSETS"
    VOICE = "VOICE"
    EDITING = "EDITING"
    RENDERING = "RENDERING"
    QC = "QC"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Orden del pipeline. COMPLETED/FAILED son terminales y no se ejecutan.
PIPELINE_ORDER: list[Stage] = [
    Stage.IDEA,
    Stage.RESEARCH,
    Stage.SCRIPT,
    Stage.STORYBOARD,
    Stage.ASSETS,
    Stage.VOICE,
    Stage.EDITING,
    Stage.RENDERING,
    Stage.QC,
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Project:
    """Un proyecto = una carpeta `projects/<id>/` con su `project.json`."""

    project_id: str
    path: Path
    data: dict = field(default_factory=dict)

    # -- ciclo de vida ----------------------------------------------------
    @classmethod
    def create(cls, root: Path, project_id: str, idea: str, **meta) -> "Project":
        path = root / "projects" / project_id
        (path / "assets").mkdir(parents=True, exist_ok=True)
        data = {
            "id": project_id,
            "idea": {"text": idea, "source": meta.get("source", "user")},
            "template": meta.get("template"),
            "duration_target_s": meta.get("duration"),
            "language": meta.get("language", "es"),
            "platforms": meta.get(
                "platforms", ["youtube_shorts", "tiktok", "instagram_reels"]
            ),
            "state": Stage.IDEA.value,
            "completed": [],
            "artifacts": {},
            "attempts": {},
            "errors": [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        project = cls(project_id, path, data)
        project.save()
        return project

    @classmethod
    def load(cls, root: Path, project_id: str) -> "Project":
        path = root / "projects" / project_id
        data = json.loads((path / "project.json").read_text(encoding="utf-8"))
        return cls(project_id, path, data)

    # -- checkpoints ------------------------------------------------------
    def mark_completed(self, stage: Stage, artifacts: dict | None = None) -> None:
        if stage.value not in self.data["completed"]:
            self.data["completed"].append(stage.value)
        if artifacts:
            self.data["artifacts"].update(artifacts)
        self.data["state"] = stage.value
        self.save()

    def mark_failed(self, stage: Stage, error: str) -> None:
        """FAILED conserva TODOS los artefactos y el historial de errores."""
        self.data["state"] = Stage.FAILED.value
        self.data["errors"].append(
            {"stage": stage.value, "error": error, "at": _now()}
        )
        self.save()

    def next_stage(self) -> Stage | None:
        """Primer estado no completado: el punto exacto de reanudación."""
        for stage in PIPELINE_ORDER:
            if stage.value not in self.data["completed"]:
                return stage
        return None

    def save(self) -> None:
        self.data["updated_at"] = _now()
        (self.path / "project.json").write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
