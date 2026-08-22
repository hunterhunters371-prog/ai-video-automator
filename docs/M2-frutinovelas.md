# M2 — Frutinovelas: personajes que hablan (diseño)

Decisiones del 22-ago-2026: **ruta gratis total** (Colab + SadTalker; MuseTalk
en v2) y **formato narrador + escenas de personajes**. Costo objetivo: $0.

## Formato del producto

Mini historias verticales 9:16 de 10-40 s: un narrador conduce la trama y los
personajes (frutas/objetos antropomórficos con cara) hablan en escenas clave.
Subtítulos siempre, con color por personaje. Destino: YouTube Shorts.

## Pipeline extendido

```
IDEA → RESEARCH → SCRIPT(historia) → PERSONAJE → STORYBOARD → ASSETS
     → VOICE(multi-voz) → ANIMATE(Colab) → EDITING → RENDERING → QC
```

### SCRIPT — modo historia

El LLM devuelve JSON con:

- `personajes[]`: nombre, especie ("limón", "taza"), `descriptor` visual FIJO
  (se repite palabra por palabra en cada prompt → coherencia), `voz` edge-tts
  asignada (pool por defecto en `script.py`; sobreescribible con
  `character_voices` en configs/voice.yml). El narrador usa la voz principal.
- `lineas[]`: `quien` (`narrador` | nombre de personaje), `texto`, `emocion`,
  `escena` (índice). Mezcla narración y diálogo.

Se activa con `mode: historia` en la plantilla. La plantilla nueva vive en
`templates/frutinovela/template.yml`; las 8 existentes siguen sirviendo para
el modo carrusel — `--template` decide el modo. Por compatibilidad mientras
llega ANIMATE, el script de historia también rellena `narration` y `beats`
(una entrada por escena), así STORYBOARD/EDITING actuales no se rompen.

### PERSONAJE — etapa nueva

Genera la **hoja de personaje**: retrato frontal, fondo neutro, cara visible,
con el `descriptor` fijo. Se guarda en `projects/<id>/characters/<nombre>.png`
y se reutiliza en TODAS las escenas habladas y episodios futuros. Idempotente
como el resto de etapas.

### STORYBOARD / ASSETS

Cada escena declara `fondo` (prompt IA, sin personaje) + `personaje_presente`.
v1: la escena hablada usa directamente la hoja del personaje (primer plano);
el fondo IA sirve para escenas del narrador. v2 [futuro]: composición del
personaje sobre el fondo.

### VOICE — multi-voz

Una pista por línea con la voz de su `quien` (edge-tts). Artefactos:
`voice/l001_narrador.mp3`, `voice/l002_limon.mp3`, ... + `voice/lines.json`
(offset y duración por línea — base del manifiesto de ANIMATE). Además se
ensambla `assets/voice.mp3` con ffmpeg (concat + re-encode) para que EDITING
y RENDERING actuales sigan funcionando sin cambios. Cada archivo de línea es
idempotente: un retry solo regenera lo que falta.

### ANIMATE — etapa nueva, corre en COLAB (no en Cloud Shell)

Cloud Shell no tiene GPU → la etapa se divide en dos mitades:

1. **Export (Cloud Shell)**: al llegar a ANIMATE sin clips listos, el pipeline
   empaqueta `projects/<id>/para_colab.zip` (hojas de personaje + audios por
   línea + `manifiesto.json` con el mapa línea→personaje→audio) e imprime las
   instrucciones. El proyecto queda PAUSADO (ANIMATE no completada).
2. **Cómputo (Colab)**: `notebooks/animar.ipynb` (botón "Open in Colab" en el
   repo): el usuario sube `para_colab.zip`, Ejecutar todo → instala SadTalker,
   genera `clips/l002.mp4`, ... (boca sincronizada con el audio) y descarga
   `clips.zip`.
3. **Import (Cloud Shell)**: el usuario sube `clips.zip` (menú ⋮ → Upload),
   `python -m src.main resume <id>` → ANIMATE verifica los clips contra el
   manifiesto, marca completada y siguen EDITING → RENDERING → QC.

Son 2 transferencias manuales por video (zip de ida, zip de vuelta). Es el
precio de $0 con GPU gratis. Si más adelante se paga una API de lip-sync,
ANIMATE se vuelve local sin tocar el resto del pipeline (misma interfaz de
artefactos).

### RENDERING / QC

RENDERING monta: clips hablados + escenas de narrador (Ken Burns, ya existe) +
narración + subtítulos ASS con color por personaje. QC suma un check: `toda
línea de diálogo tiene su clip` (y sigue siendo técnico, no estético).

## Límites honestos de la ruta gratis

- Colab free: GPU T4 (~15 GB), sesiones de hasta ~12 h con posibles cortes;
  SadTalker en T4 tarda minutos por clip corto [no verificado en esta cuenta].
  Un episodio = 3-6 clips hablados → cabe en una sesión.
- SadTalker tiene dependencias antiguas (torch específico): el notebook fija
  versiones y se marca [no verificado] hasta correrlo completo una vez.
- Coherencia de personaje = descriptor fijo + hoja reutilizada: buena, no
  perfecta. La v2 (misma semilla / LoRA) queda fuera de M2.

## Orden de construcción

1. **SCRIPT modo historia + plantilla frutinovela + VOICE multi-voz —
   CONSTRUIDO (22-ago) [no verificado en corrida real].** Probar con:
   `python -m src.main new "<idea>" --template frutinovela`
   y verificar `projects/<id>/voice/lines.json` (una entrada por línea con su
   voz). El video resultante aún es visualmente carrusel: es lo esperado hasta
   los pasos 2-4.
2. PERSONAJE (hoja consistente).
3. Export `para_colab.zip` + pausa con instrucciones en ANIMATE.
4. `notebooks/animar.ipynb` (SadTalker en Colab).
5. Import de clips + `resume`.
6. Subtítulos por personaje + check QC de clips.
