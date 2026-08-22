# MVP — Alcance y fases

## Objetivo del MVP

Un solo comando:

```bash
python -m src.main new "Crea un Short sobre el próximo evento de Roblox"
```

produce un video vertical 9:16 (~30 s) con:

- investigación web de la idea y fuentes guardadas,
- guion corto con hook (5 opciones generadas, 1 seleccionada),
- storyboard temporal en JSON,
- recursos (stock / material del usuario / assets del repo),
- voz TTS en español con texto preprocesado para sonar natural,
- subtítulos sincronizados por palabra con resaltado de keywords,
- música de fondo y SFX,
- QC técnico automático con loop de corrección,
- y **reanudación por checkpoints** ante cualquier fallo.

## Dentro del MVP ✅

- Estructura del repo, configs, plantillas y esqueleto de código (**M0 — ya hecho en este commit base**).
- Orquestador con máquina de estados, checkpoints, timeouts, reintentos y logs.
- Etapas: research (web) → script (LLM) → storyboard (LLM→JSON) → assets (stock/usuario) → voice (edge-tts) → editing (plan + subtítulos ASS) → rendering (FFmpeg) → QC (técnico v1).
- CLI: `new`, `resume`, `status`.
- 1 plantilla funcional de punta a punta (`roblox`); las demás como YAML listo.

## Fuera del MVP ❌ (fases posteriores)

- Generación de imágenes/video con IA (la interfaz ya está definida).
- Publicación automática en YouTube/TikTok/Instagram.
- Panel de control visual.
- Integración directa con el Roblox Trend Agent (el contrato `ideas/inbox/` ya quedó especificado).
- Producción por lotes (M3), voces premium, análisis de rendimiento.

## Fases

| Fase | Contenido | Criterio de aceptación |
|---|---|---|
| **M0 — Base** | Estructura, docs, configs, plantillas, esqueleto `src/` | Repo clonado + `python -m src.main --help` funciona |
| **M1 — Pipeline mínimo** | Etapas end-to-end con plantilla `roblox` | 1 Short de ~30 s generado desde una idea; `resume` reanuda tras matar el proceso a mitad |
| **M2 — Calidad** | Subtítulos con resaltado, SFX, transiciones, las 8 plantillas activas, loop QC | QC detecta y corrige un render roto sin intervención |
| **M3 — Lotes + inbox** | `batch` con diversidad, `process-inbox` | 10 Shorts de un mismo tema, todos con ángulos distintos |
| **M4 — Ecosistema** | Trend Agent → inbox, panel básico, assets IA | Una tendencia detectada termina en video publicable sin tocar nada |

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Binarios grandes en GitHub | Git LFS para finales; `.gitignore` para material de trabajo |
| Calidad del TTS gratuito | Abstracción de proveedor; cambiar a ElevenLabs/OpenAI es solo config |
| Duración real ≠ objetivo | El storyboard se recalcula con la duración real del audio TTS |
| Licencias de música/gameplay | Solo biblioteca licenciada o material propio en `assets/` |
| Coste/límites de APIs | Reintentos con backoff + caché de assets compartida en lotes |

## Qué se necesita para M1

1. `ffmpeg` instalado en la máquina que ejecute el pipeline.
2. Una clave de LLM (OpenAI o Anthropic) en `.env`.
3. (Opcional) clave de Pexels para stock; si no, usar material propio en `assets/`.

## Estado (22 ago 2026)

- M0 ✅ (commit base).
- M1: las 8 etapas + `status` del CLI implementadas en código (capa
  `src/config.py` + `src/llm.py` + `src/websearch.py`; etapas research → qc).
- **Verificado en sandbox** (sin red, ffmpeg 7.0 real): sintaxis completa,
  funciones puras (números en letra, preprocesado TTS, parseo de tiempos,
  ASS/SRT con resaltado y safe zones, resync con duración real, parseo JSON
  del LLM) y RENDERING + QC end-to-end: render 1080x1920@30 con voz y
  subtítulos incrustados, QC en verde, render idempotente. Dos bugs
  encontrados por la prueba y corregidos: fps de salida salía a 25 (ahora
  normalización final explícita) y falso positivo de pantalla negra con el
  fondo oscuro de plantilla (blackdetect pix_th 0.10 → 0.04).
- Aún **[no verificado]** (requieren red o claves): research (web + LLM),
  script y storyboard (LLM), voice (edge-tts), whisper en editing, y los
  proveedores de assets (Pexels / HF Inference / Pollinations; el endpoint
  de Pollinations sigue marcado [no verificado]).
- ASSETS con imágenes IA gratuitas: proveedores sin tarjeta (HF Inference
  con `HF_TOKEN`, Pollinations con `POLLINATIONS_KEY`; ver
  `configs/images.yml`). Orden por escena: ruta explícita → video stock →
  imagen IA → foto stock → fondo de color.
