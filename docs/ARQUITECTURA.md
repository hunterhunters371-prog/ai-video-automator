# Arquitectura técnica

## 1. Principios de diseño

1. **La IA decide, el código ejecuta.** El LLM toma decisiones creativas (selección de idea, guion, hooks, storyboard, elección de recursos, correcciones de QC). El código orquesta de forma determinista: estados, reintentos, timeouts, render y validación.
2. **Modular.** Cada etapa del pipeline es un módulo con la misma interfaz (`BaseStage`). Se puede reemplazar el TTS, el motor de edición o el proveedor de imágenes sin tocar el resto.
3. **Persistente.** Todo el estado vive en GitHub: `projects/<id>/project.json` es la fuente de verdad de cada video.
4. **Recuperable.** Checkpoint después de cada etapa. `resume` continúa desde el último estado completado; un fallo en RENDERING nunca destruye el guion ni los recursos ya generados.
5. **Escalable.** Plantillas reutilizables + producción por lotes con diversidad garantizada.

## 2. Vista por capas

```
┌─ Entrada ────────────────────────────────────────────┐
│  Tú (CLI/Notion)  │  Roblox Trend Agent (futuro)     │
│  idea directa     │  ideas/inbox/<fecha>-<slug>.json │
└─────────┬────────────────────────────────────────────┘
          ▼
┌─ Orquestador (src/orchestrator.py) ──────────────────┐
│  Máquina de estados · checkpoints · timeouts ·       │
│  reintentos con backoff · registro de errores        │
└─────────┬────────────────────────────────────────────┘
          ▼
┌─ Etapas (src/stages/*) ──────────────────────────────┐
│  research · script · storyboard · assets · voice ·   │
│  editing · rendering · qc                            │
└─────────┬────────────────────────────────────────────┘
          ▼
┌─ Proveedores (intercambiables por config) ───────────┐
│  LLM │ TTS │ Imagen IA │ Stock │ Música │ Whisper    │
└─────────┬────────────────────────────────────────────┘
          ▼
┌─ Almacenamiento: GitHub ─────────────────────────────┐
│  proyectos, configs, plantillas, logs (git normal)   │
│  binarios grandes → Git LFS / GitHub Releases        │
└──────────────────────────────────────────────────────┘
```

## 3. Modelo de datos

### 3.1 `projects/<id>/project.json` — estado del proyecto

