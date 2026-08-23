"""Carga de configuración: .env + configs/*.yml + plantillas.

Punto único de acceso: cualquier etapa importa `config` y lee lo suyo.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


def load_yaml(rel: str) -> dict:
    with open(ROOT / rel, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


PIPELINE = load_yaml("configs/pipeline.yml")
PLATFORMS = load_yaml("configs/platforms.yml")
VOICE = load_yaml("configs/voice.yml")
IMAGES = load_yaml("configs/images.yml")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
GITHUB_MODELS_TOKEN = os.getenv("GITHUB_MODELS_TOKEN", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
POLLINATIONS_KEY = os.getenv("POLLINATIONS_KEY", "")
# Alibaba Cloud Model Studio (Wan): clips de video por API. La clave tiene que
# ser de la región Singapur, que es la única con cuota gratis internacional.
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


def load_template(name: str) -> dict:
    return load_yaml(f"templates/{name}/template.yml")


def list_templates() -> list[str]:
    base = ROOT / "templates"
    return sorted(p.name for p in base.iterdir() if (p / "template.yml").exists())
