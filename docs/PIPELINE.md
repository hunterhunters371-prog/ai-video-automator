# Pipeline — especificación por etapa

Cada etapa implementa `BaseStage` (`src/stages/base.py`): lee artefactos del proyecto, ejecuta con timeout/reintentos y devuelve los artefactos que genera (rutas relativas a `projects/<id>/`).

| # | Estado | Entrada | Salida (artefacto) | Herramienta | Timeout | Reintentos |
|---|--------|---------|--------------------|-------------|---------|------------|
| 1 | IDEA | texto del usuario o `ideas/inbox/*.json` | `project.json` creado | orquestador | — | — |
| 2 | RESEARCH | idea | `research.md` (fuentes + datos), plantilla y duración elegidas | búsqueda web + LLM | 300 s | 2 |
| 3 | SCRIPT | research | `script.json` (5 hooks, narración, beats) | LLM | 180 s | 3 |
| 4 | STORYBOARD | script | `storyboard.json` (segmentos con tiempos) | LLM | 180 s | 2 |
| 5 | ASSETS | storyboard | archivos en `assets/` del proyecto | stock/APIs/IA | 600 s | 2 |
| 6 | VOICE | script | `voice.mp3` + duración real | edge-tts | 300 s | 3 |
| 7 | EDITING | storyboard + voz + assets | `edit_plan.json`, `subtitles.ass/.srt` | FFmpeg (plan) + whisper | 600 s | 2 |
| 8 | RENDERING | edit plan | `renders/<id>.mp4` (1080×1920) | FFmpeg | 900 s | 2 |
| 9 | QC | render | `qc_report.json` → COMPLETED o corrección | ffprobe/ffmpeg | 300 s | 1 |

## Detalle por etapa

### 1 · IDEA
Se crea `projects/<id>/` con `project.json` (estado `IDEA`). Origen: usuario (`new`), lote (`batch`) o Trend Agent (`process-inbox`).

### 2 · RESEARCH
- Investiga la idea (búsqueda web), guarda **fuentes** en `research.md`.
- Selecciona **plantilla** (`templates/<n>/template.yml`) y **duración objetivo** (15/30/45/60 s según densidad de información y límites de plataforma, ver `configs/platforms.yml`).
- Extrae 3–5 datos clave que el guion debe incluir.

### 3 · SCRIPT
- Genera **5 hooks** (1–3 s), selecciona el más fuerte y justifica por qué.
- Estructura: hook → desarrollo rápido → información principal → sorpresa/curiosidad → cierre (+CTA solo si aporta).
- Sin introducciones largas. Narración escrita para TTS natural.

### 4 · STORYBOARD
Convierte los beats del guion en segmentos temporales. Cada segmento especifica: duración, narración, texto en pantalla, asset (tipo + prompt/ruta), animación, transición y SFX. Ejemplo: `projects/_ejemplo/storyboard.json`.

### 5 · ASSETS
Resuelve cada `asset` del storyboard: imagen/video generado por IA (futuro), gameplay, capturas, material del usuario, recursos del repo o stock. Todo queda copiado dentro del proyecto.

### 6 · VOICE
TTS con la config de `configs/voice.yml` (idioma, voz, velocidad, tono, pausas). Guarda la **duración real** del audio: el EDITING re-sincroniza los tiempos del storyboard con ella.

### 7 · EDITING
- Transcribe `voice.mp3` con whisper → tiempos por palabra → `subtitles.ass` (grupos de 2–4 palabras, keywords resaltadas, posición segura).
- Genera `edit_plan.json`: filtergraph FFmpeg con cortes, zoom/pan, transiciones, música con ducking y SFX en los beats.

### 8 · RENDERING
Ejecuta el plan → `renders/<id>.mp4` (1080×1920, 9:16, fps de la plantilla). Exporta también la miniatura a `thumbnails/`.

### 9 · QC
Validaciones técnicas (existencia, audio, sincronía voz/subtítulos, pantallas negras, freezes, texto fuera de safe zones, duración, formato, tamaño, assets disponibles). Si falla: **corregir → re-render → re-validar** (máx. 3 loops) → si no, `FAILED` con diagnóstico.

## Reanudación

    Video #024:  ✓ Research ✓ Script ✓ Storyboard ✓ Assets ✓ Voice ✓ Editing ✗ Rendering
    python -m src.main resume video-0024   →   continúa en RENDERING
