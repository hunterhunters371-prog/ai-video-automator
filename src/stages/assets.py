"""ASSETS: resuelve los recursos de cada escena del storyboard.

Entrada: storyboard.json.
Salida:  assets_map.json + archivos en projects/<id>/assets/.
Orden de resolución por escena: (1) ruta explícita en repo/proyecto,
(2) stock de video Pexels si hay clave, (3) imagen IA gratuita (Inference
Providers de HF o Pollinations, según configs/images.yml), (4) foto de stock
Pexels, (5) fondo de color de la plantilla (siempre funciona, sin claves).
Video IA gratis: no existe API confiable sin pago — el video sale de stock
o de material del usuario.

Nota (22 ago 2026): ningún fallo de proveedor se traga en silencio. Cada
recurso descartado deja motivo en stdout y en assets_map.json["_warnings"].
Sin eso, un pipeline "en verde" puede haber caído a fondos de color sin avisar
— fue exactamente lo que pasó con video-0001.
"""
from __future__ import annotations

import base64
import io
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
# api-inference.huggingface.co MURIÓ: HF movió la inferencia al router de
# Inference Providers y cada modelo lo sirve un proveedor distinto (doc oficial:
# huggingface.co/docs/inference-providers/tasks/text-to-image). Por eso la vía
# preferida es el SDK huggingface_hub, que enruta solo; las rutas HTTP de
# respaldo se declaran en configs/images.yml (hf.router_bases).
POLLINATIONS_URL = "https://gen.pollinations.ai/v1/images/generations"  # [no verificado]
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a"}
MIN_IMAGE_BYTES = 10_000


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

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def _warn(self, msg: str) -> None:
        """Motivo por el que se descartó un recurso. Nunca en silencio."""
        if msg not in self.warnings:
            self.warnings.append(msg)
            print(f"    [!] {msg}", flush=True)

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

        origins = [v["origin"] for k, v in amap.items()
                   if k.startswith("seg") and isinstance(v, dict)]
        fallbacks = sum(1 for o in origins if o == "fallback_color")
        if origins and fallbacks == len(origins):
            self._warn(f"TODAS las escenas ({fallbacks}) usan fondo de color: "
                       "revisa los motivos de arriba antes de publicar el video")
        if origins:
            resumen = ", ".join(f"{o}x{origins.count(o)}" for o in sorted(set(origins)))
            print(f"    escenas: {len(origins)} · {resumen}", flush=True)

        amap["_warnings"] = list(self.warnings)
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
            self._warn(f"asset explícito no encontrado: {src}")
        prompt = ((seg.get("asset") or {}).get("prompt")
                  or seg.get("on_screen_text") or project.data["idea"]["text"])
        # 2. stock de video
        video = self._pexels(prompt, dest_base, videos=True)
        if video:
            return {"path": str(video.relative_to(project.path)),
                    "kind": "video", "origin": "pexels"}
        # 3. imagen IA gratuita
        try:
            ai = self._ai_image(prompt, dest_base)
        except Exception as exc:  # degradar con gracia, pero dejando el motivo
            self._warn(f"IA imagen: error inesperado {type(exc).__name__}: {exc}")
            ai = None
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
            self._warn("PEXELS_API_KEY vacía: sin video ni foto de stock "
                       "(clave gratis en docs/SETUP.md §3)")
            return None
        headers = {"Authorization": config.PEXELS_API_KEY}
        tipo = "video" if videos else "foto"
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
        except Exception as exc:  # cualquier fallo de stock cae al siguiente recurso
            self._warn(f"Pexels {tipo}: {type(exc).__name__}: {str(exc)[:160]}")
            return None

    def _ai_image(self, prompt: str, dest_base: Path) -> Path | None:
        cfg = config.IMAGES or {}
        provider = cfg.get("provider", "off")
        width = int(cfg.get("width", 1080))
        height = int(cfg.get("height", 1920))
        if provider == "off":
            return None
        if provider == "hf":
            if not config.HF_TOKEN:
                self._warn("images.yml pide 'hf' pero HF_TOKEN está vacío "
                           "(corre: sh setup-env.sh)")
                return None
            return self._hf_image(prompt, dest_base, cfg, width, height)
        if provider == "pollinations":
            if not config.POLLINATIONS_KEY:
                self._warn("images.yml pide 'pollinations' pero POLLINATIONS_KEY está vacía")
                return None
            return self._pollinations_image(prompt, dest_base, cfg, width, height)
        self._warn(f"images.yml: proveedor de imagen desconocido {provider!r} "
                   "(usa hf | pollinations | off)")
        return None

    def _hf_image(self, prompt: str, dest_base: Path, cfg: dict,
                  width: int, height: int) -> Path | None:
        """Intenta cada modelo de configs/images.yml: primero por SDK, luego HTTP."""
        hf_cfg = cfg.get("hf") or {}
        models = hf_cfg.get("models") or ([hf_cfg["model"]] if hf_cfg.get("model") else [])
        if not models:
            self._warn("images.yml: hf.models está vacío")
            return None
        timeout = int(hf_cfg.get("timeout_s", 180))
        full_prompt = f"{prompt}, vertical 9:16"
        dest = dest_base.with_suffix(".png")
        for model in models:
            data = (self._hf_sdk_image(full_prompt, model, width, height, timeout)
                    or self._hf_http_image(full_prompt, model, hf_cfg, timeout))
            if not data:
                continue
            dest.write_bytes(data)
            size = dest.stat().st_size
            if size > MIN_IMAGE_BYTES:
                return dest
            self._warn(f"IA imagen {model}: solo {size} bytes "
                       f"(< {MIN_IMAGE_BYTES}), descartada")
        return None

    def _hf_sdk_image(self, prompt: str, model: str, width: int, height: int,
                      timeout: int) -> bytes | None:
        """Vía preferida: el SDK enruta al proveedor vivo de cada modelo.

        Doc oficial: huggingface.co/docs/inference-providers (Quick Start
        text-to-image). Requiere huggingface_hub + Pillow (requirements.txt).
        """
        try:
            from huggingface_hub import InferenceClient
        except ImportError:
            self._warn("huggingface_hub no instalado: pip install -r requirements.txt")
            return None
        try:
            client = InferenceClient(api_key=config.HF_TOKEN, timeout=timeout)
        except Exception as exc:
            self._warn(f"IA imagen SDK: no se pudo crear el cliente "
                       f"({type(exc).__name__}: {str(exc)[:120]})")
            return None
        # Algunos proveedores rechazan width/height: reintento sin tamaño.
        for extra in ({"width": width, "height": height}, {}):
            etiqueta = "con tamaño" if extra else "sin tamaño"
            try:
                image = client.text_to_image(prompt, model=model, **extra)
            except Exception as exc:
                self._warn(f"IA imagen SDK {model} ({etiqueta}): "
                           f"{type(exc).__name__}: {str(exc)[:180]}")
                continue
            try:
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                return buf.getvalue()
            except Exception as exc:
                self._warn(f"IA imagen SDK {model}: no se pudo serializar "
                           f"({type(exc).__name__})")
                return None
        return None

    def _hf_http_image(self, prompt: str, model: str, hf_cfg: dict,
                       timeout: int) -> bytes | None:
        """Respaldo sin SDK: POST a las rutas del router de configs/images.yml.

        Formato oficial de la tarea text-to-image: {"inputs": ...} → bytes de
        imagen. Un 404/410 aquí significa que ESE proveedor no sirve ESE modelo.
        """
        for base in hf_cfg.get("router_bases") or []:
            url = f"{str(base).rstrip('/')}/{model}"
            try:
                r = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {config.HF_TOKEN}"},
                    json={"inputs": prompt},
                    timeout=timeout,
                )
            except Exception as exc:
                self._warn(f"IA imagen HTTP {url}: {type(exc).__name__}")
                continue
            if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
                return r.content
            self._warn(f"IA imagen HTTP {url}: HTTP {r.status_code} · {r.text[:120]}")
        return None

    def _pollinations_image(self, prompt: str, dest_base: Path, cfg: dict,
                            width: int, height: int) -> Path | None:
        poll_cfg = cfg.get("pollinations") or {}
        model = poll_cfg.get("model", "flux")
        timeout = int(poll_cfg.get("timeout_s", 180))
        try:
            r = requests.post(
                POLLINATIONS_URL,
                headers={"Authorization": f"Bearer {config.POLLINATIONS_KEY}"},
                json={"model": model, "prompt": prompt,
                      "size": f"{width}x{height}", "n": 1,
                      "response_format": "b64_json"},
                timeout=timeout,
            )
        except Exception as exc:
            self._warn(f"Pollinations: {type(exc).__name__}: {str(exc)[:160]}")
            return None
        if r.status_code != 200:
            self._warn(f"Pollinations HTTP {r.status_code}: {r.text[:120]} "
                       "(endpoint [no verificado]: confirmar en gen.pollinations.ai/docs)")
            return None
        try:
            data = (r.json().get("data") or [{}])[0]
        except Exception:
            self._warn("Pollinations: la respuesta no trae JSON con 'data'")
            return None
        dest = dest_base.with_suffix(".png")
        if data.get("b64_json"):
            dest.write_bytes(base64.b64decode(data["b64_json"]))
        elif data.get("url"):
            _download(data["url"], dest)
        else:
            self._warn("Pollinations: sin b64_json ni url en la respuesta")
            return None
        size = dest.stat().st_size
        if size > MIN_IMAGE_BYTES:
            return dest
        self._warn(f"Pollinations: imagen de {size} bytes, descartada")
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
