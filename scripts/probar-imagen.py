#!/usr/bin/env python3
"""Prueba la generación de imágenes IA sin correr el pipeline completo.

Uso:
    python scripts/probar-imagen.py
    python scripts/probar-imagen.py "un estadio de Roblox con luces neón"

Llama al MISMO código que usa la etapa ASSETS (no a una copia): si esto sale
en verde, la próxima corrida generará imágenes reales en vez de fondos de color.
Nunca imprime el token: solo su longitud.

Salida: 0 si generó imagen, 1 si ASSETS caería al fondo de color.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config  # noqa: E402
from src.stages.assets import AssetsStage  # noqa: E402


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "un estadio de Roblox con luces neón"
    cfg = config.IMAGES or {}
    modelos = (cfg.get("hf") or {}).get("models") or []
    print(f"proveedor : {cfg.get('provider')}")
    print(f"modelos   : {', '.join(modelos) if modelos else '(ninguno)'}")
    print(f"HF_TOKEN  : {len(config.HF_TOKEN)} caracteres"
          + ("" if config.HF_TOKEN else "  <-- VACÍO: corre  sh setup-env.sh"))
    print(f"prompt    : {prompt}")
    print("-- intentos --")

    stage = AssetsStage()
    dest_base = Path(tempfile.mkdtemp(prefix="prueba-imagen-")) / "prueba"
    # A propósito se llama al método interno: es el mismo camino que ASSETS.
    imagen = stage._ai_image(prompt, dest_base)

    print("-- resultado --")
    if imagen is None:
        print("✗ sin imagen IA: ASSETS caería al fondo de color.")
        print("  Revisa los motivos de arriba (token, permiso de inferencia,")
        print("  o modelo sin proveedor vivo en configs/images.yml).")
        return 1
    print(f"✓ imagen generada: {imagen} ({imagen.stat().st_size} bytes)")
    print("  ASSETS usará imágenes IA en la próxima corrida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
