# 🤖 AI Video Automator

Sistema autónomo de producción de videos cortos con IA para **YouTube Shorts, TikTok e Instagram Reels**.

> **Idea → video terminado**, sin edición manual.

El usuario escribe:

    Crea un Short sobre el próximo evento de Roblox.

y el sistema produce el proyecto completo: investigación, guion con hook, storyboard, recursos, voz, edición, subtítulos, control de calidad y render final vertical 9:16.

## Pipeline

    IDEA → RESEARCH → SCRIPT → STORYBOARD → ASSETS → VOICE
         → EDITING → RENDERING → QC → COMPLETED
                                    ↘ FAILED (reanudable)

Cada etapa guarda un **checkpoint** en `projects/<id>/project.json`. Si algo falla o se interrumpe, `resume` continúa desde el último estado completado — **nunca desde cero**.

## Estructura del repositorio

```
ai-video-automator/
├── ideas/           # Ideas manuales e inbox del agente de tendencias
│   └── inbox/       # Contrato de entrada para el Roblox Trend Agent
├── scripts/         # Guiones generados (respaldo; la fuente de verdad es el proyecto)
├── assets/          # Recursos reutilizables
│   ├── images/
│   ├── videos/
│   ├── audio/
│   └── music/       # Solo música con licencia adecuada
├── projects/        # Un proyecto por video: estado, artefactos, errores
├── renders/         # Videos finales (binarios grandes → Git LFS)
├── subtitles/       # Subtítulos generados (.srt/.ass)
├── thumbnails/      # Miniaturas
├── templates/       # Plantillas reutilizables de estilo/estructura
├── configs/         # Configuración del pipeline, plataformas y voz
├── logs/            # Registro de ejecución y errores por proyecto
├── completed/       # Manifiesto de proyectos terminados
└── src/             # Orquestador, máquina de estados y etapas
```

## Documentación

- [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) — diseño técnico completo
- [docs/MVP.md](docs/MVP.md) — alcance del MVP y fases
- [docs/PIPELINE.md](docs/PIPELINE.md) — especificación etapa por etapa

## Uso (objetivo del MVP)

```bash
pip install -r requirements.txt   # requiere además el binario `ffmpeg`

python -m src.main new "Crea un Short sobre el próximo evento de Roblox"
python -m src.main resume video-0001     # reanuda desde el último checkpoint
python -m src.main status                # panel por consola
python -m src.main batch ideas.txt --count 10
python -m src.main process-inbox         # convierte ideas/inbox/*.json en proyectos
```

## Principio fundamental

Esto no es un script que genera videos: es un **sistema de producción automatizada de contenido**.

- **La IA decide** (idea, guion, hooks, storyboard, selección de recursos, correcciones de QC).
- **El código ejecuta** de forma determinista (pipeline, estados, reintentos, render, validación).
- **Modular, persistente, recuperable, escalable y basado en GitHub.**
