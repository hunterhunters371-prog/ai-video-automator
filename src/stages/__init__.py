"""Etapas del pipeline. Cada etapa extiende `BaseStage`."""
from .base import BaseStage, StageError

__all__ = ["BaseStage", "StageError"]
