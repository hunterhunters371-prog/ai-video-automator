"""ASSETS: resuelve los recursos de cada escena del storyboard.

Entrada: storyboard.json.
Salida:  assets_map.json + archivos en projects/<id>/assets/.
Orden de resolución por escena: (1) ruta explícita en repo/proyecto,
(2) stock Pexels si hay clave, (3) fondo de color de la plantilla (siempre
funciona, sin claves). Imagen IA: interfaz en ARQUITECTURA.md §6, fase posterior.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import requests

from .. import config
from ..state import Project, Stage
from .base import BaseStage, StageError

PEXELS_VIDEOS = "https://api.pexels.com/videos/search"
PEXELS_PHOTOS = "https://api.pexels.com/v1/search"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a"}


def _kind(path: Path) -> str:
    if path.suffix.lower() in VIDEO_EXT:
        return "video"
    if path.suffix.lower() in AUDIO_EXT:
        return "audio"
    return "image"


def _download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


class AssetsStage(BaseStage):
    stage = Stage.ASSETS

    def run(self, project: Project) -> dict:
        board = json.loads((project.path / "storyboard.json").read_text(encoding="utf-8"))
        template = config.load_template(board.get("template") or "roblox")
        assets_dir = project.path / "assets"
        assets_dir.mkdir(exist_ok=True)

        amap_path = project.path / "assets_map.json"
        amap = json.loads(amap_path.read_text(encoding="utf-8")) if amap_path.exists() else {}

        for i, seg in enumerate(board["segments"]):
            key = f"seg{i:02d}"
            if key in amap and (project.path / amap[key]["path"]).exists():
                continue  # idempotente
            amap[key] = self._resolve(project, seg, assets_dir / key, template)

        music = self._music(project, assets_dir)
        if music:
            amap["music"] = music
        amap_path.write_text(json.dumps(amap, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"assets_map": "assets_map.json"}

    # -- resolución por escena --------------------------------------------
    def _resolve(self, project: Project, seg: dict, dest_base: Path, template: dict) -> dict:
        # 1. ruta explícita (material del usuario o recursos del repo)
        src = (seg.get("asset") or {}).get("src")
        if src:
            for candidate in (project.path / src, config.ROOT / src):
                if candidate.exists():
                    dest = dest_base.with_suffix(candidate.suffix)
                    shutil.copy2(candidate, dest)
                    return {"path": str(dest.relative_to(project.path)),
                            "kind": _kind(dest), "origin": "repo"}
        # 2. stock Pexels (opcional)
        prompt = ((seg.get("asset") or {}).get("prompt")
                  or seg.get("on_screen_text") or project.data["idea"]["text"])
        found = self._pexels(prompt, dest_base)
        if found:
            return {"path": str(found.relative_to(project.path)),
                    "kind": _kind(found), "origin": "pexels"}
        # 3. fondo de color de la plantilla (determinista, sin claves)
        dest = dest_base.with_suffix(".png")
        bg = (template.get("style", {}).get("colors", {}).get("background")
              or "#0E0E10").lstrip("#")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x{bg}:s=1080x1920",
                 "-frames:v", "1", str(dest)],
                check=True, capture_output=True,
            )
        except FileNotFoundError as exc:
            raise StageError("ffmpeg no encontrado: instálalo (docs/SETUP.md §1)") from exc
        return {"path": str(dest.relative_to(project.path)),
                "kind": "image", "origin": "fallback_color"}

    def _pexels(self, query: str, dest_base: Path) -> Path | None:
        if not config.PEXELS_API_KEY:
            return None
        headers = {"Authorization": config.PEXELS_API_KEY}
        try:
            r = requests.get(PEXELS_VIDEOS, headers=headers, timeout=30,
                             params={"query": query, "per_page": 1,
                                     "orientation": "portrait"})
            videos = r.json().get("videos", [])
            if videos:
                files = sorted(videos[0]["video_files"],
                               key=lambda f: abs(f.get("width", 0) - 1080))
                dest = dest_base.with_suffix(".mp4")
                _download(files[0]["link"], dest)
                return dest
            r = requests.get(PEXELS_PHOTOS, headers=headers, timeout=30,
                             params={"query": query, "per_page": 1,
                                     "orientation": "portrait"})
            photos = r.json().get("photos", [])
            if photos:
                dest = dest_base.with_suffix(".jpg")
                _download(photos[0]["src"]["large2x"], dest)
                return dest
        except Exception:
            return None  # cualquier fallo de stock cae al fondo de color
        return None

    def _music(self, project: Project, assets_dir: Path) -> dict | None:
        lib = config.ROOT / "assets" / "music"
        if not lib.exists():
            return None
        for track in sorted(lib.iterdir()):
            if track.suffix.lower() in AUDIO_EXT:
                dest = assets_dir / f"music{track.suffix}"
                if not dest.exists():
                    shutil.copy2(track, dest)
                return {"path": str(dest.relative_to(project.path)),
                        "kind": "audio", "origin": "repo"}
        return None