```json
{
  "id": "video-0001",
  "idea": { "text": "...", "source": "user | trend-agent" },
  "template": "roblox",
  "duration_target_s": 30,
  "language": "es",
  "platforms": ["youtube_shorts", "tiktok", "instagram_reels"],
  "state": "RENDERING",
  "completed": ["IDEA", "RESEARCH", "SCRIPT", "STORYBOARD", "ASSETS", "VOICE", "EDITING"],
  "artifacts": {
    "research": "research.md",
    "script": "script.json",
    "storyboard": "storyboard.json",
    "voice": "assets/voice.mp3",
    "subtitles": "subtitles.ass",
    "edit_plan": "edit_plan.json",
    "render": "../../renders/video-0001.mp4",
    "qc_report": "qc_report.json"
  },
  "attempts": { "RENDERING": 2 },
  "errors": [
    { "stage": "RENDERING", "error": "ffmpeg exit 1: ...", "at": "2026-08-20T19:00:00Z" }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### 3.2 `ideas/inbox/<fecha>-<slug>.json` — contrato con el agente de tendencias

```json
{
  "title": "Nuevo evento de Roblox anunciado",
  "summary": "...",
  "sources": ["https://..."],
  "trend_score": 0.87,
  "suggested_template": "roblox",
  "suggested_duration_s": 30,
  "detected_at": "2026-08-20T18:00:00Z"
}
```

El Trend Agent **solo escribe en `ideas/inbox/`**. `python -m src.main process-inbox` convierte cada archivo en un proyecto y lo mueve a `ideas/processed/`.

### 3.3 `script.json` — guion estructurado

```json
{
  "hooks": ["...", "...", "...", "...", "..."],
  "selected_hook": 0,
  "narration": "Texto completo optimizado para TTS (pausas, números en letra).",
  "beats": [
    { "role": "hook", "text": "...", "max_s": 3 },
    { "role": "contexto", "text": "...", "max_s": 6 },
    { "role": "dato_clave", "text": "...", "max_s": 9 },
    { "role": "revelacion", "text": "...", "max_s": 7 },
    { "role": "cierre_cta", "text": "...", "max_s": 5 }
  ],
  "cta_included": true,
  "prompt_used": "..."
}
```

Reglas del guion: hook de 1–3 s, desarrollo rápido, sin introducciones largas, un elemento de sorpresa/curiosidad, CTA solo cuando aporta. El LLM genera **5 hooks** y selecciona el más fuerte (los ejemplos de estructura son referencia, no texto a copiar).

### 3.4 `storyboard.json` — la única fuente de verdad de la edición

La edición es determinista: **todo lo que aparece en pantalla sale de este JSON**. Ver ejemplo completo en `projects/_ejemplo/storyboard.json`. Cada segmento define: `t` (rango), `role`, `narration`, `on_screen_text`, `asset` (tipo + ruta), `animation`, `transition_in`, `sfx`.

### 3.5 `qc_report.json`

```json
{
  "passed": false,
  "checks": [
    { "name": "exists", "ok": true },
    { "name": "has_audio", "ok": true },
    { "name": "black_frames", "ok": false, "detail": "negro 1.2s en t=14.0" }
  ],
  "fix_applied": "recortar segmento 4 y re-renderizar",
  "loop": 2
}
```

## 4. Máquina de estados

`IDEA → RESEARCH → SCRIPT → STORYBOARD → ASSETS → VOICE → EDITING → RENDERING → QC → COMPLETED`
+ estado terminal `FAILED` (reanudable).

Mapeo con el pipeline conceptual:

| Paso conceptual | Estado |
|---|---|
| IDEA | IDEA |
| ANÁLISIS + SELECCIÓN DE FORMATO + INVESTIGACIÓN | RESEARCH |
| GUION + HOOK | SCRIPT |
| STORYBOARD | STORYBOARD |
| GENERACIÓN/RECOPILACIÓN DE RECURSOS | ASSETS |
| VOZ | VOICE |
| EDICIÓN + SUBTÍTULOS + EFECTOS | EDITING |
| RENDER + EXPORTACIÓN | RENDERING |
| CONTROL DE CALIDAD | QC |

Reglas:

- Cada etapa es **idempotente**: si su artefacto ya existe y es válido, no se repite el trabajo.
- Al terminar una etapa se actualiza `completed[]` y se guarda `project.json` (checkpoint).
- `resume` busca el primer estado no completado y continúa desde ahí.
- `FAILED` conserva todos los artefactos y el historial de errores.

## 5. Reintentos, timeouts y logs

- Cada etapa tiene `timeout_s` y `retries` configurables en `configs/pipeline.yml`.
- Backoff exponencial entre reintentos (`5s × 2^n`).
- Todo error se anexa a `project.json.errors` y a `logs/<id>.log` (con timestamp y etapa).
- El contador `attempts` también se persiste: una interrupción a mitad de reintentos no reinicia el conteo.

## 6. Proveedores (capa de abstracción)

| Capacidad | Interfaz | MVP | Futuro |
|---|---|---|---|
| LLM | `llm.complete(prompt) → str` | OpenAI/Anthropic vía `.env` | modelos locales |
| Voz TTS | `tts.speak(text, voice_cfg) → mp3` | `edge-tts` (gratuito) | ElevenLabs, OpenAI TTS |
| Imágenes | `images.generate(prompt) → png` | stock (Pexels) + material del usuario | SDXL / Flux / DALL·E |
| Video IA | `video.generate(prompt) → mp4` | — (no en MVP) | Runway / Pika / Kling |
| Subtítulos | `transcribe(audio) → words[]` | `faster-whisper` (tiempos por palabra) | — |
| Música/SFX | biblioteca local | `assets/music` con licencia | generación con IA |

El texto de narración se preprocesa para TTS (números en letra, pausas con puntuación, siglas espaciadas) para que no suene robótico.

## 7. Motor de edición

**MVP: FFmpeg generado desde `storyboard.json`.** El orquestador traduce cada segmento a un filtergraph: zoom/pan (Ken Burns), `xfade` para transiciones, overlays de texto grande, mezcla de música con *ducking* bajo la voz, SFX en los beats, y subtítulos `.ass` incrustados.

**Futuro: Remotion** (React) para motion graphics complejos, manteniendo el mismo `storyboard.json` como entrada.

Prioridad de la edición: **ritmo y retención** — corte visual cada 2–4 s, cambio sincronizado con palabras clave, nunca imágenes estáticas en secuencia.

## 8. Subtítulos

1. `faster-whisper` transcribe la voz generada → tiempos por palabra.
2. Agrupación inteligente: 2–4 palabras por línea, máx. ~22 caracteres, corte en pausas naturales.
3. Resaltado de palabras clave (color `highlight` de la plantilla).
4. Posición: tercio inferior con *safe zones* de Shorts/TikTok/Reels; nunca tapa el centro de la escena.
5. Salida: `.ass` (estilos) + `.srt` (compatibilidad), guardados también en `subtitles/`.

## 9. Control de calidad

**v1 — técnico (determinista, MVP):**

- Existe el archivo, tamaño > 0, duración dentro del objetivo ±1.5 s.
- `ffprobe`: resolución 1080×1920, fps, streams de audio y video presentes.
- `ffmpeg blackdetect` / `freezedetect`: sin pantallas negras ni congelados.
- `loudnorm`: volumen dentro de rango; voz audible sobre la música.
- Validación de cajas de subtítulos dentro de *safe zones*.
- Artefactos referenciados en `storyboard.json` existen.

**Loop QC:** si algo falla → el LLM propone corrección sobre el storyboard/plan → re-render → re-validar. Máximo `max_qc_loops` (por defecto 3); después, `FAILED` con diagnóstico completo.

**v2 — semántico (futuro):** un VLM compara narración vs. imagen por segmento (¿la imagen muestra lo que dice la voz?).

## 10. Plantillas

`templates/<nombre>/template.yml` define: estructura narrativa (roles y duración máxima por beat), tipografía, colores, posición de subtítulos, animaciones, transiciones, música (mood + volumen), SFX y duración objetivo. Incluidas: `news`, `gaming`, `roblox`, `facts`, `top10`, `storytelling`, `reaction`, `announcement`. El stage RESEARCH elige plantilla según la idea; el usuario puede forzarla con `--template`.

## 11. Producción por lotes

`batch` recibe un tema y N. El LLM genera N ideas con una **matriz de diversidad** (subtema × ángulo × plantilla × duración), descarta las demasiado similares entre sí y crea un proyecto independiente por idea. Cada proyecto mantiene su propio estado: un fallo en el Short 07 no afecta al resto del lote.

## 12. Binarios grandes en GitHub

GitHub limita archivos a 100 MB y no está pensado para mucho binario. Estrategia:

- **git normal:** código, configs, plantillas, estados, guiones, storyboards, logs.
- **Git LFS:** renders finales y assets pesados que sí se quieran versionar.
- **GitHub Releases:** archivo histórico opcional de videos publicados.
- `.gitignore` ya bloquea commits accidentales de material de trabajo.

## 13. Secretos

Claves de API en `.env` local (ignorado por git) o en *GitHub Secrets* si se automatiza con Actions. Nunca en el repo.

## 14. Panel de control (fase posterior)

Opciones, en orden de esfuerzo: (a) `status` por consola — ya en el CLI; (b) `dashboard.json` generado por el orquestador + GitHub Pages; (c) base de datos de Notion sincronizada como panel visual. Muestra: totales (completed/processing/failed), estado por proyecto, progreso, errores, duración de procesamiento, fecha y archivo final.
