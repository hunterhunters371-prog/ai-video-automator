"""Prueba de humo de Wan: un clip de 2 s antes de gastar la cuota entera.

    python scripts/probar-wan.py [ruta_imagen]

Sin argumento busca una imagen en projects/*/refs/ y, si no hay, en
projects/*/assets/. Gasta ~2 s de los 50 s gratis y deja el mp4 en
/tmp/prueba-wan.mp4 para que lo puedas descargar y mirar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, wan  # noqa: E402

PROMPT = (
    "3D Pixar-style animated shot, vertical 9:16. The character from the image "
    "talks to the camera with an exaggerated jealous telenovela performance: "
    "the mouth moves continuously as if speaking, very expressive eyes, small "
    "head tilt. Keep exactly the same character design and colors as the input "
    "image. One single continuous shot, slow subtle camera push-in."
)


def _buscar() -> Path | None:
    raiz = config.ROOT / "projects"
    if not raiz.exists():
        return None
    for patron in ("*/refs/*", "*/assets/*"):
        for cand in sorted(raiz.glob(patron), reverse=True):
            if cand.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                return cand
    return None


def main() -> int:
    if not config.DASHSCOPE_API_KEY:
        print("DASHSCOPE_API_KEY vacía. Pasos: docs/wan-alibaba.md")
        return 1
    imagen = Path(sys.argv[1]) if len(sys.argv) > 1 else _buscar()
    if not imagen or not imagen.exists():
        print("No encuentro ninguna imagen. Pásame una:")
        print("    python scripts/probar-wan.py projects/video-0004/refs/limon.png")
        return 1

    cfg = (config.PIPELINE.get("animate") or {}).get("wan") or {}
    modelo = str(cfg.get("modelo", "wan2.6-i2v-flash"))
    resolucion = wan.resolucion_valida(modelo, str(cfg.get("resolucion", "1080P")))
    dest = Path("/tmp/prueba-wan.mp4")
    print(f"imagen : {imagen}")
    print(f"modelo : {modelo} · {resolucion} · 2 s")
    print("tarda de 1 a 5 minutos; se consulta cada 15 s ...")
    try:
        r = wan.generar(
            modelo=modelo, prompt=PROMPT, imagen=imagen, dest=dest,
            resolucion=resolucion, segundos=2,
            negativo="on-screen text, watermark, deformed face, low quality",
        )
    except wan.WanError as exc:
        print(f"\nFALLO: {exc}")
        print("\nSi dice InvalidApiKey o similar: la clave tiene que ser de la")
        print("región Singapur; una de Pekín no vale contra este dominio.")
        return 1
    print(f"\nOK · {dest} · {dest.stat().st_size // 1024} KB · "
          f"{r['segundos']:.0f}s de cuota")
    print("Descárgalo para verlo:  cloudshell download /tmp/prueba-wan.mp4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
