"""ASSETS: resuelve los recursos de cada escena del storyboard.

Entrada: storyboard.json.
Salida:  assets_map.json + archivos en projects/<id>/assets/.
Orden de resolución por escena: (1) ruta explícita en repo/proyecto,
(2) stock de video Pexels si hay clave, (3) imagen IA gratuita (HF Inference
o Pollinations, según configs/images.yml), (4) foto de stock Pexels,
(5) fondo de color de la plantilla (siempre funciona, sin claves).
Video IA gratis: no existe API confiable sin pago — el video sale de stock
o de material del usuario.
"""
from __future__ import annotations

import base64
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
HF_URL = "https://api-inference.huggingface.co/models/{model}"
# [no verificado] endpoint exacto de la API nueva de Pollinations:
# si falla en la primera ejecución real, confirmar en https://gen.pollinations.ai/docs
POLLINATIONS_URL = "https://gen.pollinations.ai/v1/images/generations"
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
        prompt = ((seg.get("asset") or {}).get("prompt")
                  or seg.get("on_screen_text") or project.data["idea"]["text"])
        # 2. stock de video
        video = self._pexels(prompt, dest_base, videos=True)
        if video:
            return {"path": str(video.relative_to(project.path)),
                    "kind": "video", "origin": "pexels"}
        # 3. imagen IA gratuita
        ai = self._ai_image(prompt, dest_base)
        if ai:
            return {"path": str(ai.relative_to(project.path)),
                    "kind": "image",
                    "origin": f"ia:{(config.IMAGES or {}).get('provider')}"}
        # 4. foto de stock
        photo = self._pexels(prompt, dest_base, videos=False)
        if photo:
            return {"path": str(photo.relative_to(project.path)),
                    "kind": "image", "origin": "pexels"}
        # 5. fondo de color de la plantilla (determinista, sin claves)
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

    # -- proveedores ---------------------------------------------------------
    def _pexels(self, query: str, dest_base: Path, videos: bool) -> Path | None:
        if not config.PEXELS_API_KEY:
            return None
        headers = {"Authorization": config.PEXELS_API_KEY}
        try:
            if videos:
                r = requests.get(PEXELS_VIDEOS, headers=headers, timeout=30,
                                 params={"query": query, "per_page": 1,
                                         "orientation": "portrait"})
                items = r.json().get("videos", [])
                if not items:
                    return None
                files = sorted(items[0]["video_files"],
                               key=lambda f: abs(f.get("width", 0) - 1080))
                dest = dest_base.with_suffix(".mp4")
                _download(files[0]["link"], dest)
                return dest
            r = requests.get(PEXELS_PHOTOS, headers=headers, timeout=30,
                             params={"query": query, "per_page": 1,
                                     "orientation": "portrait"})
            photos = r.json().get("photos", [])
            if not photos:
                return None
            dest = dest_base.with_suffix(".jpg")
            _download(photos[0]["src"]["large2x"], dest)
            return dest
        except Exception:
            return None  # cualquier fallo de stock cae al siguiente recurso

    def _ai_image(self, prompt: str, dest_base: Path) -> Path | None:
        cfg = config.IMAGES or {}
        provider = cfg.get("provider", "off")
        width = cfg.get("width", 1080)
        height = cfg.get("height", 1920)
        try:
            if provider == "hf" and config.HF_TOKEN:
                return self._hf_image(prompt, dest_base, cfg, width, height)
            if provider == "pollinations" and config.POLLINATIONS_KEY:
                return self._pollinations_image(prompt, dest_base, cfg, width, height)
        except Exception:
            return None  # cualquier fallo de IA cae al siguiente recurso
        return None

    def _hf_image(self, prompt: str, dest_base: Path, cfg: dict,
                  width: int, height: int) -> Path | None:
        model = cfg.get("hf", {}).get("model", "black-forest-labs/FLUX.1-schnell")
        timeout = cfg.get("hf", {}).get("timeout_s", 180)
        r = requests.post(
            HF_URL.format(model=model),
            headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
            json={"inputs": f"{prompt}, vertical 9:16"},
            timeout=timeout,
        )
        if r.status_code != 200 or "image" not in r.headers.get("content-type", ""):
            return None
        dest = dest_base.with_suffix(".png")
        dest.write_bytes(r.content)
        return dest if dest.stat().st_size > 10_000 else None

    def _pollinations_image(self, prompt: str, dest_base: Path, cfg: dict,
                            width: int, height: int) -> Path | None:
        model = cfg.get("pollinations", {}).get("model", "flux")
        timeout = cfg.get("pollinations", {}).get("timeout_s", 180)
        r = requests.post(
            POLLINATIONS_URL,
            headers={"Authorization": f"Bearer {config.POLLINATIONS_KEY}"},
            json={"model": model, "prompt": prompt,
                  "size": f"{width}x{height}", "n": 1,
                  "response_format": "b64_json"},
            timeout=timeout,
        )
        if r.status_code != 200:
            return None
        data = (r.json().get("data") or [{}])[0]
        dest = dest_base.with_suffix(".png")
        if data.get("b64_json"):
            dest.write_bytes(base64.b64decode(data["b64_json"]))
        elif data.get("url"):
            _download(data["url"], dest)
        else:
            return None
        return dest if dest.stat().st_size > 10_000 else None

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
